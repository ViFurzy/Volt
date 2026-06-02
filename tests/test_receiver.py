"""Unit tests for hidpp.receiver."""

from unittest.mock import MagicMock, patch
from hidpp.receiver import find_receiver, open_receiver, discover_device_index, DEVICE_IDX


def test_find_receiver_filters_ff43_only():
    """find_receiver returns only usage_page=0xFF43 interfaces."""
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            {"usage_page": 0xFF00, "product_id": 0xC547, "path": b"/dev/hid0",
             "usage": 0x01, "manufacturer_string": "", "product_string": ""},
            {"usage_page": 0xFF43, "product_id": 0x0ABA, "path": b"/dev/hid1",
             "usage": 0x01, "manufacturer_string": "", "product_string": ""},
            {"usage_page": 0x000C, "product_id": 0x0ABA, "path": b"/dev/hid2",
             "usage": 0x01, "manufacturer_string": "", "product_string": ""},
        ]
        result = find_receiver()
    assert len(result) == 1
    assert result[0]["usage_page"] == 0xFF43


def test_find_receiver_empty_when_no_ff43():
    """find_receiver returns [] when no 0xFF43 interface is present."""
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            {"usage_page": 0xFF00, "product_id": 0xC547, "path": b"/dev/hid0",
             "usage": 0x01, "manufacturer_string": "", "product_string": ""},
        ]
        result = find_receiver()
    assert result == []


def test_open_receiver_calls_open_path():
    """open_receiver calls device.open_path with the info path."""
    with patch("hid.device") as mock_dev_class:
        mock_dev = MagicMock()
        mock_dev_class.return_value = mock_dev
        open_receiver({"path": b"/dev/hidraw0"})
    mock_dev.open_path.assert_called_once_with(b"/dev/hidraw0")


def test_device_idx_constant_is_0xff():
    """DEVICE_IDX module constant is 0xFF."""
    assert DEVICE_IDX == 0xFF


def test_discover_device_index_returns_0xff():
    """discover_device_index returns DEVICE_IDX (0xFF) without any HID I/O."""
    mock_device = MagicMock()
    result = discover_device_index(mock_device)
    assert result == 0xFF
    assert mock_device.write.call_count == 0
