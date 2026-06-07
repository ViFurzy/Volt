import pytest
from hidpp.protocol import build_short_msg, send_and_recv, HIDppError, ERROR_OFFLINE


def test_build_short_msg_basic(mock_hid):
    """build_short_msg with fn=0, dev=1, feat=0 returns [0x10,0x01,0x00,0x01,0,0,0]."""
    assert build_short_msg(device_idx=0x01, feature_idx=0x00, function=0) == [0x10, 0x01, 0x00, 0x01, 0, 0, 0]


def test_build_short_msg_function_nibble(mock_hid):
    """func_swid byte is (function<<4)|0x01 for function=3."""
    msg = build_short_msg(device_idx=0x01, feature_idx=0x00, function=3)
    assert msg[3] == (3 << 4) | 0x01


def test_build_short_msg_params(mock_hid):
    """params tuple appears at positions [4], [5], [6]."""
    msg = build_short_msg(device_idx=0x01, feature_idx=0x00, function=0, params=(0xAA, 0xBB, 0xCC))
    assert msg[4] == 0xAA
    assert msg[5] == 0xBB
    assert msg[6] == 0xCC


def test_send_and_recv_timeout_returns_none(mock_hid):
    """send_and_recv returns None when device.read returns empty list (timeout)."""
    mock_hid.read.return_value = []
    result = send_and_recv(mock_hid, [0x10, 0x01, 0x00, 0x01, 0, 0, 0])
    assert result is None


def test_send_and_recv_error_raises(mock_hid):
    """send_and_recv raises HIDppError with .code==0x05 when response[2]==0xFF."""
    mock_hid.read.return_value = [0x10, 0x01, 0xFF, 0x00, 0x00, 0x05, 0x00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    with pytest.raises(HIDppError) as exc_info:
        send_and_recv(mock_hid, [0x10, 0x01, 0x00, 0x01, 0, 0, 0])
    assert exc_info.value.code == 0x05


def test_send_and_recv_valid_response(mock_hid):
    """send_and_recv returns the response list unchanged on a normal response."""
    mock_hid.read.return_value = [0x10, 0x01, 0x00, 0x01, 0x03, 0x00, 0x00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    result = send_and_recv(mock_hid, [0x10, 0x01, 0x00, 0x01, 0, 0, 0])
    assert result[4] == 0x03


def test_send_and_recv_oserror_on_write(mock_hid):
    """send_and_recv re-raises OSError from device.write."""
    mock_hid.write.side_effect = OSError("disconnected")
    with pytest.raises(OSError):
        send_and_recv(mock_hid, [0x10, 0x01, 0x00, 0x01, 0, 0, 0])


def test_send_and_recv_short_response_returns_none(mock_hid):
    """send_and_recv returns None when response is shorter than min_len (default 7)."""
    mock_hid.read.return_value = [0x10, 0x01]
    result = send_and_recv(mock_hid, [0x10, 0x01, 0x00, 0x01, 0, 0, 0])
    assert result is None
