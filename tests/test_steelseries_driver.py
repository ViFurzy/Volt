"""Unit tests for steelseries.driver."""

import ast
import pathlib
from unittest.mock import MagicMock, patch

import pytest

from steelseries.driver import find_dongle, open_dongle, ss_battery_probe, SS_VENDOR_INTERFACE


# ---------------------------------------------------------------------------
# find_dongle tests
# ---------------------------------------------------------------------------

def test_find_dongle_filters_interface_3():
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            {"interface_number": 0, "product_id": 0x1852, "path": b"/dev/hid0",
             "usage_page": 0x0001, "vendor_id": 0x1038},
            {"interface_number": 3, "product_id": 0x1852, "path": b"/dev/hid1",
             "usage_page": 0xFFC0, "vendor_id": 0x1038},
        ]
        result = find_dongle()
    assert len(result) == 1
    assert result[0]["interface_number"] == 3


def test_find_dongle_verbose_prints(capsys):
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            {"interface_number": 3, "product_id": 0x1852, "path": b"/dev/hid1",
             "usage_page": 0xFFC0, "vendor_id": 0x1038},
        ]
        find_dongle(verbose=True)
    captured = capsys.readouterr()
    assert captured.out != ""


def test_find_dongle_silent_when_not_verbose(capsys):
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            {"interface_number": 3, "product_id": 0x1852, "path": b"/dev/hid1",
             "usage_page": 0xFFC0, "vendor_id": 0x1038},
        ]
        find_dongle(verbose=False)
    captured = capsys.readouterr()
    assert captured.out == ""


# ---------------------------------------------------------------------------
# open_dongle tests
# ---------------------------------------------------------------------------

def test_open_dongle_calls_open_path():
    with patch("hid.device") as mock_dev_class:
        mock_dev = MagicMock()
        mock_dev_class.return_value = mock_dev
        open_dongle({"path": b"/dev/hid3"})
    mock_dev.open_path.assert_called_once_with(b"/dev/hid3")


# ---------------------------------------------------------------------------
# ss_battery_probe tests
# ---------------------------------------------------------------------------

def test_ss_battery_probe_parses_level_byte(mock_hid):
    # 3 warmup reads (empty), then battery response: raw=5 → percent=20, not charging
    mock_hid.read.side_effect = [[], [], [], [0xD2, 0x05] + [0x00] * 62]
    result = ss_battery_probe(mock_hid, 0x00)
    assert result.percent == 20
    assert result.charging is False
    assert result.voltage_mv == 0
    assert result.feature_used == "0xD2"


def test_ss_battery_probe_charging_flag(mock_hid):
    # level_byte=0x85: bit7=1 (charging), raw=(0x85 & 0x7F)=5, percent=20
    mock_hid.read.side_effect = [[], [], [], [0xD2, 0x85] + [0x00] * 62]
    result = ss_battery_probe(mock_hid, 0x00)
    assert result.percent == 20
    assert result.charging is True


def test_ss_battery_probe_returns_none_on_timeout(mock_hid):
    # All reads empty → no 0xD2 response, returns None
    mock_hid.read.return_value = []
    result = ss_battery_probe(mock_hid, 0x00)
    assert result is None


def test_ss_battery_probe_skips_0x61_packets(mock_hid):
    # 3 warmup empties, then several 0x61 async notification packets, then 0xD2 response
    warmup = [[], [], []]
    skip_packets = [[0x61, 0x00, 0x46, 0x38] + [0x00] * 60] * 3
    response = [[0xD2, 0x05] + [0x00] * 62]
    mock_hid.read.side_effect = warmup + skip_packets + response
    result = ss_battery_probe(mock_hid, 0x00)
    assert result is not None
    assert result.percent == 20


def test_ss_battery_probe_warmup_read_count(mock_hid):
    # Verify exactly 3 reads happen before the first write call
    mock_hid.read.side_effect = [[], [], [], [0xD2, 0x05] + [0x00] * 62]
    ss_battery_probe(mock_hid, 0x00)
    # Find the index of the first write call in mock_calls
    call_names = [str(c) for c in mock_hid.mock_calls]
    read_calls_before_write = 0
    for call in mock_hid.mock_calls:
        call_str = str(call)
        if "write" in call_str:
            break
        if "read" in call_str:
            read_calls_before_write += 1
    assert read_calls_before_write == 3


def test_no_hid_open_direct_call():
    """driver.py must not call hid.open(vid, pid) directly — use open_path()."""
    source = pathlib.Path("src/steelseries/driver.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "open"
                and isinstance(func.value, ast.Name)
                and func.value.id == "hid"
            ):
                pytest.fail(
                    f"Found forbidden hid.open() call at line {node.lineno}"
                )


def test_raw_zero_gives_zero_percent(mock_hid):
    # level_byte=0x01: raw=1, percent=(1-1)*5=0
    mock_hid.read.side_effect = [[], [], [], [0xD2, 0x01] + [0x00] * 62]
    result = ss_battery_probe(mock_hid, 0x00)
    assert result.percent == 0


def test_raw_21_gives_100_percent(mock_hid):
    # level_byte=0x15 (21): raw=21, percent=(21-1)*5=100
    mock_hid.read.side_effect = [[], [], [], [0xD2, 0x15] + [0x00] * 62]
    result = ss_battery_probe(mock_hid, 0x00)
    assert result.percent == 100
