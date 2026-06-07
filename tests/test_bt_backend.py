"""Unit tests for monitor.bt_backend.

All async functions tested via asyncio.run() with mocked WinRT and bleak.
No hardware required. WinRT DeviceInformation and BleakClient patched at
the bt_backend module namespace.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import monitor.bt_backend as bt_backend
from monitor.bt_backend import (
    BATTERY_CHAR_UUID,
    BATTERY_PKEY,
    IS_CONNECTED_PKEY,
    gatt_battery,
    resolve_battery,
    winrt_enumerate_bt,
)


# ---------------------------------------------------------------------------
# TestWinrtEnumerate
# ---------------------------------------------------------------------------

class TestWinrtEnumerate:
    def test_returns_list_of_dicts(self, mocker):
        """Battery property present as int — returned verbatim."""
        mock_device = MagicMock()
        mock_device.id = "dev://1"
        mock_device.name = "Test Device"
        mock_device.properties = {BATTERY_PKEY: 75, IS_CONNECTED_PKEY: True}

        # pywinrt 3.x uses descriptive method name per overload (Plan 07-02 finding)
        mock_find = AsyncMock(return_value=[mock_device])
        mocker.patch(
            "monitor.bt_backend.DeviceInformation.find_all_async_aqs_filter_and_additional_properties",
            mock_find,
        )

        result = asyncio.run(winrt_enumerate_bt())

        assert len(result) == 1
        assert result[0]["id"] == "dev://1"
        assert result[0]["name"] == "Test Device"
        assert result[0]["battery"] == 75
        assert result[0]["type"] == "bt"
        assert result[0]["ble_address"] is None  # "dev://1" has no BluetoothLE in id

    def test_battery_property_none_when_absent(self, mocker):
        """Battery property returns None — dict entry is None."""
        mock_device = MagicMock()
        mock_device.id = "dev://2"
        mock_device.name = "No Battery Device"
        mock_device.properties = {BATTERY_PKEY: None, IS_CONNECTED_PKEY: True}

        mock_find = AsyncMock(return_value=[mock_device])
        mocker.patch(
            "monitor.bt_backend.DeviceInformation.find_all_async_aqs_filter_and_additional_properties",
            mock_find,
        )

        result = asyncio.run(winrt_enumerate_bt())

        assert result[0]["battery"] is None

    def test_battery_property_non_numeric_type_guarded(self, mocker):
        """Battery property is a non-numeric string — isinstance guard returns None."""
        mock_device = MagicMock()
        mock_device.id = "dev://3"
        mock_device.name = "Bad Battery Device"
        mock_device.properties = {BATTERY_PKEY: "not-a-number", IS_CONNECTED_PKEY: True}

        mock_find = AsyncMock(return_value=[mock_device])
        mocker.patch(
            "monitor.bt_backend.DeviceInformation.find_all_async_aqs_filter_and_additional_properties",
            mock_find,
        )

        result = asyncio.run(winrt_enumerate_bt())

        assert result[0]["battery"] is None

    def test_disconnected_device_filtered(self, mocker):
        """Device with IS_CONNECTED_PKEY=False is included in results with connected=False."""
        mock_device = MagicMock()
        mock_device.id = "dev://off"
        mock_device.name = "Offline Device"
        mock_device.properties = {BATTERY_PKEY: None, IS_CONNECTED_PKEY: False}

        mock_find = AsyncMock(return_value=[mock_device])
        mocker.patch(
            "monitor.bt_backend.DeviceInformation.find_all_async_aqs_filter_and_additional_properties",
            mock_find,
        )

        result = asyncio.run(winrt_enumerate_bt())

        assert len(result) == 1
        assert result[0]["id"] == "dev://off"
        assert result[0]["name"] == "Offline Device"
        assert result[0]["battery"] is None
        assert result[0]["connected"] is False


# ---------------------------------------------------------------------------
# TestGattBattery
# ---------------------------------------------------------------------------

class TestGattBattery:
    def test_success_returns_int(self, mocker):
        """GATT read returns b'\\x4b' (75) — result is int 75."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.read_gatt_char = AsyncMock(return_value=b"\x4b")

        mock_bleak_cls = MagicMock(return_value=mock_client)
        mocker.patch("monitor.bt_backend.BleakClient", mock_bleak_cls)

        result = asyncio.run(gatt_battery("AA:BB:CC:DD:EE:FF"))

        assert result == 75

    def test_no_service_returns_none(self, mocker):
        """read_gatt_char raises BleakCharacteristicNotFoundError — result is None."""
        from bleak.exc import BleakCharacteristicNotFoundError

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.read_gatt_char = AsyncMock(side_effect=BleakCharacteristicNotFoundError("no char"))

        mock_bleak_cls = MagicMock(return_value=mock_client)
        mocker.patch("monitor.bt_backend.BleakClient", mock_bleak_cls)

        result = asyncio.run(gatt_battery("AA:BB:CC:DD:EE:FF"))

        assert result is None

    def test_bleak_error_returns_none(self, mocker):
        """BleakError raised on context manager enter — result is None."""
        from bleak import BleakError

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(side_effect=BleakError("connect failed"))
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_bleak_cls = MagicMock(return_value=mock_client)
        mocker.patch("monitor.bt_backend.BleakClient", mock_bleak_cls)

        result = asyncio.run(gatt_battery("AA:BB:CC:DD:EE:FF"))

        assert result is None


# ---------------------------------------------------------------------------
# TestResolveBattery
# ---------------------------------------------------------------------------

