from unittest.mock import MagicMock, patch
import pytest

from drivers.generic import GenericDriver
from drivers import get_driver_for_device, get_known_devices
from hidpp.features import BatteryResult

def test_generic_driver_supported_devices():
    driver = GenericDriver()
    devs = driver.supported_devices
    assert (0x258A, 0x0150) in devs  # RoyalKludge/SinoWealth Gaming KB

def test_generic_driver_dev_idx():
    driver = GenericDriver()
    assert driver.dev_idx == 0x00

def test_generic_driver_probe_battery():
    driver = GenericDriver()
    res = driver.probe_battery(None, 0)
    assert isinstance(res, BatteryResult)
    assert res.percent is None
    assert res.voltage_mv == 0
    assert res.charging is False
    assert res.feature_used == "generic"

def test_generic_driver_find_devices():
    driver = GenericDriver()
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            {"product_id": 0x0150, "vendor_id": 0x258A, "interface_number": 0, "path": b"/dev/hid0"},
            {"product_id": 0x0150, "vendor_id": 0x258A, "interface_number": 1, "path": b"/dev/hid0"},  # duplicate path/device
        ]
        
        found = driver.find_devices()
        assert len(found) == 1
        assert found[0]["product_id"] == 0x0150
        assert found[0]["vendor_id"] == 0x258A

def test_get_driver_for_device_fallbacks():
    # Known exact match
    drv = get_driver_for_device(0x046D, 0x0ABA)
    assert drv.__class__.__name__ == "LogitechDriver"

    # Fallback by VID
    drv_logi = get_driver_for_device(0x046D, 0xDEAD)
    assert drv_logi.__class__.__name__ == "LogitechDriver"

    drv_ss = get_driver_for_device(0x1038, 0xDEAD)
    assert drv_ss.__class__.__name__ == "SteelSeriesDriver"

    drv_rk = get_driver_for_device(0x258A, 0xDEAD)
    assert drv_rk.__class__.__name__ == "GenericDriver"

    # Default fallback
    drv_def = get_driver_for_device(0x9999, 0x9999)
    assert drv_def.__class__.__name__ == "GenericDriver"

def test_get_known_devices_monitored_addition(monkeypatch):
    monkeypatch.setattr(
        "ui.settings_manager.load_config",
        lambda: {
            "monitored_devices": [
                {"id": "hid:9999:8888", "name": "Monitored Custom", "type": "hid"}
            ],
            "custom_hid_devices": []
        }
    )
    devs = get_known_devices()
    assert (0x9999, 0x8888) in devs
    assert devs[(0x9999, 0x8888)] == "Monitored Custom"
