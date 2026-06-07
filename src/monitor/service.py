"""
MonitorService — asyncio background-thread polling engine for Volt.

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
from collections import deque

from hidpp.features import voltage_to_percent
from drivers import get_all_drivers, get_driver_for_device

_VOLTAGE_WINDOW = 4  # readings to average (~4 min at 60s poll)
import monitor.bt_backend as bt_backend
from monitor.registry import DeviceRegistry
from monitor.state import KNOWN_DEVICES, DeviceState, DeviceStatus, BtDeviceInfo, BtScanResultEvent
from ui.settings_manager import load_config, save_config


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
        poll_interval: float = 3.0,
    ) -> None:
        self._ui_queue = ui_queue
        self._registry = registry
        self.poll_interval = poll_interval
        self._loop = asyncio.new_event_loop()
        self._thread: threading.Thread | None = None
        self._poll_task: asyncio.Task | None = None
        self._bt_poll_task: asyncio.Task | None = None
        # Open HID device handles keyed by (vid, pid, dev_idx).
        # Accessed exclusively on the bg asyncio thread.
        self._open: dict[tuple[int, int, int], object] = {}
        # Rolling voltage history for smoothing (keyed same as _open).
        self._voltage_history: dict[tuple[int, int, int], deque] = {}
        # Discovered BT devices keyed by bt_id str.
        # Accessed exclusively on the bg asyncio thread.
        self._bt_devices: dict[str, BtDeviceInfo] = {}
        # Last poll timestamp for each device key (vid, pid, dev_idx).
        self._last_poll_time: dict[tuple[int, int, int], float] = {}
        # Last poll timestamp for BT devices.
        self._last_bt_poll_time: float = 0.0
        # Tracks percent before charging starts to display valid info
        self._percent_before_charging: dict[tuple[int, int, int], int] = {}
        # Tracks last time the charging percent was updated for each device
        self._last_charging_percent_update: dict[tuple[int, int, int], float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the daemon background thread and start the polling loop."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._start_poll_loop(), self._loop)

    async def _start_poll_loop(self) -> None:
        """Schedule _poll_loop and _bt_poll_loop as tracked Tasks so stop() can cancel them cleanly."""
        self._poll_task = asyncio.ensure_future(self._poll_loop())
        self._bt_poll_task = asyncio.ensure_future(self._bt_poll_loop())

    def stop(self) -> None:
        """Close all open handles and shut down the asyncio loop cleanly.

        Cancels the poll tasks and then AWAITS them (via asyncio.gather with
        return_exceptions=True) so each task's CancelledError is consumed before
        the loop stops.  Without the await, Python prints
        "Task was destroyed but it is pending!" for every cancelled task on GC
        (BUG-01).

        All mutations of self._open are routed through the bg loop so this method
        is data-race-free with poll_once() / discover() (CR-01).
        """
        async def _shutdown() -> None:
            tasks = []
            if self._poll_task is not None:
                self._poll_task.cancel()
                tasks.append(self._poll_task)
            if self._bt_poll_task is not None:
                self._bt_poll_task.cancel()
                tasks.append(self._bt_poll_task)
            if tasks:
                # Wait for every cancelled task to fully handle CancelledError.
                # return_exceptions=True prevents gather itself from raising.
                await asyncio.gather(*tasks, return_exceptions=True)
            for key, handle in list(self._open.items()):
                driver = get_driver_for_device(key[0], key[1])
                if driver:
                    driver.close_device(handle)
            self._open.clear()
            self._loop.stop()

        # No-op if start() was never called — the loop isn't running so
        # run_coroutine_threadsafe would raise RuntimeError.
        if self._thread is None:
            return
        asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _is_running(self) -> bool:
        """Return True if the bg thread is alive (i.e. start() was called)."""
        return self._thread is not None and self._thread.is_alive()


    def rescan(self) -> concurrent.futures.Future:
        """Thread-safe entry point for the hot-plug callback (03-03).

        Schedules a new discover() run on the bg asyncio loop and returns the
        Future so the caller can optionally wait or add callbacks.
        """
        return asyncio.run_coroutine_threadsafe(self.discover(), self._loop)

    def scan_bt_devices(self) -> concurrent.futures.Future:
        """Thread-safe entry point for the Devices page scan button (BT-03).

        Schedules _run_bt_scan() on the bg loop; returns the Future so the caller
        can attach a done callback. Result arrives via _ui_queue as BtScanResultEvent.
        """
        return asyncio.run_coroutine_threadsafe(self._run_bt_scan(), self._loop)

    def add_monitored_device(self, entry: dict) -> None:
        """Thread-safe: register a device (BT or HID) for polling after user adds it to monitoring."""
        def _do() -> None:
            device_id = entry.get("id")
            if not device_id:
                return
            if device_id.startswith("hid:"):
                # Trigger discover immediately on the loop to open handle and start polling
                asyncio.ensure_future(self.discover())
            else:
                bt_id = device_id
                if bt_id not in self._bt_devices:
                    status = DeviceStatus.ONLINE if entry.get("connected", True) else DeviceStatus.OFFLINE
                    info = BtDeviceInfo(
                        bt_id=bt_id,
                        name=entry.get("name", "Unknown"),
                        battery=entry.get("battery"),
                        ble_address=entry.get("ble_address"),
                        status=status,
                    )
                    self._bt_devices[bt_id] = info
                    self._ui_queue.put(info)

                    # Run an immediate resolve_battery for this device in the background so it updates instantly
                    async def _poll_single():
                        connected = True
                        container_id = None
                        try:
                            from winrt.windows.devices.enumeration import DeviceInformation
                            d_info = await DeviceInformation.create_from_id_async_additional_properties(
                                bt_id, ["System.Devices.Aep.IsConnected", "System.Devices.Aep.ContainerId"]
                            )
                            if d_info:
                                connected = bool(bt_backend._get_winrt_prop(d_info.properties, "System.Devices.Aep.IsConnected"))
                                container_id = bt_backend._get_winrt_prop(d_info.properties, "System.Devices.Aep.ContainerId")
                        except Exception:
                            pass

                        battery = None
                        if container_id:
                            battery = await bt_backend.query_container_battery(container_id)

                        if battery is None:
                            device_info = {"battery": info.battery, "ble_address": info.ble_address}
                            battery = await bt_backend.resolve_battery(device_info)

                        is_online = connected

                        updated = BtDeviceInfo(
                            bt_id=bt_id,
                            name=info.name,
                            battery=battery,
                            ble_address=info.ble_address,
                            status=DeviceStatus.ONLINE if is_online else DeviceStatus.OFFLINE,
                        )
                        self._bt_devices[bt_id] = updated
                        self._ui_queue.put(updated)
                    asyncio.ensure_future(_poll_single())
        self._loop.call_soon_threadsafe(_do)

    def add_bt_device(self, entry: dict) -> None:
        """Thread-safe: register a BT device for polling (retained for backward compatibility)."""
        self.add_monitored_device(entry)

    def remove_monitored_device(self, device_id: str) -> None:
        """Thread-safe: stop polling/tracking a device (BT or HID) after removal from monitoring."""
        def _do() -> None:
            if device_id.startswith("hid:"):
                parts = device_id.split(":")
                if len(parts) == 3:
                    try:
                        vid = int(parts[1], 16)
                        pid = int(parts[2], 16)
                        for key in list(self._open.keys()):
                            if key[0] == vid and key[1] == pid:
                                handle = self._open.pop(key)
                                driver = get_driver_for_device(vid, pid)
                                if driver:
                                    driver.close_device(handle)
                                self._voltage_history.pop(key, None)
                                self._registry.mark_offline(key)
                    except Exception:
                        pass
            else:
                self._bt_devices.pop(device_id, None)
        self._loop.call_soon_threadsafe(_do)

    def remove_bt_device(self, bt_id: str) -> None:
        """Thread-safe: stop polling a BT device (retained for backward compatibility)."""
        self.remove_monitored_device(bt_id)

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
            await self.poll_once(force=False)
            await asyncio.sleep(1.0)

    async def _bt_poll_loop(self) -> None:
        """Continuous Bluetooth polling coroutine: poll BT status every 5 seconds."""
        while True:
            await self._poll_bt_devices()
            await asyncio.sleep(5.0)

    async def _run_bt_scan(self) -> None:
        """Enumerate connected Bluetooth and HID devices and put a BtScanResultEvent on the queue (BT-03)."""
        bt_devices = await bt_backend.winrt_enumerate_bt()

        hid_devices = []
        import hid
        try:
            # Enumerate all connected HID devices
            all_hid = hid.enumerate()
            for info in all_hid:
                vid = info["vendor_id"]
                pid = info["product_id"]

                # Check if this device is registered/known, or is a Logitech/SteelSeries/SinoWealth device
                is_known = (vid, pid) in KNOWN_DEVICES
                is_logitech = (vid == 0x046D)
                is_steelseries = (vid == 0x1038)
                is_sinowealth = (vid == 0x258A)

                if is_known or is_logitech or is_steelseries or is_sinowealth:
                    # Determine a friendly name for display
                    if is_known:
                        name = KNOWN_DEVICES[(vid, pid)]
                    else:
                        prod_str = info.get("product_string")
                        if prod_str:
                            name = f"{prod_str} (Unsupported)"
                        else:
                            if is_logitech:
                                brand = "Logitech"
                            elif is_steelseries:
                                brand = "SteelSeries"
                            elif is_sinowealth:
                                brand = "SinoWealth"
                            else:
                                brand = "Generic"
                            name = f"Unknown {brand} Device (VID:{vid:04X}, PID:{pid:04X})"

                    hid_id = f"hid:{vid:04X}:{pid:04X}"
                    if not any(d["id"] == hid_id for d in hid_devices):
                        # Use already-open handle for battery probe if available.
                        # Never open a temp handle here: if the device is already
                        # open on self._open the second open risks a double-open
                        # conflict on some OS versions (BUG-03).  For unmonitored
                        # devices, battery=None is shown as "N/A" in the scan list;
                        # the real value is populated by poll_once() once the user
                        # adds the device to monitoring.
                        battery_val = None
                        driver = get_driver_for_device(vid, pid)
                        if driver:
                            key = (vid, pid, driver.dev_idx)
                            handle = self._open.get(key)
                            if handle:
                                try:
                                    res = driver.probe_battery(handle, driver.dev_idx)
                                    if res and res.percent != 0:
                                        battery_val = res.percent
                                except Exception:
                                    pass

                        hid_devices.append({
                            "id": hid_id,
                            "name": name,
                            "battery": battery_val,
                            "type": "hid",
                            "connected": True,
                        })
        except Exception:
            pass

        self._ui_queue.put(BtScanResultEvent(devices=bt_devices + hid_devices))

    async def discover(self) -> None:
        """Enumerate receivers, open new ones, and immediately mark disappeared ones OFFLINE.

        Called on startup and on every WM_DEVICECHANGE (via rescan()). Because it runs on
        both plug AND unplug events, it serves as the fast unplug detector: any handle in
        self._open whose device is no longer enumerable is closed and marked OFFLINE here,
        without waiting for the next poll_once() cycle.
        """
        found_keys: set[tuple[int, int, int]] = set()
        all_interfaces = []
        
        for driver in get_all_drivers():
            interfaces = driver.find_devices(verbose=False)
            for info in interfaces:
                vid, pid = info["vendor_id"], info["product_id"]
                if (vid, pid) in KNOWN_DEVICES:
                    found_keys.add((vid, pid, driver.dev_idx))
                    info['_driver'] = driver
                    all_interfaces.append(info)

        # Load config to filter and auto-monitor
        cfg = load_config()
        monitored = cfg.get("monitored_devices", [])
        ignored = cfg.get("ignored_devices", [])
        monitored_ids = {d["id"] for d in monitored if d.get("type") == "hid"}

        # Mark any open handle that disappeared or is no longer monitored as OFFLINE immediately (HID-04 fast path).
        for key in list(self._open.keys()):
            vid, pid, dev_idx = key
            hid_id = f"hid:{vid:04X}:{pid:04X}"
            if key not in found_keys or hid_id not in monitored_ids:
                offline_state = self._registry.mark_offline(key)
                if offline_state is not None and hid_id in monitored_ids:
                    self._ui_queue.put(offline_state)
                handle = self._open[key]
                driver = get_driver_for_device(key[0], key[1])
                if driver:
                    driver.close_device(handle)
                del self._open[key]
                self._voltage_history.pop(key, None)

        # Open handles for newly-appeared devices that are monitored or not ignored (auto-monitor connected devices)
        changed = False
        for info in all_interfaces:
            vid = info["vendor_id"]
            pid = info["product_id"]
            driver = info['_driver']
            key = (vid, pid, driver.dev_idx)
            hid_id = f"hid:{vid:04X}:{pid:04X}"

            if hid_id not in monitored_ids and hid_id in ignored:
                continue

            if key in self._open:
                continue  # already open; poll_once() owns live state
            try:
                handle = driver.open_device(info)
            except OSError:
                continue
            self._open[key] = handle

            # Since it successfully opened, ensure it is added to monitored
            if hid_id not in monitored_ids:
                name = KNOWN_DEVICES[(vid, pid)]
                monitored.append({
                    "id": hid_id,
                    "name": name,
                    "type": "hid"
                })
                changed = True
                monitored_ids.add(hid_id)

            device_name = KNOWN_DEVICES[(vid, pid)]
            state = DeviceState(
                vid=vid,
                pid=pid,
                dev_idx=driver.dev_idx,
                device_name=device_name,
                percent=None,
                charging=False,
                status=DeviceStatus.ONLINE,
            )
            self._registry.upsert(state)
            self._ui_queue.put(state)

        if changed:
            cfg["monitored_devices"] = monitored
            save_config(cfg)

        # Push OFFLINE state for any monitored HID device that is not currently connected
        for entry in monitored:
            if entry.get("type") == "hid":
                hid_id = entry["id"]
                parts = hid_id.split(":")
                if len(parts) == 3:
                    try:
                        vid = int(parts[1], 16)
                        pid = int(parts[2], 16)
                        is_open = any(k[0] == vid and k[1] == pid for k in self._open)
                        if not is_open:
                            device_name = entry.get("name", KNOWN_DEVICES.get((vid, pid), "Unknown"))
                            driver = get_driver_for_device(vid, pid)
                            dev_idx = driver.dev_idx if driver else 0
                            state = DeviceState(
                                vid=vid,
                                pid=pid,
                                dev_idx=dev_idx,
                                device_name=device_name,
                                percent=None,
                                charging=False,
                                status=DeviceStatus.OFFLINE,
                            )
                            self._registry.upsert(state)
                            self._ui_queue.put(state)
                    except Exception:
                        pass

        # Load persisted BT devices from config and register them for polling (BT-04).
        # These don't get opened like HID devices; they are polled via resolve_battery().
        for entry in monitored:
            if entry.get("type", "bt") == "bt":
                bt_id = entry.get("id")
                if bt_id and bt_id not in self._bt_devices:
                    info = BtDeviceInfo(
                        bt_id=bt_id,
                        name=entry.get("name", "Unknown"),
                        battery=None,
                        ble_address=entry.get("ble_address"),
                        status=DeviceStatus.ONLINE,
                    )
                    self._bt_devices[bt_id] = info
                    self._ui_queue.put(info)  # create card immediately; poll will fill battery
        await self._poll_bt_devices()

    async def _poll_bt_devices(self) -> None:
        """Helper to query and update battery/online status for all tracked Bluetooth devices."""
        for bt_id, bt_info in list(self._bt_devices.items()):
            connected = True
            container_id = None
            try:
                from winrt.windows.devices.enumeration import DeviceInformation
                d_info = await DeviceInformation.create_from_id_async_additional_properties(
                    bt_id, ["System.Devices.Aep.IsConnected", "System.Devices.Aep.ContainerId"]
                )
                if d_info:
                    connected = bool(bt_backend._get_winrt_prop(d_info.properties, "System.Devices.Aep.IsConnected"))
                    container_id = bt_backend._get_winrt_prop(d_info.properties, "System.Devices.Aep.ContainerId")
            except Exception:
                pass

            battery = None
            if container_id:
                battery = await bt_backend.query_container_battery(container_id)

            if battery is None:
                device_info = {"battery": bt_info.battery, "ble_address": bt_info.ble_address}
                battery = await bt_backend.resolve_battery(device_info)

            is_online = connected

            updated = BtDeviceInfo(
                bt_id=bt_id,
                name=bt_info.name,
                battery=battery,
                ble_address=bt_info.ble_address,
                status=DeviceStatus.ONLINE if is_online else DeviceStatus.OFFLINE,
            )
            self._bt_devices[bt_id] = updated
            self._ui_queue.put(updated)

    async def poll_once(self, force: bool = True) -> None:
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
        import time
        now = time.time()

        for key, handle in list(self._open.items()):
            vid, pid, dev_idx = key

            if not force:
                current_state = self._registry.get(key)
                is_offline = current_state is None or current_state.status == DeviceStatus.OFFLINE
                
                if is_offline:
                    interval = 3.0
                else:
                    interval = self.poll_interval
                    
                last_poll = self._last_poll_time.get(key, 0.0)
                if now - last_poll < interval:
                    continue

            self._last_poll_time[key] = now

            driver = get_driver_for_device(vid, pid)
            if driver is None:
                continue
            
            result = driver.probe_battery(handle, dev_idx)
            if result is None or result.percent == 0:
                # Headset off, transitioning, or zero-voltage transient — mark
                # OFFLINE but keep handle so recovery is automatic on next poll.
                offline_state = self._registry.mark_offline(key)
                if offline_state is not None:
                    self._ui_queue.put(offline_state)
            else:
                if result.voltage_mv != 0:
                    # Smooth raw voltage over the last _VOLTAGE_WINDOW readings to
                    # eliminate ADC jitter that causes ±1% flicker.
                    hist = self._voltage_history.setdefault(key, deque(maxlen=_VOLTAGE_WINDOW))
                    hist.append(result.voltage_mv)
                    smoothed_percent = voltage_to_percent(round(sum(hist) / len(hist)))
                else:
                    # SteelSeries reports voltage_mv=0; use percent directly, no smoothing.
                    smoothed_percent = result.percent
                # D-03: charging=True → CHARGING; else → ONLINE
                status = DeviceStatus.CHARGING if result.charging else DeviceStatus.ONLINE
                
                if result.charging:
                    if key not in self._percent_before_charging:
                        last_state = self._registry.get(key)
                        if last_state and last_state.percent is not None:
                            self._percent_before_charging[key] = last_state.percent
                        else:
                            self._percent_before_charging[key] = smoothed_percent
                        self._last_charging_percent_update[key] = now
                    
                    # Update baseline charging percent only once every 2 minutes (120s)
                    last_update = self._last_charging_percent_update.get(key, 0.0)
                    if now - last_update >= 120.0:
                        self._last_charging_percent_update[key] = now
                        if smoothed_percent is not None and self._percent_before_charging[key] is not None:
                            if smoothed_percent > self._percent_before_charging[key]:
                                self._percent_before_charging[key] = smoothed_percent
                            
                    percent = self._percent_before_charging.get(key, smoothed_percent)
                else:
                    self._percent_before_charging.pop(key, None)
                    self._last_charging_percent_update.pop(key, None)
                    percent = smoothed_percent

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

        # BT device battery refresh (BT-04): re-run resolve_battery() for each tracked BT device.
        if force or (now - self._last_bt_poll_time >= self.poll_interval):
            self._last_bt_poll_time = now
            await self._poll_bt_devices()