class TestResolveBattery:
    def test_winrt_path_short_circuits(self, mocker):
        """WinRT battery property present — gatt_battery is never called."""
        mock_gatt = mocker.patch("monitor.bt_backend.gatt_battery", new_callable=AsyncMock)

        device_info = {"battery": 80, "ble_address": "AA:BB"}
        result = asyncio.run(resolve_battery(device_info))

        assert result == 80
        mock_gatt.assert_not_called()

    def test_fallthrough_to_gatt_when_winrt_none(self, mocker):
        """WinRT battery is None — falls through to gatt_battery which returns 55."""
        mocker.patch("monitor.bt_backend.gatt_battery", new_callable=AsyncMock, return_value=55)

        device_info = {"battery": None, "ble_address": "AA:BB:CC:DD:EE:FF"}
        result = asyncio.run(resolve_battery(device_info))

        assert result == 55

    def test_returns_none_when_all_tiers_fail(self, mocker):
        """WinRT battery is None, ble_address is None — result is None."""
        device_info = {"battery": None, "ble_address": None}
        result = asyncio.run(resolve_battery(device_info))

        assert result is None


# ---------------------------------------------------------------------------
# TestExtractBleAddress
# ---------------------------------------------------------------------------

class TestExtractBleAddress:
    def test_extract_standard_colon_separated(self):
        device_id = "BluetoothLE#BluetoothLE00:1a:7d:da:71:15-fe:19:a3:62:12:1b"
        assert bt_backend._extract_ble_address(device_id) == "FE:19:A3:62:12:1B"

    def test_extract_bthle_dev_hex(self):
        device_id = "\\\\?\\BTHLE#Dev_fe19a362121b#d&307530c6&0&fe19a362121b#{80795c47-03f0-446d-b1f2-e424b30db4da}"
        assert bt_backend._extract_ble_address(device_id) == "FE:19:A3:62:12:1B"

    def test_extract_bthledevice_hex(self):
        device_id = "\\\\?\\BTHLEDevice#{00001800-0000-1000-8000-00805f9b34fb}_Dev_VID&0218d1_PID&9400_REV&0100_fe19a362121b#c&2acd8c43&2&0014"
        assert bt_backend._extract_ble_address(device_id) == "FE:19:A3:62:12:1B"

    def test_excludes_uuid_suffix(self):
        # The Sig base UUID has suffix 00805f9b34fb. It is preceded by a hyphen.
        # It should not match.
        device_id = "USB\\VID_18D1&PID_9400&MI_00#b&268a397e&0&0000#{00001801-0000-1000-8000-00805f9b34fb}"
        assert bt_backend._extract_ble_address(device_id) is None

    def test_non_ble_id_returns_none(self):
        device_id = "USB\\VID_18D1&PID_9400#9A070YCAC2LZYT#{a5dcbf10-6530-11d2-901f-00c04fb951ed}"
        assert bt_backend._extract_ble_address(device_id) is None


# ---------------------------------------------------------------------------
# TestGetWinrtProp
# ---------------------------------------------------------------------------

class TestGetWinrtProp:
    def test_primitives_returned_verbatim(self):
        props = {"key1": 42, "key2": 3.14, "key3": True, "key4": "hello"}
        assert bt_backend._get_winrt_prop(props, "key1") == 42
        assert bt_backend._get_winrt_prop(props, "key2") == 3.14
        assert bt_backend._get_winrt_prop(props, "key3") is True
        assert bt_backend._get_winrt_prop(props, "key4") == "hello"
        assert bt_backend._get_winrt_prop(props, "missing") is None

    def test_winrt_object_casting(self, mocker):
        mock_val = MagicMock()
        mock_val.as_ = MagicMock()
        
        # Test string
        mock_prop_str = MagicMock()
        mock_prop_str.type = 12
        mock_prop_str.get_string = MagicMock(return_value="winrt_str")
        mock_val.as_.return_value = mock_prop_str
        assert bt_backend._get_winrt_prop({"key": mock_val}, "key") == "winrt_str"

        # Test Guid
        mock_prop_guid = MagicMock()
        mock_prop_guid.type = 16
        mock_prop_guid.get_guid = MagicMock(return_value="guid_val")
        mock_val.as_.return_value = mock_prop_guid
        assert bt_backend._get_winrt_prop({"key": mock_val}, "key") == "guid_val"

        # Test Boolean
        mock_prop_bool = MagicMock()
        mock_prop_bool.type = 11
        mock_prop_bool.get_boolean = MagicMock(return_value=True)
        mock_val.as_.return_value = mock_prop_bool
        assert bt_backend._get_winrt_prop({"key": mock_val}, "key") is True


# ---------------------------------------------------------------------------
# TestQueryContainerBattery
# ---------------------------------------------------------------------------

class TestQueryContainerBattery:
    def test_query_success(self, mocker):
        mock_device = MagicMock()
        mock_device.properties = {BATTERY_PKEY: 85}
        
        mock_find = AsyncMock(return_value=[mock_device])
        mocker.patch(
            "monitor.bt_backend.DeviceInformation.find_all_async_with_kind_aqs_filter_and_additional_properties",
            mock_find,
        )
        
        res = asyncio.run(bt_backend.query_container_battery("some-uuid"))
        assert res == 85
        
    def test_query_no_devices(self, mocker):
        mock_find = AsyncMock(return_value=[])
        mocker.patch(
            "monitor.bt_backend.DeviceInformation.find_all_async_with_kind_aqs_filter_and_additional_properties",
            mock_find,
        )
        
        res = asyncio.run(bt_backend.query_container_battery("some-uuid"))
        assert res is None


