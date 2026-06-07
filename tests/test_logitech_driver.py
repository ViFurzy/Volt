from unittest.mock import MagicMock, patch
import pytest

from drivers.logitech import LogitechDriver
from hidpp.features import BatteryResult

def test_logitech_driver_supported_devices():
    driver = LogitechDriver()
    devs = driver.supported_devices
    assert (0x046D, 0x0ABA) in devs  # G Pro X Wireless
    assert (0x046D, 0xC548) in devs  # Logitech Bolt Receiver
    assert (0x046D, 0xC52B) in devs  # Logitech Unifying Receiver


def test_logitech_driver_find_devices():
    driver = LogitechDriver()
    
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            # Bolt receiver interface 2 (usage_page 0xFF00)
            {"product_id": 0xC548, "usage_page": 0xFF00, "interface_number": 2, "path": b"/dev/hid0", "vendor_id": 0x046d},
            # Duplicate Bolt receiver interface 2 path
            {"product_id": 0xC548, "usage_page": 0xFF00, "interface_number": 2, "path": b"/dev/hid0", "vendor_id": 0x046d},
            # Headset interface (usage_page 0xFF43)
            {"product_id": 0x0ABA, "usage_page": 0xFF43, "interface_number": 3, "path": b"/dev/hid1", "vendor_id": 0x046d},
            # Non-matching interface
            {"product_id": 0x0ABA, "usage_page": 0x0001, "interface_number": 0, "path": b"/dev/hid2", "vendor_id": 0x046d},
        ]
        
        found = driver.find_devices()
        assert len(found) == 2
        # Deduplicated by path, matches correct usage_page
        pids = [d["product_id"] for d in found]
        assert 0xC548 in pids
        assert 0x0ABA in pids


def test_probe_battery_receiver_success_1004():
    driver = LogitechDriver()
    # Bolt Receiver is 0xC548 (starts with 0xC5)
    handle = {"path": b"/dev/hid0", "product_id": 0xC548}
    
    with patch("drivers.logitech.send_and_recv") as mock_send_recv:
        # Mock index 1: Root:GetFeature returns feature index 2 for 0x1004
        # GetBatteryStatus on feature index 2 returns battery report: level=80%, charging=1 (recharging)
        # response: [0x10, device_idx, feat_idx, func_idx, level, status, ...]
        mock_send_recv.side_effect = [
            [0x10, 1, 0, 0, 2, 0, 0],  # GetFeature index query for 0x1004 -> index 2
            [0x10, 1, 2, 0, 80, 1, 0], # GetBatteryStatus -> 80% battery, status recharging (1)
        ]
        
        res = driver.probe_battery(handle, 0xFF)
        assert res is not None
        assert res.percent == 80
        assert res.charging is True
        assert res.feature_used == "0x1004"


def test_probe_battery_receiver_fallback_1000():
    driver = LogitechDriver()
    handle = {"path": b"/dev/hid0", "product_id": 0xC548}
    
    with patch("drivers.logitech.send_and_recv") as mock_send_recv:
        # Index 1: 
        # - GetFeature 0x1004 returns None/Error (represented by returning None)
        # - GetFeature 0x1000 returns index 3
        # - GetBatteryStatus on feature index 3 returns level=50%, status=0 (discharging)
        mock_send_recv.side_effect = [
            None,                      # 0x1004 query returns None
            [0x10, 1, 0, 0, 3, 0, 0],  # 0x1000 query returns index 3
            [0x10, 1, 3, 0, 50, 0, 0], # GetBatteryStatus -> 50% battery, status discharging (0)
        ]
        
        res = driver.probe_battery(handle, 0xFF)
        assert res is not None
        assert res.percent == 50
        assert res.charging is False
        assert res.feature_used == "0x1000"


def test_probe_battery_receiver_all_offline():
    driver = LogitechDriver()
    handle = {"path": b"/dev/hid0", "product_id": 0xC548}
    
    with patch("drivers.logitech.send_and_recv", return_value=None):
        # All device channels return None (offline)
        res = driver.probe_battery(handle, 0xFF)
        assert res is not None
        assert res.percent is None  # Connection online but battery level not available
        assert res.charging is False
        assert res.feature_used == "receiver"


def test_probe_battery_non_receiver_fallback():
    driver = LogitechDriver()
    # G Pro X is 0x0ABA
    handle = {"path": b"/dev/hid0", "product_id": 0x0ABA}
    
    with patch("drivers.logitech.battery_probe_chain") as mock_chain:
        mock_chain.return_value = BatteryResult(percent=90, voltage_mv=3900, charging=False, feature_used="0x06/0x0D")
        
        res = driver.probe_battery(handle, 0xFF)
        assert res is not None
        assert res.percent == 90
        mock_chain.assert_called_once_with(handle, 0xFF)
