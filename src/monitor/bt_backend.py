"""
Bluetooth device battery resolution — three-tier chain.

Tier (a): WinRT OS battery property via DeviceInformation.find_all_async_aqs_filter_and_additional_properties.
Tier (b): BLE GATT Battery Service (UUID 0x180F / char 0x2A19) via bleak.
Tier (c): Existing vendor protocol (HID++) handled by MonitorService for KNOWN_DEVICES.

All functions are async. They run exclusively on the asyncio background thread
via MonitorService — never called directly from the Qt main thread.

Hardware findings (Plan 07-02, OUTCOME C):
- BATTERY_PKEY returns None on all tested hardware (Sound Blaster FRee, Stadia Z6ZK).
- Tier (a) always falls through to tier (b) GATT for BLE devices.
- pywinrt 3.x uses descriptive method names per overload instead of Python-style
  overloaded dispatch: find_all_async(aqs, props) → find_all_async_aqs_filter_and_additional_properties(aqs, props).
"""

import asyncio
import re

from bleak import BleakClient, BleakError
from bleak.exc import BleakCharacteristicNotFoundError
from winrt.windows.devices.bluetooth import BluetoothDevice, BluetoothLEDevice
from winrt.windows.devices.enumeration import DeviceInformation, DeviceInformationKind

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

BATTERY_PKEY = "{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2"
IS_CONNECTED_PKEY = "System.Devices.Aep.IsConnected"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def is_bluetooth_enabled() -> bool:
    """Check if the Bluetooth radio is turned on."""
    try:
        from winrt.windows.devices import radios
        all_radios = await radios.Radio.get_radios_async()
        for radio in all_radios:
            if radio.kind == radios.RadioKind.BLUETOOTH:
                return radio.state == radios.RadioState.ON
        return False
    except Exception:
        return True


def _get_winrt_prop(properties, key: str):
    """Retrieve and safely cast property values from WinRT properties map.

    Avoids Python truthiness issues with WinRT boolean wrappers and extracts
    primitive types like GUIDs, ints, doubles, and strings correctly.
    """
    from winrt.windows.foundation import IPropertyValue
    raw = properties.get(key)
    if raw is None:
        return None
    if hasattr(raw, "as_"):
        try:
            prop = raw.as_(IPropertyValue)
            if prop.type == 12:  # String
                return prop.get_string()
            elif prop.type == 16:  # Guid
                return str(prop.get_guid())
            elif prop.type == 11:  # Boolean
                return prop.get_boolean()
            elif prop.type in (1, 2, 3, 4, 5, 6, 7, 8):  # Numeric
                return int(prop.get_double() if prop.type in (6, 7, 8) else prop.get_int32())
        except Exception:
            pass
    elif isinstance(raw, (int, float, bool, str)):
        return raw
    return None


async def query_container_battery(container_id: str) -> int | None:
    """Query all physical devices of kind DEVICE under a ContainerId

    to find and return the battery percentage property if exposed.
    """
    aqs = f"System.Devices.ContainerId:=\"{{{container_id}}}\""
    try:
        devices = await DeviceInformation.find_all_async_with_kind_aqs_filter_and_additional_properties(
            aqs, [BATTERY_PKEY], DeviceInformationKind.DEVICE
        )
        for d in devices:
            val = _get_winrt_prop(d.properties, BATTERY_PKEY)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return int(val)
    except Exception:
        pass
    return None


def _extract_ble_address(device_id: str) -> str | None:
    """Extract and format BLE MAC address from a Windows Device ID.

    Supports both standard hyphenated colon formats and raw 12-char hex values.
    """
    # 1. Standard colon-separated format at the end (e.g. BluetoothLE#BluetoothLE<local>-<device>)
    if "BluetoothLE" in device_id and "-" in device_id:
        ble_address = device_id.rsplit("-", 1)[-1].upper()
        if len(ble_address) == 17 and ble_address.count(":") == 5:
            return ble_address

    # 2. Hex pattern (e.g. BTHLEDevice#..._fe19a362121b#...)
    # Preceded by dev_, _, or & and followed by #, _, \, or end of string.
    # Excludes UUID/GUID endings because they are preceded by -
    match = re.search(r'(?i)(?:dev_|[_&])([0-9a-fA-F]{12})(?=[#_\\]|$)', device_id)
    if match:
        hex_str = match.group(1).upper()
        return ":".join(hex_str[i:i+2] for i in range(0, 12, 2))

    return None


async def winrt_enumerate_bt() -> list[dict]:
    """Enumerate paired Bluetooth (classic BT + BLE) devices and their WinRT OS battery property.

    Queries both BluetoothDevice and BluetoothLEDevice AQS selectors to cover
    classic BT and BLE association endpoints. For BLE devices, ble_address is
    extracted from the device id for tier (b) GATT fallback.

    Returns a list of dicts with keys: id, name, battery (int or None), type ("bt"),
    ble_address (str or None), connected (bool). Returns [] on any WinRT error
    or if Bluetooth is disabled.

    pywinrt 3.x note: WinRT overloads use descriptive method suffixes, not Python
    overload dispatch. find_all_async(aqs, props) must be called as
    find_all_async_aqs_filter_and_additional_properties(aqs, props).
    """
    if not await is_bluetooth_enabled():
        return []
    try:
        additional_props = [
            "System.ItemNameDisplay",
            BATTERY_PKEY,
            IS_CONNECTED_PKEY,
            "System.Devices.Aep.ContainerId",
        ]
        results: list[dict] = []
        seen_names: set[str] = set()

        for get_selector_fn in (
            BluetoothDevice.get_device_selector_from_pairing_state,
            BluetoothLEDevice.get_device_selector_from_pairing_state,
        ):
            try:
                aqs = get_selector_fn(True)
                devices = await DeviceInformation.find_all_async_aqs_filter_and_additional_properties(
                    aqs, additional_props
                )
            except Exception:
                continue
            for d in devices:
                if d.name in seen_names:
                    continue
                seen_names.add(d.name)
                
                # Safely extract properties
                container_id = _get_winrt_prop(d.properties, "System.Devices.Aep.ContainerId")
                connected = bool(_get_winrt_prop(d.properties, IS_CONNECTED_PKEY))
                raw_battery = _get_winrt_prop(d.properties, BATTERY_PKEY)
                battery_pct = int(raw_battery) if isinstance(raw_battery, (int, float)) and not isinstance(raw_battery, bool) else None

                if battery_pct is None and container_id:
                    battery_pct = await query_container_battery(container_id)

                # Extract BLE address from id for GATT tier (b).
                ble_address = _extract_ble_address(d.id)
                results.append({
                    "id": d.id,
                    "name": d.name,
                    "battery": battery_pct,
                    "type": "bt",
                    "ble_address": ble_address,
                    "connected": connected,
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
