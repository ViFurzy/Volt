"""Unit tests for DevicesPage widget.

Strategy:
  - NEVER call widget.show() in headless tests — Qt show() requires a display.
  - Instantiate DevicesPage and call methods directly.
  - pytest-qt's qapp fixture provides the QApplication singleton.
"""
import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QWidget, QListWidgetItem
from PySide6.QtCore import Qt


class TestDevicesPageConstruction:
    def test_constructs_without_raising(self, qapp):
        from ui.devices_page import DevicesPage
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        assert page is not None

    def test_is_qwidget(self, qapp):
        from ui.devices_page import DevicesPage
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        assert isinstance(page, QWidget)

    def test_has_scan_button(self, qapp):
        from ui.devices_page import DevicesPage
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        assert page._scan_btn is not None

    def test_has_scan_results_list(self, qapp):
        from ui.devices_page import DevicesPage
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        assert page._scan_list is not None  # QListWidget


class TestDevicesPageScanResults:
    def test_on_scan_result_populates_list(self, qapp):
        from ui.devices_page import DevicesPage
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        devices = [
            {"id": "dev://1", "name": "Stadia Controller", "battery": 82, "type": "bt"},
            {"id": "dev://2", "name": "SoundCore", "battery": None, "type": "bt"},
            {"id": "hid://3", "name": "G502 X Plus", "battery": None, "type": "hid"},
        ]
        page.on_scan_result(devices)
        assert page._scan_list.count() == 3
        assert "Stadia Controller" in page._scan_list.item(0).text()
        assert "82%" in page._scan_list.item(0).text()
        assert "unknown" in page._scan_list.item(1).text().lower()
        assert "HID" in page._scan_list.item(2).text()


class TestDevicesPageAddRemove:
    def test_add_device_saves_to_config(self, qapp, tmp_path, monkeypatch):
        from ui.devices_page import DevicesPage
        from ui.settings_manager import load_config, save_config

        # Use a temporary config file
        import json
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"monitored_devices": []}))

        # Monkeypatch load_config and save_config to use tmp file
        def _load():
            with open(str(config_file)) as f:
                return json.load(f)

        def _save(cfg):
            with open(str(config_file), "w") as f:
                json.dump(cfg, f)

        monkeypatch.setattr("ui.devices_page.load_config", _load)
        monkeypatch.setattr("ui.devices_page.save_config", _save)

        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        page.on_scan_result([{"id": "dev://1", "name": "Stadia", "battery": 75, "type": "bt", "ble_address": None}])
        page._scan_list.setCurrentRow(0)
        page._on_add_clicked()

        cfg = _load()
        monitored = cfg.get("monitored_devices", [])
        assert any(d["id"] == "dev://1" for d in monitored)

    def test_remove_triggers_remove_callback(self, qapp):
        from ui.devices_page import DevicesPage
        callback = MagicMock()
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=callback)

        # Pre-populate monitored list with one entry
        entry = {"id": "dev://1", "name": "Stadia", "type": "bt", "ble_address": None}
        item = QListWidgetItem("Stadia  |  BT")
        item.setData(Qt.ItemDataRole.UserRole, entry)
        page._monitored_list.addItem(item)
        page._monitored_list.setCurrentRow(0)
        page._on_remove_clicked()
        callback.assert_called_once_with("dev://1")
