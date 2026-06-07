"""Unit tests for DevicesPage widget.

Strategy:
  - NEVER call widget.show() in headless tests — Qt show() requires a display.
  - Instantiate DevicesPage and call methods directly.
  - pytest-qt's qapp fixture provides the QApplication singleton.
"""
import json
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
        assert page._scan_list is not None

    def test_has_monitored_list(self, qapp):
        from ui.devices_page import DevicesPage
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        assert page._monitored_list is not None


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
        assert "N/A" in page._scan_list.item(1).text()
        assert "HID" in page._scan_list.item(2).text()

    def test_scan_result_skips_already_monitored(self, qapp, monkeypatch):
        """Devices already in monitored_ids are not shown in the scan list."""
        from ui.devices_page import DevicesPage
        monkeypatch.setattr(
            "ui.devices_page.load_config",
            lambda: {"monitored_devices": [{"id": "dev://1", "name": "X", "type": "bt", "ble_address": None}]},
        )
        monkeypatch.setattr("ui.devices_page.save_config", lambda cfg: None)
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        page.on_scan_result([
            {"id": "dev://1", "name": "Stadia", "battery": None, "type": "bt"},
            {"id": "dev://2", "name": "Other", "battery": None, "type": "bt"},
        ])
        assert page._scan_list.count() == 1
        assert "Other" in page._scan_list.item(0).text()


class TestDevicesPageAddRemove:
    def test_add_device_saves_to_config(self, qapp, tmp_path, monkeypatch):
        from ui.devices_page import DevicesPage

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"monitored_devices": []}))

        def _load():
            with open(str(config_file)) as f:
                return json.load(f)

        def _save(cfg):
            with open(str(config_file), "w") as f:
                json.dump(cfg, f)

        monkeypatch.setattr("ui.devices_page.load_config", _load)
        monkeypatch.setattr("ui.devices_page.save_config", _save)

        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        entry = {"id": "dev://1", "name": "Stadia", "battery": 75, "type": "bt", "ble_address": None}
        page._on_add_device(entry)

        cfg = _load()
        assert any(d["id"] == "dev://1" for d in cfg.get("monitored_devices", []))

    def test_add_device_appears_in_monitored_list(self, qapp, monkeypatch):
        from ui.devices_page import DevicesPage
        monkeypatch.setattr("ui.devices_page.load_config", lambda: {"monitored_devices": []})
        monkeypatch.setattr("ui.devices_page.save_config", lambda cfg: None)
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        entry = {"id": "dev://1", "name": "Stadia", "type": "bt", "ble_address": None}
        page._on_add_device(entry)
        assert page._monitored_list.count() == 1
        assert "Stadia" in page._monitored_list.item(0).text()

    def test_remove_device_triggers_callback(self, qapp, monkeypatch):
        from ui.devices_page import DevicesPage
        monkeypatch.setattr("ui.devices_page.load_config", lambda: {"monitored_devices": []})
        monkeypatch.setattr("ui.devices_page.save_config", lambda cfg: None)
        callback = MagicMock()
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=callback)
        entry = {"id": "dev://1", "name": "Stadia", "type": "bt", "ble_address": None}
        page._monitored_ids.add("dev://1")
        page._on_remove_device(entry)
        callback.assert_called_once_with("dev://1")

    def test_remove_device_updates_monitored_ids(self, qapp, monkeypatch):
        from ui.devices_page import DevicesPage
        monkeypatch.setattr("ui.devices_page.load_config", lambda: {"monitored_devices": []})
        monkeypatch.setattr("ui.devices_page.save_config", lambda cfg: None)
        page = DevicesPage(service=MagicMock(), loop=MagicMock(), remove_card_callback=None)
        page._monitored_ids.add("dev://1")
        entry = {"id": "dev://1", "name": "Stadia", "type": "bt", "ble_address": None}
        page._on_remove_device(entry)
        assert "dev://1" not in page._monitored_ids


class TestMainWindowBt:
    def test_remove_card_from_dashboard(self, qapp):
        from ui.main_window import MainWindow
        from monitor.state import BtDeviceInfo, DeviceStatus
        window = MainWindow(service=None, loop=None)
        info = BtDeviceInfo(
            bt_id="dev://1",
            name="Stadia",
            battery=80,
            ble_address=None,
            status=DeviceStatus.ONLINE,
        )
        window.on_bt_device_update(info)
        assert "dev://1" in window._cards
        window.remove_bt_card("dev://1")
        assert len(window._cards) == 0
