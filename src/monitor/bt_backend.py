"""
Bluetooth device battery resolution — three-tier chain.

Tier (a): WinRT OS battery property via DeviceInformation.find_all_async.
Tier (b): BLE GATT Battery Service (UUID 0x180F / char 0x2A19) via bleak.
Tier (c): Existing vendor protocol (HID++) handled by MonitorService for KNOWN_DEVICES.

All functions are async. They run exclusively on the asyncio background thread
via MonitorService — never called directly from the Qt main thread.
"""

import asyncio

from bleak import BleakClient, BleakError
from bleak.exc import BleakCharacteristicNotFoundError
from winrt.windows.devices.bluetooth import BluetoothDevice
from winrt.windows.devices.enumeration import DeviceInformation

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

BATTERY_PKEY = "{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def winrt_enumerate_bt() -> list[dict]:
    """Enumerate all paired Bluetooth devices and return their WinRT OS battery property.

    Uses BluetoothDevice.get_device_selector_from_pairing_state(True) to build an
    AQS selector for paired-only devices (covers both BLE and classic BT).

    Returns a list of dicts with keys: id, name, battery (int or None), type ("bt").
    Returns [] on any WinRT error.
    """
    try:
        aqs = BluetoothDevice.get_device_selector_from_pairing_state(True)
        additional_props = ["System.ItemNameDisplay", BATTERY_PKEY]
        devices = await DeviceInformation.find_all_async(aqs, additional_props)
        results = []
        for d in devices:
            battery_raw = d.properties.get(BATTERY_PKEY)
            # T-07-01: isinstance guard — WinRT property bag may return unexpected types
            battery_pct = int(battery_raw) if isinstance(battery_raw, (int, float)) else None
            results.append({
                "id": d.id,
                "name": d.name,
                "battery": battery_pct,
                "type": "bt",
            })
        return results
    except Exception:
        return []


async def gatt_battery(ble_address: str, timeout: float = 5.0) -> int | None:
    """Read battery level via BLE GATT Battery Service (UUID 0x180F / char 0x2A19).

    Returns 0-100 int, or None if the device does not expose the Battery Service,
    connection fails, or any other error occurs.
    """
    try:
        async with BleakClient(ble_address, timeout=timeout) as client:
            data = await client.read_gatt_char(BATTERY_CHAR_UUID)
            # T-07-02: length-check before int.from_bytes(); guard empty bytes
            return int.from_bytes(data[:1], "little") if data else None
    except BleakCharacteristicNotFoundError:
        return None  # device connected but lacks Battery Service
    except BleakError:
        return None  # connection failed, device not in BLE range, etc.
    except Exception:
        return None  # catch-all: asyncio.TimeoutError, OS error, etc.


async def resolve_battery(device_info: dict) -> int | None:
    """Attempt battery resolution using the three-tier priority chain.

    Tier (a): WinRT OS property — pre-fetched from find_all_async properties.
    Tier (b): BLE GATT Battery Service — for true BLE peripherals.
    Tier (c): Existing HID++ vendor protocol — handled separately by MonitorService
              for KNOWN_DEVICES; this function returns None for that case.

    Returns int 0-100 from the first successful tier, or None if all tiers fail.
    """
    # Tier (a): WinRT OS battery property
    winrt_pct = device_info.get("battery")
    if winrt_pct is not None:
        return winrt_pct

    # Tier (b): BLE GATT Battery Service
    ble_address = device_info.get("ble_address")
    if ble_address:
        gatt_pct = await gatt_battery(ble_address)
        if gatt_pct is not None:
            return gatt_pct

    # Tier (c): not handled here
    return None
