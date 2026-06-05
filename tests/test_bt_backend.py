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
        """Device with IS_CONNECTED_PKEY=False is excluded from results."""
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

        assert result == []


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
