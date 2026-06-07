"""TrayManager — QSystemTrayIcon lifecycle for Volt.

Pattern 1 from RESEARCH: icon + menu set BEFORE show() (Pitfall 3).
DoubleClick on the tray icon restores the main window (D-07).
"""
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from ui.icon import make_volt_icon


class TrayManager:
    """Owns the QSystemTrayIcon lifecycle.

    Attributes:
        _tray:   the underlying QSystemTrayIcon
        _window: the MainWindow to restore on Show / DoubleClick
        _menu:   the context menu (kept alive as instance attr)

    Usage:
        tray = TrayManager(window, qapp)
        tray.show()   # call AFTER construction; icon+menu already wired
    """

    def __init__(self, window, qapp: QApplication) -> None:
        self._window = window

        self._tray = QSystemTrayIcon(parent=qapp)
        self._tray.setIcon(make_volt_icon())
        self._tray.setToolTip("VOLT | POWER CENTER")

        # Build context menu (D-07): Show the app | ---- | Quit
        parent_widget = window if isinstance(window, QWidget) else None
        self._menu = QMenu(parent=parent_widget)
        
        self._show_action = self._menu.addAction("Show the app")
        self._show_action.triggered.connect(window.show_restore)

        self._compact_action = self._menu.addAction("Compact mode")
        self._compact_action.triggered.connect(window.enter_widget_mode)

        self._menu.addSeparator()

        self._quit_action = self._menu.addAction("Quit")
        self._quit_action.triggered.connect(qapp.quit)

        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)
        # Icon + menu are set; show() is called externally after construction.

    def show(self) -> None:
        """Make the tray icon visible. Must be called after icon + menu are set."""
        self._tray.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (D-07)."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._window.show_restore()

