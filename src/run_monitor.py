import sys
sys.coinit_flags = 0  # MUST be first — before all imports. 0 = COINIT_MULTITHREADED (MTA). PySide6 and pywin32 initialize COM as STA; bleak WinRT backend requires MTA. Setting this after any import that touches COM causes await client.connect() to hang silently.

import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from monitor.app import MonitorApp
from monitor.state import DeviceState


def mock_consumer(state: DeviceState) -> None:
    """Phase 3 stand-in consumer — prints each DeviceState snapshot to stdout.

    Phase 4 replaces this with the real device-card UI update.
    """
    pct = f"{state.percent}%" if state.percent is not None else "None"
    print(
        f"[consumer] {state.device_name} | {pct} | {state.status.name}"
        f" | charging={state.charging}"
    )


def main() -> None:
    qapp = QApplication([])

    # Qt's event loop on Windows swallows SIGINT unless a QTimer is ticking.
    # A 200ms heartbeat lets Python process the signal; the handler calls quit().
    signal.signal(signal.SIGINT, lambda *_: qapp.quit())
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)  # wake Python every 200ms

    app_obj = MonitorApp(mock_consumer)
    app_obj.start()

    # build_hotplug() MUST come after QApplication is created (winId requires it).
    # Keep explicit references to both objects — T-03-11: GC before first event
    # silently disables hot-plug / queue drain.
    hotplug = app_obj.build_hotplug()
    timer = app_obj.make_timer()  # noqa: F841 — kept alive intentionally

    qapp.exec()

    # Clean shutdown (mirrors threading_stub.py lines 78-84).
    app_obj.stop()
    hotplug.unregister()


if __name__ == "__main__":
    main()
