"""Devices page widget for PeriphWatcher.

Shows paired Bluetooth and HID devices from a scan, lets the user add
devices to the monitored list, and remove them. Monitored devices persist
to config['monitored_devices'].
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from ui.settings_manager import load_config, save_config


class DevicesPage(QWidget):
    """Devices tab: scan for BT/HID devices, add/remove from monitoring.

    Constructor args:
        service  -- MonitorService (provides scan_bt_devices())
        loop     -- asyncio event loop (kept for API symmetry; not used directly)
        remove_card_callback -- Callable[[str], None] called with bt_id on remove;
                                None is safe (guarded before call)
        parent   -- optional parent QWidget
    """

    def __init__(self, service, loop, remove_card_callback=None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._loop = loop
        self._remove_card_callback = remove_card_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Heading ────────────────────────────────────────────────
        heading = QLabel("Devices")
        heading.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(heading)

        # ── Scan row ───────────────────────────────────────────────
        scan_row = QHBoxLayout()
        scan_row.setSpacing(8)
        scan_label = QLabel("Paired Bluetooth & HID devices")
        scan_label.setStyleSheet("font-size: 13px; color: #AAAACC;")
        self._scan_btn = QPushButton("Scan")
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        scan_row.addWidget(scan_label)
        scan_row.addStretch()
        scan_row.addWidget(self._scan_btn)
        layout.addLayout(scan_row)

        # ── Scan results list ──────────────────────────────────────
        self._scan_list = QListWidget()
        layout.addWidget(self._scan_list)

        # ── Add / Remove buttons ───────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._add_btn = QPushButton("Add to monitoring")
        self._remove_btn = QPushButton("Remove")
        self._add_btn.clicked.connect(self._on_add_clicked)
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Currently monitored heading ────────────────────────────
        monitored_heading = QLabel("Currently monitored")
        monitored_heading.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(monitored_heading)

        # ── Monitored devices list ─────────────────────────────────
        self._monitored_list = QListWidget()
        layout.addWidget(self._monitored_list)

        layout.addStretch()

        # Populate from config on construction
        monitored = load_config().get("monitored_devices", [])
        for entry in monitored:
            label = f"{entry.get('name', 'Unknown')}  |  {entry.get('type', 'bt').upper()}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._monitored_list.addItem(item)

    def _on_scan_clicked(self) -> None:
        """Fire-and-forget scan.

        scan_bt_devices() is a plain def (not a coroutine) that internally
        schedules work on the bg loop and returns a concurrent.futures.Future.
        Call it directly — do NOT wrap in asyncio.run_coroutine_threadsafe
        (that function requires a coroutine argument and would raise TypeError).
        The scan result arrives via _ui_queue → MonitorApp.drain() → on_scan_result().
        """
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("Scanning...")
        future = self._service.scan_bt_devices()
        future.add_done_callback(lambda f: None)  # fire-and-forget; result via queue

    def on_scan_result(self, devices: list) -> None:
        """Called by MainWindow when BtScanResultEvent arrives from drain().

        Runs on Qt main thread. Handles both BT entries (type='bt') and HID
        entries (type='hid') from the merged list.
        """
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("Scan")
        self._scan_list.clear()
        for d in devices:
            device_type = d.get("type", "bt").upper()
            battery_str = f"{d['battery']}%" if d.get("battery") is not None else "battery unknown"
            text = f"{d['name']}  |  {device_type}  |  {battery_str}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, d)
            self._scan_list.addItem(item)

    def _on_add_clicked(self) -> None:
        selected = self._scan_list.currentItem()
        if selected is None:
            return
        d = selected.data(Qt.ItemDataRole.UserRole)
        cfg = load_config()
        monitored = cfg.get("monitored_devices", [])
        if any(e["id"] == d["id"] for e in monitored):
            return  # already added
        entry = {
            "id": d["id"],
            "name": d["name"],
            "type": d.get("type", "bt"),
            "ble_address": d.get("ble_address"),
        }
        monitored.append(entry)
        cfg["monitored_devices"] = monitored
        save_config(cfg)
        label = f"{entry['name']}  |  {entry['type'].upper()}"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, entry)
        self._monitored_list.addItem(item)

    def _on_remove_clicked(self) -> None:
        selected = self._monitored_list.currentItem()
        if selected is None:
            return
        d = selected.data(Qt.ItemDataRole.UserRole)
        bt_id = d["id"]
        cfg = load_config()
        cfg["monitored_devices"] = [
            e for e in cfg.get("monitored_devices", []) if e["id"] != bt_id
        ]
        save_config(cfg)
        row = self._monitored_list.row(selected)
        self._monitored_list.takeItem(row)
        if self._remove_card_callback is not None:
            self._remove_card_callback(bt_id)

    # ------------------------------------------------------------------
    # paintEvent override — required for QSS background-color on QWidget
    # subclasses (Research Pattern 3 / Pitfall 1).
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
