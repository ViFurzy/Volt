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


def _probe_receiver(feature_id: int, feat_idx: int, function: int, reply: list[int]):
    """Probe device channel 1 behind a Bolt receiver.

    The device only answers `function` on its battery feature; any other function
    (e.g. 0x1004 GetCapabilities = 0x00) gets no reply, like a wrong call would.
    """
    driver = LogitechDriver()
    handle = {"path": b"/dev/hid0", "product_id": 0xC548}  # Bolt receiver

    def send_recv(device, msg, *args, **kwargs):
        if msg[1] != 1:
            return None
        if msg[2] == 0x00:  # Root.GetFeature
            if (msg[4] << 8) | msg[5] == feature_id:
                return [0x10, 1, 0, 0, feat_idx, 0, 0]
        elif msg[2] == feat_idx and msg[3] == function:
            return reply
        return None

    with patch("drivers.logitech.send_and_recv", side_effect=send_recv):
        return driver.probe_battery(handle, 0xFF)


def test_probe_battery_receiver_success_1004():
    # GetStatus = function 1 (0x10); params: 80%, level "good", status 1 = charging
    res = _probe_receiver(0x1004, 2, 0x10, [0x10, 1, 2, 0x10, 80, 0x04, 0x01])
    assert isinstance(res, dict)
    assert res[1].percent == 80
    assert res[1].charging is True
    assert res[1].feature_used == "0x1004"


def test_probe_battery_1004_level_byte_is_not_charging():
    # Status (resp[6]) 0 = discharging, even though the level byte (resp[5]) is non-zero
    res = _probe_receiver(0x1004, 2, 0x10, [0x10, 1, 2, 0x10, 80, 0x04, 0x00])
    assert res[1].percent == 80
    assert res[1].charging is False


def test_probe_battery_1004_without_state_of_charge_uses_level():
    # Device reports only the level bitmask (0x02 = low) and 0% state of charge
    res = _probe_receiver(0x1004, 2, 0x10, [0x10, 1, 2, 0x10, 0, 0x02, 0x00])
    assert res[1].percent == 20


def test_probe_battery_receiver_fallback_1000():
    # GetBatteryLevelStatus = function 0; params: 50%, next level 20%, status 0
    res = _probe_receiver(0x1000, 3, 0x00, [0x10, 1, 3, 0x00, 50, 20, 0x00])
    assert isinstance(res, dict)
    assert res[1].percent == 50
    assert res[1].charging is False
    assert res[1].feature_used == "0x1000"


def test_probe_battery_1000_charging_status_is_resp6():
    res = _probe_receiver(0x1000, 3, 0x00, [0x10, 1, 3, 0x00, 50, 0, 0x01])
    assert res[1].charging is True


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
