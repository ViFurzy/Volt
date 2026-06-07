"""Tests for G Pro X Wireless battery reading via G-series headset protocol (feature 0x06/0x0D)."""
import pytest
from hidpp.features import battery_probe_chain, BatteryResult, voltage_to_percent
from hidpp.protocol import HIDppError


# ---------------------------------------------------------------------------
# voltage_to_percent tests
# ---------------------------------------------------------------------------

def test_voltage_to_percent_full():
    assert voltage_to_percent(4150) == 100


def test_voltage_to_percent_full_above():
    assert voltage_to_percent(4200) == 100


def test_voltage_to_percent_zero():
    assert voltage_to_percent(3320) == 0


def test_voltage_to_percent_zero_below():
    assert voltage_to_percent(3000) == 0


def test_voltage_to_percent_50pct():
    assert voltage_to_percent(3830) == 50


def test_voltage_to_percent_interpolation():
    # Midpoint of 3320–3670 range → between 0 and 5 percent
    assert 0 < voltage_to_percent(3495) < 10


# ---------------------------------------------------------------------------
# battery_probe_chain tests
# ---------------------------------------------------------------------------

def test_timeout_returns_none(mock_hid):
    mock_hid.read.return_value = []
    result = battery_probe_chain(mock_hid, 0xFF)
    assert result is None


def test_offline_error_returns_none(mock_hid):
    # Device sends HID++ error 0x05 (ERROR_OFFLINE) when headset is off
    mock_hid.read.return_value = [0x10, 0xFF, 0xFF, 0x00, 0x00, 0x05, 0x00] + [0x00] * 13
    result = battery_probe_chain(mock_hid, 0xFF)
    assert result is None


def test_parses_voltage_bytes(mock_hid):
    # [0x11, 0xFF, 0x06, 0x0D, 0x0D, 0xF4, 0x01, ...] → 3572 mV, discharging
    mock_hid.read.return_value = [0x11, 0xFF, 0x06, 0x0D, 0x0D, 0xF4, 0x01] + [0x00] * 13
    result = battery_probe_chain(mock_hid, 0xFF)
    assert result.voltage_mv == 3572
    assert result.percent == voltage_to_percent(3572)
    assert result.charging is False
    assert result.feature_used == "0x06/0x0D"


def test_command_bytes_correct(mock_hid):
    # Supply a valid response so battery_probe_chain completes
    mock_hid.read.return_value = [0x11, 0xFF, 0x06, 0x0D, 0x0F, 0x26, 0x01] + [0x00] * 13
    battery_probe_chain(mock_hid, 0xFF)
    written = mock_hid.write.call_args[0][0]
    assert written == [0x11, 0xFF, 0x06, 0x0D, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]


def test_charging_state_true(mock_hid):
    mock_hid.read.return_value = [0x11, 0xFF, 0x06, 0x0D, 0x0F, 0x26, 0x03] + [0x00] * 13
    result = battery_probe_chain(mock_hid, 0xFF)
    assert result.charging is True


def test_discharging_state_false(mock_hid):
    mock_hid.read.return_value = [0x11, 0xFF, 0x06, 0x0D, 0x0F, 0x26, 0x01] + [0x00] * 13
    result = battery_probe_chain(mock_hid, 0xFF)
    assert result.charging is False
