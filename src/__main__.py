import sys
sys.coinit_flags = 0  # MUST be here — before any other import. pythoncom reads this flag exactly once on first COM init. PySide6/pywin32 imports initialize COM as STA; bleak WinRT backend requires MTA. If STA is set first, await client.connect() hangs forever silently.

import os
import signal

# When run as `python -m src`, Python adds the project root to sys.path but not
# the src/ directory itself. Add src/ so that monitor.*, ui.*, hidpp.* are importable.
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from monitor.app import MonitorApp
from ui.main_window import MainWindow
from ui.styles import DARK_QSS
from ui.tray import TrayManager


def main() -> None:
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)  # REQUIRED: keeps process alive when window hides (Pitfall 2)
    qapp.setStyleSheet(DARK_QSS)

    window = MainWindow()
    tray = TrayManager(window, qapp)
    tray.show()

    # Qt's event loop on Windows swallows SIGINT unless a QTimer is ticking.
    # A 200ms heartbeat lets Python process the signal; the handler calls quit().
    signal.signal(signal.SIGINT, lambda *_: qapp.quit())
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)  # wake Python every 200ms

    app_obj = MonitorApp(consumer=window.on_device_update, poll_interval=2.0)
    app_obj.start()

    # build_hotplug() MUST come after QApplication is created (winId requires it).
    # Keep explicit references — GC before first event silently disables hotplug/drain.
    hotplug = app_obj.build_hotplug()
    timer = app_obj.make_timer()  # noqa: F841 — kept alive intentionally

    window.show()
    qapp.exec()

    # Clean shutdown
    app_obj.stop()
    hotplug.unregister()


if __name__ == "__main__":
    main()
