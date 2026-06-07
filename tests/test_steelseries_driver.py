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


# ---------------------------------------------------------------------------
# Dynamic Database Scanning and Headset Support Tests
# ---------------------------------------------------------------------------

from drivers.steelseries import SteelSeriesDriver, load_devices_from_db

def test_supported_devices_loads_from_mock_db():
    # Clear cache
    SteelSeriesDriver._cached_supported_devices = None

    with patch("drivers.steelseries.get_steelseries_db_path", return_value="dummy_path.db"), \
         patch("shutil.copy2"), \
         patch("os.path.exists", return_value=True), \
         patch("os.remove"), \
         patch("sqlite3.connect") as mock_connect:

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock rows: (product_id, connected_product_id, full_name, name)
        # 0x10382202 is (0x1038, 0x2202) -> Arctis Nova 7
        mock_cursor.fetchall.return_value = [
            (0x10382202, 0x10382202, "Arctis Nova 7", "Arctis Nova 7"),
        ]

        driver = SteelSeriesDriver()
        devs = driver.supported_devices

        assert (0x1038, 0x2202) in devs
        assert devs[(0x1038, 0x2202)] == "Arctis Nova 7"
        assert (0x1038, 0x1852) in devs # Aerox 5 Wireless baseline is still present


def test_probe_battery_nova_pro_wireless():
    driver = SteelSeriesDriver()
    # Nova Pro Wireless PID is 0x12E0
    handle = {"path": b"/dev/hid1", "product_id": 0x12E0}

    with patch("drivers.steelseries.open_dongle") as mock_open:
        mock_dev = MagicMock()
        mock_open.return_value = mock_dev

        # Warmup reads (3 empty), then response starting with 0xb0 (176)
        # response[6] is battery raw (e.g. 4 -> 50%)
        # response[15] is status (0x02 -> charging)
        response = [176] + [0]*5 + [4] + [0]*8 + [0x02] + [0]*48
        mock_dev.read.side_effect = [[], [], [], response]

        res = driver.probe_battery(handle, 0)
        assert res is not None
        assert res.percent == 50
        assert res.charging is True
        assert res.feature_used == "0x06,0xb0"


def test_probe_battery_nova_5():
    driver = SteelSeriesDriver()
    # Nova 5 PID is 0x2232
    handle = {"path": b"/dev/hid1", "product_id": 0x2232}

    with patch("drivers.steelseries.open_dongle") as mock_open:
        mock_dev = MagicMock()
        mock_open.return_value = mock_dev

        # Warmup reads, response starting with 0xb0 (176)
        # response[1] is status (0x01 -> online/charging? wait, status online is not 0x02. charging is resp[4]==1)
        # response[3] is level (e.g. 75%)
        # response[4] is charging (0x01 -> True)
        response = [176, 0x01, 0, 75, 0x01] + [0]*59
        mock_dev.read.side_effect = [[], [], [], response]

        res = driver.probe_battery(handle, 0)
        assert res is not None
        assert res.percent == 75
        assert res.charging is True
        assert res.feature_used == "0x00,0xb0"


def test_probe_battery_nova_7():
    driver = SteelSeriesDriver()
    # Nova 7 PID is 0x2202
    handle = {"path": b"/dev/hid1", "product_id": 0x2202}

    with patch("drivers.steelseries.open_dongle") as mock_open:
        mock_dev = MagicMock()
        mock_open.return_value = mock_dev

        # Warmup reads, response starting with 0xb0 (176)
        # response[2] is level (e.g. 2 -> 2*25 = 50% for discrete)
        # response[3] is status (e.g. 0x01 -> online, charging=True)
        response = [176, 0, 2, 0x01] + [0]*60
        mock_dev.read.side_effect = [[], [], [], response]

        res = driver.probe_battery(handle, 0)
        assert res is not None
        assert res.percent == 50
        assert res.charging is True
        assert res.feature_used == "0x00,0xb0"


def test_probe_battery_headset_offline():
    driver = SteelSeriesDriver()
    # Nova 7 PID is 0x2202
    handle = {"path": b"/dev/hid1", "product_id": 0x2202}

    with patch("drivers.steelseries.open_dongle") as mock_open:
        mock_dev = MagicMock()
        mock_open.return_value = mock_dev

        # response starting with 0xb0
        # response[3] is status (0x00 -> offline)
        response = [176, 0, 2, 0x00] + [0]*60
        mock_dev.read.side_effect = [[], [], [], response]

        res = driver.probe_battery(handle, 0)
        assert res is None  # Offline returns None

