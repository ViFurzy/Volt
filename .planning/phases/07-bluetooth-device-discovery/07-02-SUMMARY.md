---
plan: 07-02
phase: 07-bluetooth-device-discovery
status: complete
completed: 2026-06-05
---

# Plan 07-02 Summary: Hardware BT Probe + bt_backend Fix

## What Was Built

- `scripts/probe_bt_devices.py` — diagnostic script that calls `winrt_enumerate_bt()` and prints device enumeration results including battery PKEY, device-kind fallback, and GATT battery for BLE devices.
- Bug fix in `src/monitor/bt_backend.py`: corrected pywinrt 3.x API call (see Hardware Findings below).
- Updated `tests/test_bt_backend.py`: patches now target the correct method name.

## Hardware Findings

**Devices enumerated:**
- Sound Blaster FRee (classic BT, kind=5 AssociationEndpoint)
- StadiaZ6ZK-121b (BLE, found via BluetoothLEDevice selector)

**PKEY outcome: OUTCOME C** — `{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2` returns `None` for all devices with both default kind and `DeviceInformationKind.DEVICE`. No hardware-side battery reporting via this property on tested devices. Tier (a) always falls through to tier (b) GATT.

## Critical Bug Found and Fixed

**Bug:** `winrt_enumerate_bt()` used `DeviceInformation.find_all_async(aqs, additional_props)` which fails with `TypeError: Invalid parameter count` in pywinrt 3.x. This caused the function to always return `[]` silently (caught by the outer `except Exception`).

**Root cause:** pywinrt 3.x does **not** use Python-style overloaded method dispatch. Each WinRT overload is exposed as a separate method with a descriptive suffix:
- `find_all_async()` — 0-arg overload
- `find_all_async_aqs_filter_and_additional_properties(aqs, props)` — 2-arg overload ← correct

**Fix applied:**
1. Changed call to `find_all_async_aqs_filter_and_additional_properties`
2. Added `BluetoothLEDevice.get_device_selector_from_pairing_state` selector to enumerate BLE devices (previously missing — Stadia was not found at all)
3. BLE address extraction from device id for GATT tier (b) fallback: `BluetoothLE#BluetoothLE<local>-<device>` → `ble_address = <device>` (e.g. `FE:19:A3:62:12:1B`)
4. Added comment in module docstring documenting the pywinrt 3.x naming convention

## Test Results

- 9 tests in `tests/test_bt_backend.py`: all pass
- 161 tests total: all pass
- `winrt_enumerate_bt()` live: returns 2 devices (Sound Blaster FRee, StadiaZ6ZK-121b) correctly

## Key Files

- `scripts/probe_bt_devices.py` — hardware probe script
- `src/monitor/bt_backend.py` — fixed; `find_all_async_aqs_filter_and_additional_properties` + BLE selector
- `tests/test_bt_backend.py` — updated patches

## Self-Check: PASSED

All must-haves verified:
- ✓ Hardware behavior of BATTERY_PKEY documented (OUTCOME C)
- ✓ bt_backend.py corrected (pywinrt method name + BLE selector added)
- ✓ All tests pass
