"""
MonitorService — asyncio background-thread polling engine for PeriphWatcher.

Owns the 60-second polling loop that discovers known devices, reads battery
via the Phase 2 protocol layer, and pushes full DeviceState snapshots to a
thread-safe queue.Queue for the Qt main thread to consume.

Architecture invariants (from CLAUDE.md):
  - All HID I/O runs exclusively on the asyncio background thread (self._loop).
  - Cross-thread communication via queue.Queue only — never direct attribute reads
    across threads for device state.
  - hid device opens use open_receiver() via open_path() — never hid.open(vid, pid)
    which risks opening the wrong interface.
"""

import asyncio
import concurrent.futures
import queue
import threading

from hidpp.receiver import (
    DEVICE_IDX,
    find_receiver,
    open_receiver,
)
from hidpp.features import battery_probe_chain
from monitor.registry import DeviceRegistry
from monitor.state import KNOWN_DEVICES, DeviceState, DeviceStatus


class MonitorService:
    """Asyncio-based background polling engine.

    Lifecycle:
        service = MonitorService(ui_queue, registry)
        service.start()   # launches daemon thread + schedules _poll_loop
        ...
        service.stop()    # shuts down gracefully

    All HID calls happen inside coroutines running on self._loop (the bg thread).
    The Qt main thread NEVER calls HID functions directly.

    Thread-safe entry points for the main thread:
        service.rescan()  — schedule a re-discovery (used by WM_DEVICECHANGE in 03-03)
    """

    def __init__(
        self,
        ui_queue: queue.Queue,
        registry: DeviceRegistry,
        poll_interval: float = 60.0,
    ) -> None:
        self._ui_queue = ui_queue
        self._registry = registry
        self.poll_interval = poll_interval
        self._loop = asyncio.new_event_loop()
        self._thread: threading.Thread | None = None
        self._poll_task: asyncio.Task | None = None
        # Open HID device handles keyed by (vid, pid, dev_idx).
        # Accessed exclusively on the bg asyncio thread.
        self._open: dict[tuple[int, int, int], object] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the daemon background thread and start the polling loop."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._start_poll_loop(), self._loop)

    async def _start_poll_loop(self) -> None:
        """Schedule _poll_loop as a tracked Task so stop() can cancel it cleanly."""
        self._poll_task = asyncio.ensure_future(self._poll_loop())

    def stop(self) -> None:
        """Close all open handles and shut down the asyncio loop cleanly.

        All mutations of self._open are routed through the bg loop via a single
        call_soon_threadsafe callback. This prevents the data race where the Qt
        main thread and the asyncio bg thread both access self._open concurrently
        (CR-01: stop() previously iterated self._open directly from the main thread
        while poll_once() or discover() could be running on the bg thread).
        """
        def _shutdown() -> None:
            if self._poll_task is not None:
                self._poll_task.cancel()
            for handle in list(self._open.values()):
                try:
                    handle.close()
                except Exception:
                    pass
            self._open.clear()
            self._loop.stop()

        self._loop.call_soon_threadsafe(_shutdown)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def rescan(self) -> concurrent.futures.Future:
        """Thread-safe entry point for the hot-plug callback (03-03).

        Schedules a new discover() run on the bg asyncio loop and returns the
        Future so the caller can optionally wait or add callbacks.
        """
        return asyncio.run_coroutine_threadsafe(self.discover(), self._loop)

    # ------------------------------------------------------------------
    # Background thread entry point
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Run the asyncio event loop on the daemon thread (mirrors threading_stub)."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # ------------------------------------------------------------------
    # Coroutines (run on bg asyncio thread)
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Continuous polling coroutine: discover once, then poll every interval."""
        await self.discover()
        while True:
            await self.poll_once()
            await asyncio.sleep(self.poll_interval)

    async def discover(self) -> None:
        """Enumerate receivers, open new ones, and immediately mark disappeared ones OFFLINE.

        Called on startup and on every WM_DEVICECHANGE (via rescan()). Because it runs on
        both plug AND unplug events, it serves as the fast unplug detector: any handle in
        self._open whose device is no longer enumerable is closed and marked OFFLINE here,
        without waiting for the next poll_once() cycle.
        """
        interfaces = find_receiver(verbose=False)

        # Build the set of currently-enumerable known-device keys.
        found_keys: set[tuple[int, int, int]] = set()
        for info in interfaces:
            vid = info["vendor_id"]
            pid = info["product_id"]
            if (vid, pid) in KNOWN_DEVICES:
                found_keys.add((vid, pid, DEVICE_IDX))

        # Mark any open handle that disappeared as OFFLINE immediately (HID-04 fast path).
        for key in list(self._open.keys()):
            if key not in found_keys:
                offline_state = self._registry.mark_offline(key)
                if offline_state is not None:
                    self._ui_queue.put(offline_state)
                try:
                    self._open[key].close()
                except Exception:
                    pass
                del self._open[key]

        # Open handles for newly-appeared known devices.
        for info in interfaces:
            vid = info["vendor_id"]
            pid = info["product_id"]
            if (vid, pid) not in KNOWN_DEVICES:
                continue
            key = (vid, pid, DEVICE_IDX)
            if key in self._open:
                continue  # already open; poll_once() owns live state
            try:
                handle = open_receiver(info)
            except OSError:
                continue
            self._open[key] = handle
            device_name = KNOWN_DEVICES[(vid, pid)]
            state = DeviceState(
                vid=vid,
                pid=pid,
                dev_idx=DEVICE_IDX,
                device_name=device_name,
                percent=None,
                charging=False,
                status=DeviceStatus.ONLINE,
            )
            self._registry.upsert(state)
            self._ui_queue.put(state)

    async def poll_once(self) -> None:
        """Read battery for all open devices and push snapshots to the queue.

        On None result or 0% (headset off or transitioning): mark OFFLINE but
        KEEP the handle open. This allows automatic recovery when the headset
        powers back on without the dongle being replugged — the next poll cycle
        will detect the live reading and transition back to ONLINE.

        Handles are only closed by discover() when the dongle is physically
        unplugged (fast-path via WM_DEVICECHANGE).

        percent=0 is treated as offline because:
        - The G Pro X calibration floor is 3320 mV; 0 mV is a transient reading
          as the headset powers down, not a genuine empty battery.
        - Genuine 0% battery means the headset has already shut down.
        """
        for key, handle in list(self._open.items()):
            vid, pid, dev_idx = key
            result = battery_probe_chain(handle, dev_idx)
            if result is None or result.percent == 0:
                # Headset off, transitioning, or zero-voltage transient — mark
                # OFFLINE but keep handle so recovery is automatic on next poll.
                offline_state = self._registry.mark_offline(key)
                if offline_state is not None:
                    self._ui_queue.put(offline_state)
            else:
                # D-03: charging=True → CHARGING; else → ONLINE
                status = DeviceStatus.CHARGING if result.charging else DeviceStatus.ONLINE
                # During CHARGING, hide the voltage-elevated % (charger current
                # inflates voltage to ~4.2 V regardless of actual charge state).
                # Show None so the UI renders "CHARGING" without a misleading %.
                percent = None if result.charging else result.percent
                device_name = KNOWN_DEVICES.get((vid, pid), "Unknown")
                state = DeviceState(
                    vid=vid,
                    pid=pid,
                    dev_idx=dev_idx,
                    device_name=device_name,
                    percent=percent,
                    charging=result.charging,
                    status=status,
                )
                self._registry.upsert(state)
                self._ui_queue.put(state)
