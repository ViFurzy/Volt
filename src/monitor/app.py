"""
MonitorApp — wiring layer for Phase 3 components.

Combines MonitorService (asyncio bg polling), DeviceRegistry (shared store),
and HotPlugWatcher (WM_DEVICECHANGE) behind a single entry point that drives
a consumer callback from the Qt main thread via a QTimer-drained queue.Queue.

Architecture invariants (from CLAUDE.md):
  - All HID I/O runs on the asyncio bg thread inside MonitorService.
  - This class never performs HID I/O directly.
  - Cross-thread communication via queue.Queue only (QTimer drain on main thread).
  - sys.coinit_flags = 0 belongs in the entry point (run_monitor.py), not here.
"""

import queue
from typing import Callable

from PySide6.QtCore import QTimer

from monitor.hotplug import HotPlugWatcher
from monitor.registry import DeviceRegistry
from monitor.service import MonitorService
from monitor.state import DeviceState


class MonitorApp:
    """Wires MonitorService + DeviceRegistry + HotPlugWatcher for the Phase 3 stack.

    Does NOT own the QApplication — the entry point creates and owns it.

    Lifecycle (entry point responsibility):
        qapp = QApplication([])
        app_obj = MonitorApp(consumer)
        app_obj.start()
        hotplug = app_obj.build_hotplug()   # must come after QApplication exists
        timer   = app_obj.make_timer()       # keep reference to prevent GC
        qapp.exec()
        app_obj.stop()
        hotplug.unregister()
    """

    def __init__(
        self,
        consumer: Callable[[DeviceState], None],
        poll_interval: float = 60.0,
        drain_ms: int = 500,
    ) -> None:
        self.ui_queue: queue.Queue = queue.Queue()
        self.registry = DeviceRegistry()
        self.service = MonitorService(self.ui_queue, self.registry, poll_interval)
        self._consumer = consumer
        self._drain_ms = drain_ms

    def build_hotplug(self) -> HotPlugWatcher:
        """Construct and register a HotPlugWatcher bound to self.service.

        MUST be called after a QApplication exists (winId requires it).
        The caller is responsible for keeping the returned reference alive
        (T-03-11: GC before events arrive silently disables hot-plug).
        """
        watcher = HotPlugWatcher(self.service)
        watcher.register()
        return watcher

    def drain(self) -> None:
        """Drain all queued DeviceState snapshots and pass each to the consumer.

        Called by QTimer every drain_ms on the Qt main thread. Mirrors the
        drain_queue pattern from threading_stub.py lines 32-41.
        Silently exits on queue.Empty — that is the normal empty-cycle case.
        """
        try:
            while True:
                state: DeviceState = self.ui_queue.get_nowait()
                self._consumer(state)
        except queue.Empty:
            pass

    def make_timer(self) -> QTimer:
        """Create a QTimer that calls self.drain every drain_ms milliseconds.

        Returns the timer so the caller can keep a reference (T-03-11: GC
        before the first tick silently stops all queue processing).
        """
        timer = QTimer()
        timer.timeout.connect(self.drain)
        timer.start(self._drain_ms)
        return timer

    def start(self) -> None:
        """Launch the MonitorService asyncio bg thread and start the polling loop."""
        self.service.start()

    def stop(self) -> None:
        """Close all HID handles and shut down the asyncio loop cleanly."""
        self.service.stop()
