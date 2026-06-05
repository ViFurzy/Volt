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
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from monitor.state import BtDeviceInfo, BtScanResultEvent
from ui.device_card import DeviceCard
from ui.devices_page import DevicesPage
from ui.settings_manager import load_config, save_config
from ui.settings_page import SettingsPage
from ui.sidebar import SidebarNav

if TYPE_CHECKING:
    from monitor.state import DeviceState


class MainWindow(QMainWindow):
    """Main application window for VOLT | POWER CENTER."""

    def __init__(self, service=None, loop=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._loop = loop
        self.setWindowTitle("VOLT | POWER CENTER")
        self.resize(960, 620)

        # ── Stack pages ────────────────────────────────────────────
        self._stack = QStackedWidget()

        # Page 0 — Dashboard
        dashboard_page, self.dashboard_layout, self._count_label = self._build_dashboard()
        self._stack.addWidget(dashboard_page)   # index 0

        # Page 1 — Devices
        self._devices_page = DevicesPage(
            service=service,
            loop=loop,
            remove_card_callback=self.remove_bt_card,
        )
        self._stack.addWidget(self._devices_page)           # index 1

        # Pages 2-3 — Placeholders
        for name in ("History", "Profiles"):
            self._stack.addWidget(_PlaceholderPage(name))   # indices 2, 3

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

        # Device card registry: keyed by (vid, pid, dev_idx) for HID devices, str bt_id for BT devices
        self._cards: dict = {}

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

    # ── Close behaviour ────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle the X button.

        Checks saved preference first. If none is saved and the window is
        actually visible, shows a dialog asking the user what to do.
        Falls back to hide (tray) when called headlessly (e.g. in tests).
        """
        event.ignore()

        cfg = load_config()
        behavior = cfg.get("close_behavior")

        if behavior == _CloseDialog.QUIT:
            QApplication.instance().quit()
            return
        if behavior == _CloseDialog.TRAY:
            self.hide()
            return

        # No saved preference — skip dialog if window isn't actually on screen
        if not self.isVisible():
            self.hide()
            return

        dlg = _CloseDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.hide()
            return

        if dlg.remember:
            save_config({**cfg, "close_behavior": dlg.choice})

        if dlg.choice == _CloseDialog.QUIT:
            QApplication.instance().quit()
        else:
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

    def on_bt_device_update(self, info: BtDeviceInfo) -> None:
        """Create or update a DeviceCard for a BT device keyed by bt_id.

        Uses info.bt_id as the card registry key (string, not tuple).
        Card created when first battery reading arrives; updated on subsequent polls.
        """
        from monitor.state import DeviceState, DeviceStatus
        key = info.bt_id
        if key not in self._cards:
            adapter = DeviceState(
                vid=0, pid=0, dev_idx=0,
                device_name=info.name,
                percent=info.battery,
                charging=False,
                status=DeviceStatus.ONLINE,
            )
            card = DeviceCard(adapter)
            self._cards[key] = card
            stretch_idx = self.dashboard_layout.count() - 1
            self.dashboard_layout.insertWidget(stretch_idx, card)
            self._sidebar.register_device(key, info.name)
            self._count_label.setText(f"All Devices ({len(self._cards)})")
        else:
            adapter = DeviceState(
                vid=0, pid=0, dev_idx=0,
                device_name=info.name,
                percent=info.battery,
                charging=False,
                status=DeviceStatus.ONLINE,
            )
            self._cards[key].update_state(adapter)

    def remove_bt_card(self, bt_id: str) -> None:
        """Remove the dashboard card for a BT device.

        Called by DevicesPage._on_remove_clicked. Pops the card from _cards
        and detaches it from the layout by reparenting to None.
        Safe to call when no card exists for bt_id (no-op).
        """
        card = self._cards.pop(bt_id, None)
        if card:
            card.setParent(None)
            self._count_label.setText(f"All Devices ({len(self._cards)})")

    def on_scan_result(self, devices: list) -> None:
        """Route scan results to the DevicesPage list widget (BT-03)."""
        self._devices_page.on_scan_result(devices)


class _CloseDialog(QDialog):
    """Modal dialog shown when the user clicks the window X button.

    Offers "Keep in tray" vs "Close app" with an optional "Remember" checkbox.
    """

    TRAY = "tray"
    QUIT = "quit"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VOLT | POWER CENTER")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setFixedSize(360, 168)
        self._choice = self.TRAY

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        msg = QLabel(
            "Would you like to minimize to the system tray,\n"
            "or close the application?"
        )
        msg.setStyleSheet("font-size: 13px; color: #CCCCDD;")
        layout.addWidget(msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_tray = QPushButton("Keep in tray")
        btn_tray.setStyleSheet(
            "QPushButton { background-color: #282366; color: #7B9FFF;"
            " border: 1px solid #7B9FFF; border-radius: 6px; padding: 8px 16px; font-size: 13px; }"
            "QPushButton:hover { background-color: #32306a; }"
        )
        btn_tray.clicked.connect(lambda: self._select(self.TRAY))

        btn_quit = QPushButton("Close app")
        btn_quit.setStyleSheet(
            "QPushButton { background-color: #2a1a1a; color: #EE6800;"
            " border: 1px solid #EE6800; border-radius: 6px; padding: 8px 16px; font-size: 13px; }"
            "QPushButton:hover { background-color: #3a2020; }"
        )
        btn_quit.clicked.connect(lambda: self._select(self.QUIT))

        btn_row.addWidget(btn_tray)
        btn_row.addWidget(btn_quit)
        layout.addLayout(btn_row)

        self._remember = QCheckBox("Remember my choice")
        self._remember.setStyleSheet("font-size: 12px; color: #888899;")
        layout.addWidget(self._remember)

    def _select(self, choice: str) -> None:
        self._choice = choice
        self.accept()

    @property
    def choice(self) -> str:
        return self._choice

    @property
    def remember(self) -> bool:
        return self._remember.isChecked()


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
