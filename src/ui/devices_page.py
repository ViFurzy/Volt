"""Devices page — side-by-side drag & drop device management.

Layout:
    Left panel  — Paired Bluetooth & HID Devices (scan results)
    Right panel — Currently Monitored

Drag left → right to add a device to monitoring.
Drag right → left to remove a device from monitoring.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
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


def _battery_badge(entry: dict) -> str:
    """Return a short battery indicator for scan-list display."""
    battery = entry.get("battery")
    if battery is not None:
        return f"{battery}%"
    return "N/A"


class _DeviceList(QListWidget):
    """QListWidget with cross-list drag & drop.

    item_dropped emits the dragged entry when an item from ANOTHER list
    is dropped here. The source item is removed from its origin list.
    """
    item_dropped = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(2)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        source = event.source()
        if source is self or not isinstance(source, QListWidget):
            event.ignore()
            return
        item = source.currentItem()
        if item is None:
            event.ignore()
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        source.takeItem(source.row(item))
        self.item_dropped.emit(entry)


class DevicesPage(QWidget):
    """Devices tab: drag-and-drop device management.

    Left panel shows scan results; right panel shows monitored devices.
    Drag left → right to add; drag right → left to remove.

    Constructor args:
        service  -- MonitorService (provides scan_bt_devices())
        loop     -- asyncio event loop (kept for API symmetry)
        remove_card_callback -- Callable[[str], None] called with bt_id on remove
        parent   -- optional parent QWidget
    """

    def __init__(self, service, loop, remove_card_callback=None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._loop = loop
        self._remove_card_callback = remove_card_callback
        self._monitored_ids: set[str] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Devices")
        heading.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(heading)

        panels = QHBoxLayout()
        panels.setSpacing(16)
        panels.addWidget(self._build_available_panel())
        panels.addWidget(self._build_monitored_panel())
        layout.addLayout(panels)

        self._monitored_list.item_dropped.connect(self._on_add_device)
        self._scan_list.item_dropped.connect(self._on_remove_device)

        for entry in load_config().get("monitored_devices", []):
            self._add_monitored_item(entry)

    # ── Panel builders ─────────────────────────────────────────────

    def _build_available_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("devicePanel")
        vl = QVBoxLayout(panel)
        vl.setContentsMargins(16, 16, 16, 16)
        vl.setSpacing(8)

        row = QHBoxLayout()
        title = QLabel("Paired Bluetooth && HID Devices")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #CCCCDD;")
        row.addWidget(title)
        row.addStretch()
        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setFixedWidth(64)
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        row.addWidget(self._scan_btn)
        vl.addLayout(row)

        hint = QLabel("Drag a device → Currently Monitored to track it")
        hint.setStyleSheet("font-size: 11px; color: #555566;")
        vl.addWidget(hint)

        self._scan_list = _DeviceList()
        vl.addWidget(self._scan_list)

        return panel

    def _build_monitored_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("devicePanel")
        vl = QVBoxLayout(panel)
        vl.setContentsMargins(16, 16, 16, 16)
        vl.setSpacing(8)

        title = QLabel("Currently Monitored")
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #CCCCDD;")
        vl.addWidget(title)

        hint = QLabel("Drag a device here to start monitoring")
        hint.setStyleSheet("font-size: 11px; color: #555566;")
        vl.addWidget(hint)

        self._monitored_list = _DeviceList()
        vl.addWidget(self._monitored_list)

        return panel

    # ── Item helpers ──────────────────────────────────────────────

    def _add_scan_item(self, entry: dict) -> None:
        """Add entry to available list, skipping already-monitored devices."""
        if entry.get("id") in self._monitored_ids:
            return
        badge = _battery_badge(entry)
        device_type = entry.get("type", "bt").upper()
        support = "Supported" if badge != "N/A" else "battery N/A"
        label = f"{entry['name']}  ·  {device_type}  ·  {badge} ({support})"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, entry)
        self._scan_list.addItem(item)

    def _add_monitored_item(self, entry: dict) -> None:
        """Add entry to monitored list and register its id."""
        device_type = entry.get("type", "bt").upper()
        label = f"{entry['name']}  ·  {device_type}"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, entry)
        self._monitored_list.addItem(item)
        self._monitored_ids.add(entry["id"])

    # ── Scan ──────────────────────────────────────────────────────

    def _on_scan_clicked(self) -> None:
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("…")
        future = self._service.scan_bt_devices()
        future.add_done_callback(lambda f: None)

    def on_scan_result(self, devices: list) -> None:
        """Called by MainWindow when BtScanResultEvent arrives."""
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("Scan")
        self._scan_list.clear()
        for d in devices:
            self._add_scan_item(d)

    # ── Add / remove ──────────────────────────────────────────────

    def _on_add_device(self, entry: dict) -> None:
        """Item dropped INTO monitored list — start monitoring."""
        entry_id = entry["id"]
        normalized = {
            "id": entry_id,
            "name": entry["name"],
            "type": entry.get("type", "bt"),
            "ble_address": entry.get("ble_address"),
        }
        self._add_monitored_item(normalized)
        cfg = load_config()
        
        # Ensure it is removed from ignored_devices
        ignored = cfg.get("ignored_devices", [])
        if entry_id in ignored:
            ignored = [i for i in ignored if i != entry_id]
            cfg["ignored_devices"] = ignored
            
        monitored = cfg.get("monitored_devices", [])
        if not any(d["id"] == entry_id for d in monitored):
            monitored.append(normalized)
            cfg["monitored_devices"] = monitored
            
        save_config(cfg)
        if self._service is not None:
            if hasattr(self._service, "add_monitored_device"):
                self._service.add_monitored_device(normalized)
            else:
                self._service.add_bt_device(normalized)

    def remove_monitored_device(self, device_id: str) -> None:
        """Remove a device from the monitored list by its ID (called from dashboard ⋮ menu)."""
        self._monitored_ids.discard(device_id)
        for i in range(self._monitored_list.count()):
            item = self._monitored_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole).get("id") == device_id:
                self._monitored_list.takeItem(i)
                break

    def _on_remove_device(self, entry: dict) -> None:
        """Item dropped back INTO available list — stop monitoring."""
        entry_id = entry["id"]
        self._monitored_ids.discard(entry_id)
        self._add_scan_item(entry)
        cfg = load_config()
        
        # If it is a HID device, add to ignored_devices to prevent auto-monitoring on next plug/startup
        if entry.get("type") == "hid":
            ignored = cfg.get("ignored_devices", [])
            if entry_id not in ignored:
                ignored.append(entry_id)
                cfg["ignored_devices"] = ignored
                
        cfg["monitored_devices"] = [e for e in cfg.get("monitored_devices", []) if e["id"] != entry_id]
        if "history" in cfg and entry_id in cfg["history"]:
            del cfg["history"][entry_id]
        save_config(cfg)
        if self._remove_card_callback is not None:
            self._remove_card_callback(entry_id)

    # ── QSS background support ────────────────────────────────────

    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
