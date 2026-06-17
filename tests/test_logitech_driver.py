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
    
    def mock_send_recv_side_effect(device, msg, *args, **kwargs):
        device_idx = msg[1]
        if device_idx == 1:
            if msg[2] == 0x00:  # GetFeature index query
                feature_id = (msg[4] << 8) | msg[5]
                if feature_id == 0x1004:
                    return [0x10, 1, 0, 0, 2, 0, 0]  # feature index 2
            elif msg[2] == 2:  # GetBatteryStatus on feature index 2
                return [0x10, 1, 2, 0, 80, 1, 0]
        return None

    with patch("drivers.logitech.send_and_recv", side_effect=mock_send_recv_side_effect):
        res = driver.probe_battery(handle, 0xFF)
        assert res is not None
        assert isinstance(res, dict)
        assert 1 in res
        assert res[1].percent == 80
        assert res[1].charging is True
        assert res[1].feature_used == "0x1004"


def test_probe_battery_receiver_fallback_1000():
    driver = LogitechDriver()
    handle = {"path": b"/dev/hid0", "product_id": 0xC548}
    
    def mock_send_recv_side_effect(device, msg, *args, **kwargs):
        device_idx = msg[1]
        if device_idx == 1:
            if msg[2] == 0x00:
                feature_id = (msg[4] << 8) | msg[5]
                if feature_id == 0x1000:
                    return [0x10, 1, 0, 0, 3, 0, 0]  # feature index 3
            elif msg[2] == 3:
                return [0x10, 1, 3, 0, 50, 0, 0]
        return None

    with patch("drivers.logitech.send_and_recv", side_effect=mock_send_recv_side_effect):
        res = driver.probe_battery(handle, 0xFF)
        assert res is not None
        assert isinstance(res, dict)
        assert 1 in res
        assert res[1].percent == 50
        assert res[1].charging is False
        assert res[1].feature_used == "0x1000"


def test_probe_battery_receiver_all_offline():
    driver = LogitechDriver()
    handle = {"path": b"/dev/hid0", "product_id": 0xC548}
    
    with patch("drivers.logitech.send_and_recv", return_value=None):
        # All device channels return None (offline)
        res = driver.probe_battery(handle, 0xFF)
        assert res is not None
        assert isinstance(res, dict)
        assert 0xFF in res
        assert res[0xFF].percent is None  # Connection online but battery level not available
        assert res[0xFF].charging is False
        assert res[0xFF].feature_used == "receiver"


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
