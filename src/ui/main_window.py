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

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from monitor.state import BtDeviceInfo, BtScanResultEvent, DeviceStatus
from ui.device_card import DeviceCard
from ui.devices_page import DevicesPage
from ui.flow_layout import FlowLayout
from ui.history_page import HistoryPage
from ui.settings_manager import get_config_generation, load_config, save_config
from ui.settings_page import SettingsPage
from ui.sidebar import SidebarNav
from ui.widget_window import WidgetWindow

if TYPE_CHECKING:
    from monitor.state import DeviceState


class _HFWWidget(QWidget):
    """QWidget that exposes its layout's height-for-width to QScrollArea.

    QScrollArea with widgetResizable=True checks sizePolicy().hasHeightForWidth()
    and calls heightForWidth() to determine how tall the widget should be as its
    width changes. A plain QWidget returns -1 from heightForWidth(), so the scroll
    area never grows the container vertically when cards wrap to new rows.
    This subclass fixes that by delegating to the layout.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def heightForWidth(self, w: int) -> int:
        if self.layout() and self.layout().hasHeightForWidth():
            return self.layout().heightForWidth(w)
        return super().heightForWidth(w)


class _EdgeHandle(QWidget):
    """Invisible drag handle for resizing a frameless window."""
    def __init__(self, edge: str, window: QMainWindow):
        super().__init__(window)
        self.edge = edge
        self.window = window
        self._drag_pos = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        
        if edge == "right":
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.setFixedWidth(6)
        elif edge == "bottom":
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self.setFixedHeight(6)
        elif edge == "corner":
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            self.setFixedSize(6, 6)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._drag_pos = event.globalPosition().toPoint()
            
            geom = self.window.geometry()
            if self.edge in ("right", "corner"):
                geom.setWidth(max(self.window.minimumWidth(), geom.width() + delta.x()))
            if self.edge in ("bottom", "corner"):
                geom.setHeight(max(self.window.minimumHeight(), geom.height() + delta.y()))
            self.window.setGeometry(geom)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()


class _AddPlaceholder(QFrame):
    """Empty-state card shown on dashboard to add new devices.
    
    Uses a dashed border to look like an empty drop-zone.
    """

    def __init__(self, on_click, parent=None) -> None:
        super().__init__(parent)
        self._on_click = on_click
        self.setObjectName("addDevicePlaceholder")
        self.setStyleSheet("""
            #addDevicePlaceholder {
                background: transparent;
                border: 2px dashed #444455;
                border-radius: 12px;
            }
            #addDevicePlaceholder:hover {
                border: 2px dashed #7B9FFF;
                background: rgba(123, 159, 255, 0.05);
            }
        """)
        self.setMinimumSize(220, 240)
        self.setMaximumSize(340, 260)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        plus = QLabel("+")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus.setStyleSheet("font-size: 56px; font-weight: 300; color: #7B9FFF; border: none; background: transparent;")

        label = QLabel("Add device")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888899; border: none; background: transparent;")

        layout.addStretch()
        layout.addWidget(plus)
        layout.addWidget(label)
        layout.addStretch()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    """Main application window for VOLT | POWER CENTER."""

    def __init__(self, service=None, loop=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowMinimizeButtonHint)
        self._service = service
        self._loop = loop
        self.setWindowTitle("VOLT | POWER CENTER")
        self.resize(1024, 640)
        self.setMinimumSize(760, 520)
        self._drag_pos = None

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

        # Page 2 — History
        self._history_page = HistoryPage()
        self._stack.addWidget(self._history_page)           # index 2

        # Page 3 — Profiles Placeholder
        self._stack.addWidget(_PlaceholderPage("Profiles")) # index 3

        # Page 4 — Settings
        self._settings_page = SettingsPage(service=service, window=self)
        self._stack.addWidget(self._settings_page)          # index 4

        # ── Sidebar ────────────────────────────────────────────────
        self._sidebar = SidebarNav(self._stack)
        self._sidebar.device_selected.connect(self.show_device_history_by_key)

        # ── Central layout ─────────────────────────────────────────
        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(0, 16, 24, 0)
        title_bar.addStretch()

        widget_btn = QPushButton("⊡")
        widget_btn.setFixedSize(30, 30)
        widget_btn.setToolTip("Compact mode")
        widget_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        widget_btn.setStyleSheet("QPushButton { background: transparent; color: #888899; border: none; font-size: 16px; border-radius: 4px; } QPushButton:hover { background: #333344; color: #7B9FFF; }")
        widget_btn.clicked.connect(self.enter_widget_mode)

        min_btn = QPushButton("—")
        min_btn.setFixedSize(30, 30)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setStyleSheet("QPushButton { background: transparent; color: #888899; border: none; font-size: 14px; font-weight: bold; border-radius: 4px; } QPushButton:hover { background: #333344; color: white; }")
        min_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("QPushButton { background: transparent; color: #888899; border: none; font-size: 14px; font-weight: bold; border-radius: 4px; } QPushButton:hover { background: #E50000; color: white; }")
        close_btn.clicked.connect(self.close)

        title_bar.addWidget(widget_btn)
        title_bar.addWidget(min_btn)
        title_bar.addWidget(close_btn)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addLayout(title_bar)
        right_layout.addWidget(self._stack)

        central = QWidget()
        v_layout = QVBoxLayout(central)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)
        
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        h_layout.addWidget(self._sidebar)
        h_layout.addLayout(right_layout)
        h_layout.addWidget(_EdgeHandle("right", self))
        
        v_layout.addLayout(h_layout)
        
        bottom_h_layout = QHBoxLayout()
        bottom_h_layout.setContentsMargins(0, 0, 0, 0)
        bottom_h_layout.setSpacing(0)
        bottom_h_layout.addWidget(_EdgeHandle("bottom", self))
        bottom_h_layout.addWidget(_EdgeHandle("corner", self))
        
        v_layout.addLayout(bottom_h_layout)

        self.setCentralWidget(central)

        # Device card registry: keyed by (vid, pid, dev_idx) for HID devices, str bt_id for BT devices
        self._cards: dict = {}

        # Monitored-device ID cache (BUG-04): rebuilt only when config changes.
        # Avoids a load_config() disk read on every queue drain event.
        self._monitored_ids_cache: set[str] = set()
        self._monitored_ids_gen: int = -1
        self._device_online_time: dict[str, float] = {}

        # Compact widget — created here, shown/hidden via enter/exit_widget_mode()
        self._widget = WidgetWindow(exit_callback=self.exit_widget_mode)

    # ── Dashboard builder ──────────────────────────────────────────

    def _navigate_to_devices(self) -> None:
        """Navigate sidebar + stack to the Devices page."""
        self._sidebar.navigate_to(1)

    def _get_monitored_ids(self) -> set[str]:
        """Return the set of monitored device IDs, rebuilding only when config changed.

        Uses get_config_generation() to detect saves without re-reading disk on every
        call (BUG-04). Thread-safe for reads because this always runs on the Qt main thread.
        """
        gen = get_config_generation()
        if gen != self._monitored_ids_gen:
            cfg = load_config()
            self._monitored_ids_cache = {d["id"] for d in cfg.get("monitored_devices", [])}
            self._monitored_ids_gen = gen
        return self._monitored_ids_cache

    def _build_dashboard(
        self,
    ) -> tuple[QWidget, FlowLayout, QLabel]:
        """Return (scroll-wrapped page, card flow layout, count label)."""
        container = _HFWWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        # "All Devices (N)" heading
        count_label = QLabel("All Devices (0)")
        count_label.setObjectName("dashboardHeader")
        count_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        outer.addWidget(count_label)

        # Cards area — FlowLayout wraps cards to the next row when window is narrowed
        cards_widget = QWidget()
        cards_layout = FlowLayout(cards_widget, h_spacing=16, v_spacing=16)
        outer.addWidget(cards_widget)
        outer.addStretch()

        # Empty-state placeholder — shown when _cards is empty
        self._placeholder = _AddPlaceholder(self._navigate_to_devices)
        cards_layout.addWidget(self._placeholder)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        event.accept()

    def sync_widget(self) -> None:
        """Sync current states of all cards to the compact widget."""
        for key, card in self._cards.items():
            state = card.last_state
            if state:
                is_offline = state.status == DeviceStatus.OFFLINE
                if isinstance(key, tuple):
                    self._widget.update_device(
                        key, state.device_name, state.percent, state.charging, is_offline
                    )
                else:
                    self._widget.update_device(
                        key, state.device_name, state.percent, False, is_offline
                    )

    def enter_widget_mode(self) -> None:
        """Switch to compact widget."""
        self.sync_widget()
        cfg = load_config()
        if not cfg.get("widget_show_beside", False):
            self.hide()
        self._widget.show()

    def exit_widget_mode(self) -> None:
        """Return to full window: hide widget, restore full window if hidden."""
        self._widget.hide()
        if not self.isVisible():
            self.show()
            self.raise_()
            self.activateWindow()

    def show_restore(self) -> None:
        """Restore window from tray (or from widget mode)."""
        cfg = load_config()
        show_beside = cfg.get("widget_show_beside", False)
        if self._widget.isVisible() and not show_beside:
            self.exit_widget_mode()
            return
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
        
        # Guard: check if this HID device is still monitored
        if self._service is not None:
            hid_id = f"hid:{state.vid:04X}:{state.pid:04X}"
            if hid_id not in self._get_monitored_ids():
                if key in self._cards:
                    self.remove_card(hid_id)
                return

        hid_id = f"hid:{state.vid:04X}:{state.pid:04X}"
        is_online = state.status != DeviceStatus.OFFLINE
        if is_online:
            import time
            if hid_id not in self._device_online_time:
                self._device_online_time[hid_id] = time.time()
        else:
            self._device_online_time.pop(hid_id, None)

        if state.percent is not None:
            self._record_history(hid_id, state.device_name, state.percent)

        if key not in self._cards:
            card = DeviceCard(state, device_id=hid_id)
            card.remove_requested.connect(lambda did=hid_id: self._remove_monitored_device(did))
            card.history_requested.connect(lambda name, did=hid_id: self.show_device_history(did))
            self._cards[key] = card
            # Keep placeholder at the end
            self.dashboard_layout.removeWidget(self._placeholder)
            self.dashboard_layout.addWidget(card)
            self.dashboard_layout.addWidget(self._placeholder)
            self._sidebar.register_device(key, state.device_name)
            self._count_label.setText(f"All Devices ({len(self._cards)})")
        else:
            self._cards[key].update_state(state, device_id=hid_id)

        self._widget.update_device(
            key, state.device_name, state.percent, state.charging,
            state.status == DeviceStatus.OFFLINE,
        )

        if self._history_page._device_id == hid_id:
            self._history_page.update_state(state)

    def on_bt_device_update(self, info: BtDeviceInfo) -> None:
        """Create or update a DeviceCard for a BT device keyed by bt_id.

        Uses info.bt_id as the card registry key (string, not tuple).
        Card created when first battery reading arrives; updated on subsequent polls.
        """
        from monitor.state import DeviceState, DeviceStatus
        key = info.bt_id
        
        # Guard: check if this BT device is still monitored
        if self._service is not None:
            if key not in self._get_monitored_ids():
                if key in self._cards:
                    self.remove_card(key)
                return

        is_online = info.status != DeviceStatus.OFFLINE
        if is_online:
            import time
            if key not in self._device_online_time:
                self._device_online_time[key] = time.time()
        else:
            self._device_online_time.pop(key, None)

        if info.battery is not None:
            self._record_history(key, info.name, info.battery)

        if key not in self._cards:
            adapter = DeviceState(
                vid=0, pid=0, dev_idx=0,
                device_name=info.name,
                percent=info.battery,
                charging=False,
                status=info.status,
            )
            card = DeviceCard(adapter, device_id=key)
            card.remove_requested.connect(lambda did=key: self._remove_monitored_device(did))
            card.history_requested.connect(lambda name, did=key: self.show_device_history(did))
            self._cards[key] = card
            # Keep placeholder at the end
            self.dashboard_layout.removeWidget(self._placeholder)
            self.dashboard_layout.addWidget(card)
            self.dashboard_layout.addWidget(self._placeholder)
            self._sidebar.register_device(key, info.name)
            self._count_label.setText(f"All Devices ({len(self._cards)})")
        else:
            adapter = DeviceState(
                vid=0, pid=0, dev_idx=0,
                device_name=info.name,
                percent=info.battery,
                charging=False,
                status=info.status,
            )
            self._cards[key].update_state(adapter, device_id=key)

        self._widget.update_device(
            key, info.name, info.battery, False,
            info.status == DeviceStatus.OFFLINE,
        )

        if self._history_page._device_id == key:
            self._history_page.update_state(info)

    def _remove_monitored_device(self, device_id: str) -> None:
        """Remove a device via the card's ⋮ menu: update config then drop the card."""
        cfg = load_config()
        cfg["monitored_devices"] = [
            d for d in cfg.get("monitored_devices", []) if d["id"] != device_id
        ]
        if "history" in cfg and device_id in cfg["history"]:
            del cfg["history"][device_id]
        save_config(cfg)
        self._devices_page.remove_monitored_device(device_id)
        self.remove_card(device_id)

    def _record_history(self, device_id: str, device_name: str, percent: int) -> None:
        """Record a battery percentage reading with timestamp to config JSON."""
        import datetime
        import time

        # Connection Battery Stabilization: skip writing to history for the first 3 minutes of being online
        online_time = self._device_online_time.get(device_id)
        if online_time is not None and (time.time() - online_time < 180):
            return

        cfg = load_config()
        if "history" not in cfg:
            cfg["history"] = {}
        
        hist_list = cfg["history"].setdefault(device_id, [])
        now_str = datetime.datetime.now().isoformat()
        
        # Debounce: skip if last reading was same value and recorded less than 10 mins (600s) ago
        if hist_list:
            last = hist_list[-1]
            if last.get("percent") == percent:
                try:
                    last_dt = datetime.datetime.fromisoformat(last["timestamp"])
                    now_dt = datetime.datetime.fromisoformat(now_str)
                    if (now_dt - last_dt).total_seconds() < 600:
                        return
                except Exception:
                    pass
        
        hist_list.append({"timestamp": now_str, "percent": percent})
        cfg["history"][device_id] = hist_list[-200:]  # Keep last 200 readings
        save_config(cfg)

    def show_device_history(self, device_id: str) -> None:
        """Switch to the History page for the specified device ID from a dashboard card menu."""
        self._sidebar.select_device_by_key(device_id)

    def show_device_history_by_key(self, key: tuple | str, device_name: str) -> None:
        """Configure and show the history page for the selected device."""
        if isinstance(key, tuple) and len(key) == 3:
            device_id = f"hid:{key[0]:04X}:{key[1]:04X}"
        else:
            device_id = str(key)
        self._history_page.set_device(device_id, device_name)
        
        # Force a live update using the card's last state
        if key in self._cards and self._cards[key].last_state:
            # We must pass the raw state, but card.last_state is a _BtAdapter for BT.
            # HistoryPage duck-types it nicely.
            self._history_page.update_state(self._cards[key].last_state)

    def remove_card(self, device_id: str | tuple) -> None:
        """Remove the dashboard card for a device (BT or HID).

        Pops the card from _cards, detaches it from the layout, removes
        its sidebar sub-item, and stops the service from polling it.
        """
        keys_to_remove = []
        if isinstance(device_id, str) and device_id.startswith("hid:"):
            parts = device_id.split(":")
            if len(parts) == 3:
                try:
                    vid = int(parts[1], 16)
                    pid = int(parts[2], 16)
                    # Find matching tuple keys in self._cards
                    for k in list(self._cards.keys()):
                        if isinstance(k, tuple) and len(k) == 3 and k[0] == vid and k[1] == pid:
                            keys_to_remove.append(k)
                except Exception:
                    pass
        else:
            if device_id in self._cards:
                keys_to_remove.append(device_id)

        for card_key in keys_to_remove:
            card = self._cards.pop(card_key, None)
            if card:
                self.dashboard_layout.removeWidget(card)
                card.setParent(None)
            self._sidebar.remove_device(card_key)
            self._widget.remove_device(card_key)

        self._count_label.setText(f"All Devices ({len(self._cards)})")
        
        # Stop service monitoring using string-based device_id
        if self._service is not None:
            if isinstance(device_id, tuple) and len(device_id) == 3:
                device_id = f"hid:{device_id[0]:04X}:{device_id[1]:04X}"
            self._service.remove_monitored_device(device_id)

    def remove_bt_card(self, bt_id: str) -> None:
        """Remove the dashboard card for a BT device (backward compatibility)."""
        self.remove_card(bt_id)


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
