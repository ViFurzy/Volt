"""
Probe script: validate WinRT BATTERY_PKEY behavior against real paired BT hardware.

Runs winrt_enumerate_bt() and reports:
- Device name, id, battery value, type
- For devices with battery=None and a battery-reporting name, a second lookup
  using DeviceInformationKind.Device
- For BLE devices, a GATT battery read

Used to resolve Open Question 1 from 07-RESEARCH.md before Plan 07-03 wires
bt_backend.py into MonitorService.

Outcomes:
  OUTCOME A — battery is non-None for at least one device (default kind works)
  OUTCOME B — battery is None with default kind but non-None with DeviceInformationKind.Device
  OUTCOME C — battery is None for all devices with both kinds
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import asyncio

# Keywords that suggest a device normally reports battery
_BATTERY_KEYWORDS = ("controller", "headset", "mouse", "keyboard", "headphone", "gamepad")

# Battery PKEY used in bt_backend.py
BATTERY_PKEY = "{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2"


async def _device_kind_lookup(device_id: str) -> object:
    """Second lookup using DeviceInformationKind.Device for a specific device id."""
    from winrt.windows.devices.enumeration import DeviceInformation, DeviceInformationKind

    try:
        # Use the device id as AQS filter (exact match on System.Devices.DeviceInstanceId
        # or just enumerate all Device-kind and match by id)
        all_device_kind = await DeviceInformation.find_all_async(
            "",
            [BATTERY_PKEY],
            DeviceInformationKind.DEVICE,
        )
        for d in all_device_kind:
            if d.id == device_id:
                return d.properties.get(BATTERY_PKEY)
        return None
    except Exception as exc:
        return f"ERROR: {exc}"


async def main() -> None:
    from monitor.bt_backend import winrt_enumerate_bt, gatt_battery, BATTERY_PKEY as _PKEY

    print("=" * 60)
    print("BT Device Probe — Plan 07-02 hardware validation")
    print("=" * 60)
    print()

    devices = await winrt_enumerate_bt()

    if not devices:
        print("(no paired BT devices found — is Bluetooth enabled?)")
        print()
        print("Outcome: OUTCOME C (empty enumeration — cannot determine PKEY behavior)")
        return

    print(f"Found {len(devices)} device(s):\n")

    outcome_a_hit = False
    outcome_b_hit = False

    for dev in devices:
        name = dev.get("name") or "(unnamed)"
        dev_id = dev.get("id", "")
        battery = dev.get("battery")
        dev_type = dev.get("type", "bt")
        ble_address = dev.get("ble_address")

        print(f"Device: {name}")
        print(f"  id:      {dev_id}")
        print(f"  battery: {battery}")
        print(f"  type:    {dev_type}")

        if battery is not None:
            outcome_a_hit = True

        # For devices with battery=None and a battery-reporting name keyword
        if battery is None and any(kw in name.lower() for kw in _BATTERY_KEYWORDS):
            print(f"  (name suggests battery reporting — trying DeviceInformationKind.Device)")
            device_kind_val = await _device_kind_lookup(dev_id)
            print(f"  Device-kind lookup: {device_kind_val}")
            if device_kind_val is not None and not isinstance(device_kind_val, str):
                outcome_b_hit = True

        # For BLE devices, try GATT battery read
        if ble_address:
            print(f"  (BLE address present — trying GATT battery read: {ble_address})")
            gatt_val = await gatt_battery(ble_address)
            print(f"  GATT battery: {gatt_val}")

        print()

    # Determine outcome
    print("-" * 60)
    if outcome_a_hit:
        print("OUTCOME A — PKEY works: battery is non-None with default DeviceInformationKind")
    elif outcome_b_hit:
        print("OUTCOME B — Device-kind needed: battery is None with default kind but non-None with DeviceInformationKind.Device")
    else:
        print("OUTCOME C — PKEY not supported: battery is None for all devices with both kinds")
    print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
