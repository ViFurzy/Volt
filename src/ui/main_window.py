"""MainWindow — VOLT | POWER CENTER application shell.

Layout:
    central widget
      +-- QHBoxLayout
            +-- SidebarNav (fixed width 210px)
            +-- QStackedWidget (5 pages — D-03)
                  +-- page 0: Dashboard  (device cards, side-by-side)
                  +-- page 1: Devices    ("Coming soon")
                  +-- page 2: History    ("Coming soon")
                  +-- page 3: Profiles   ("Coming soon")
                  +-- page 4: Settings

dashboard_layout is a QHBoxLayout: cards insert left-to-right, stretch at end.
Cards are limited to two per row; QScrollArea handles overflow.

Close-to-tray: closeEvent hides instead of quitting (D-08, Research Pattern 2).
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
    """Main application window for VOLT | POWER CENTER."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VOLT | POWER CENTER")
        self.resize(960, 620)

        # ── Stack pages ────────────────────────────────────────────
        self._stack = QStackedWidget()

        # Page 0 — Dashboard
        dashboard_page, self.dashboard_layout, self._count_label = self._build_dashboard()
        self._stack.addWidget(dashboard_page)   # index 0

        # Pages 1-3 — Placeholders
        for name in ("Devices", "History", "Profiles"):
            self._stack.addWidget(_PlaceholderPage(name))  # indices 1, 2, 3

        # Page 4 — Settings
        self._settings_page = SettingsPage()
        self._stack.addWidget(self._settings_page)          # index 4

        # ── Sidebar ────────────────────────────────────────────────
        self._sidebar = SidebarNav(self._stack)

        # ── Central layout ─────────────────────────────────────────
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack)
        self.setCentralWidget(central)

        # Device card registry keyed by (vid, pid, dev_idx)
        self._cards: dict[tuple[int, int, int], DeviceCard] = {}

    # ── Dashboard builder ──────────────────────────────────────────

    def _build_dashboard(
        self,
    ) -> tuple[QWidget, QHBoxLayout, QLabel]:
        """Return (scroll-wrapped page, card row layout, count label)."""
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        # "All Devices (N)" heading
        count_label = QLabel("All Devices (0)")
        count_label.setObjectName("dashboardHeader")
        count_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        outer.addWidget(count_label)

        # Card row — QHBoxLayout with trailing stretch
        cards_row = QWidget()
        cards_layout = QHBoxLayout(cards_row)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(16)
        cards_layout.addStretch()   # trailing stretch (tests assert last item has no widget)
        outer.addWidget(cards_row)
        outer.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        return scroll, cards_layout, count_label

    # ── Close-to-tray ──────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()

    def show_restore(self) -> None:
        """Restore window from tray."""
        self.show()
        self.raise_()
        self.activateWindow()

    # ── Device update consumer ─────────────────────────────────────

    def on_device_update(self, state: DeviceState) -> None:
        """Create or update the DeviceCard for the given DeviceState.

        First call for a (vid, pid, dev_idx) key creates a DeviceCard and
        inserts it into dashboard_layout before the trailing stretch.
        Subsequent calls update the existing card in place.
        """
        key = (state.vid, state.pid, state.dev_idx)
        if key not in self._cards:
            card = DeviceCard(state)
            self._cards[key] = card
            # Insert before trailing stretch
            stretch_idx = self.dashboard_layout.count() - 1
            self.dashboard_layout.insertWidget(stretch_idx, card)
            # Register in sidebar Devices sub-items
            self._sidebar.register_device(key, state.device_name)
            # Update header count
            self._count_label.setText(f"All Devices ({len(self._cards)})")
        else:
            self._cards[key].update_state(state)


class _PlaceholderPage(QWidget):
    """Simple placeholder for sidebar sections not yet implemented."""

    def __init__(self, section_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(f"{section_name} — Coming soon")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 16px; color: #555566;")
        layout.addWidget(lbl)
