"""MainWindow — application shell for PeriphWatcher.

Sidebar-driven QStackedWidget with 5 pages (D-03).
Close-to-tray: closeEvent hides instead of quitting (D-08, Research Pattern 2).
on_device_update is a Wave-3 stub; Wave 3 (04-03) fills the device card logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.device_card import DeviceCard
from ui.settings_page import SettingsPage
from ui.sidebar import SidebarNav

if TYPE_CHECKING:
    from monitor.state import DeviceState


class MainWindow(QMainWindow):
    """Main application window.

    Layout:
        central widget
          +-- QHBoxLayout
                +-- SidebarNav (fixed width)
                +-- QStackedWidget
                      +-- page 0: DashboardPage  (Wave 3 fills device cards)
                      +-- page 1: DevicesPage    ("Coming soon")
                      +-- page 2: HistoryPage    ("Coming soon")
                      +-- page 3: ProfilesPage   ("Coming soon")
                      +-- page 4: SettingsPage
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PeriphWatcher")
        self.resize(900, 600)

        # ---------------------------------------------------------------
        # Build the QStackedWidget pages
        # ---------------------------------------------------------------
        self._stack = QStackedWidget()

        # Page 0 — Dashboard (Wave 3 populates with DeviceCards)
        self._dashboard_widget = QWidget()
        self.dashboard_layout = QVBoxLayout(self._dashboard_widget)
        self.dashboard_layout.setContentsMargins(16, 16, 16, 16)
        self.dashboard_layout.setSpacing(12)
        self.dashboard_layout.addStretch()
        dashboard_scroll = QScrollArea()
        dashboard_scroll.setWidgetResizable(True)
        dashboard_scroll.setWidget(self._dashboard_widget)
        self._stack.addWidget(dashboard_scroll)  # index 0

        # Pages 1-3 — Coming soon placeholders
        for label in ("Devices", "History", "Profiles"):
            page = _PlaceholderPage(label)
            self._stack.addWidget(page)            # indices 1, 2, 3

        # Page 4 — Settings
        self._settings_page = SettingsPage()
        self._stack.addWidget(self._settings_page)  # index 4

        # ---------------------------------------------------------------
        # Sidebar + main area layout
        # ---------------------------------------------------------------
        self._sidebar = SidebarNav(self._stack)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack)
        self.setCentralWidget(central)

        # Wave 3: device card lookup dict keyed by (vid, pid, dev_idx)
        self._cards: dict[tuple[int, int, int], object] = {}

    # ------------------------------------------------------------------
    # close-to-tray (D-08, Research Pattern 2)
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        """Hide the window instead of closing it.

        event.ignore() suppresses Qt's default close/destroy behaviour.
        QApplication.setQuitOnLastWindowClosed(False) (set in __main__)
        ensures the process does not exit when the window is hidden.
        """
        event.ignore()
        self.hide()

    def show_restore(self) -> None:
        """Restore window from tray: show, bring to front, activate."""
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # Consumer hook (Wave 3 stub)
    # ------------------------------------------------------------------

    def on_device_update(self, state: DeviceState) -> None:
        """Create or update the DeviceCard for the given DeviceState.

        Called by the main-thread QTimer drain when a DeviceState arrives
        from the background asyncio thread via queue.Queue (architecture
        invariant: all Qt widget mutation on main thread only).

        First call for a (vid, pid, dev_idx) key creates a DeviceCard and
        inserts it into dashboard_layout before the trailing stretch.
        Subsequent calls update the existing card in place — no duplicates.
        """
        key = (state.vid, state.pid, state.dev_idx)
        if key not in self._cards:
            card = DeviceCard(state)
            self._cards[key] = card
            # Insert before the trailing stretch item so cards stack top-down
            stretch_idx = self.dashboard_layout.count() - 1
            self.dashboard_layout.insertWidget(stretch_idx, card)
        else:
            self._cards[key].update_state(state)


class _PlaceholderPage(QWidget):
    """Simple 'Coming soon' page for sidebar items not active in Phase 4."""

    def __init__(self, section_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(f"{section_name} — Coming soon")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 16px; color: #888888;")
        layout.addWidget(lbl)
