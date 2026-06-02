"""Unit tests for hidpp.receiver — device index discovery with mocked hid."""

import pytest
from unittest.mock import MagicMock, patch, call
from hidpp.receiver import discover_device_index


# ---------------------------------------------------------------------------
# discover_device_index tests
# ---------------------------------------------------------------------------

def test_discover_returns_first_responding_index(mock_hid):
    """Returns 0x01 when the first valid response comes from index 0x01."""
    # A valid 20-byte response: report ID 0x10, device_idx 0x01, feature_idx 0x00
    valid_response = [0x10, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00] + [0x00] * 13
    # First read returns the valid response; subsequent reads return [] (timeout)
    mock_hid.read.return_value = valid_response

    result = discover_device_index(mock_hid)

    assert result == 0x01


def test_discover_skips_timeout_indices(mock_hid):
    """Returns None when all indices time out (read returns [])."""
    mock_hid.read.return_value = []

    result = discover_device_index(mock_hid)

    assert result is None


def test_discover_skips_hidpp_error_indices(mock_hid):
    """Skips index 0x01 (HIDppError) and returns 0x02 as the next valid index."""
    # Error response at 0x01: response[2] == 0xFF triggers HIDppError(response[5])
    error_response  = [0x10, 0x01, 0xFF, 0x00, 0x00, 0x05, 0x00] + [0x00] * 13
    # Valid response at 0x02
    valid_response  = [0x10, 0x02, 0x00, 0x01, 0x00, 0x00, 0x00] + [0x00] * 13
    mock_hid.read.side_effect = [error_response, valid_response]

    result = discover_device_index(mock_hid)

    assert result == 0x02


def test_discover_never_uses_0xFF(mock_hid):
    """Verifies that 0xFF is never passed as device_idx in any write call."""
    mock_hid.read.return_value = []

    discover_device_index(mock_hid)

    # build_short_msg puts device_idx at position [1] of the message list
    # device.write() is called with that message as the single positional argument
    for write_call in mock_hid.write.call_args_list:
        msg = write_call[0][0]  # first positional arg
        assert msg[1] != 0xFF, f"device_idx 0xFF found in write call: {msg}"
