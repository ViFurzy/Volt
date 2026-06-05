---
phase: 07-bluetooth-device-discovery
plan: "01"
subsystem: monitor/bt_backend
tags: [bluetooth, ble, winrt, bleak, battery-resolution]
dependency_graph:
  requires: []
  provides:
    - winrt_enumerate_bt
    - gatt_battery
    - resolve_battery
    - BATTERY_PKEY
    - BATTERY_CHAR_UUID
  affects:
    - src/monitor/bt_backend.py
    - tests/test_bt_backend.py
    - requirements.txt
tech_stack:
  added:
    - bleak==3.0.2
    - winrt-Windows.Devices.Enumeration==3.2.1
    - winrt-Windows.Devices.Bluetooth==3.2.1
  patterns:
    - WinRT DeviceInformation.find_all_async with AQS paired-device selector
    - BleakClient async context manager for GATT Battery Service read
    - Three-tier battery resolution chain (WinRT OS property -> GATT -> None)
    - isinstance guard on WinRT property bag before int() conversion (T-07-01)
    - data[:1] slice guard on GATT bytes before int.from_bytes() (T-07-02)
key_files:
  created:
    - src/monitor/bt_backend.py
    - tests/test_bt_backend.py
  modified:
    - requirements.txt
decisions:
  - "BleakClient imported at module level (not inside function body) so mocker.patch at monitor.bt_backend.BleakClient works in tests"
  - "WinRT imports (DeviceInformation, BluetoothDevice) at module level — packages confirmed installed in Task 1"
  - "gatt_battery catches three exception tiers: BleakCharacteristicNotFoundError, BleakError, Exception"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-05"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 7 Plan 01: BT Backend Module Summary

**One-liner:** Bluetooth battery resolution module with WinRT OS property enumeration and BLE GATT fallback via bleak, backed by 9 unit tests.

---

## What Was Built

`src/monitor/bt_backend.py` — the foundation for all Phase 7 BT battery reading. Three async functions:

- `winrt_enumerate_bt()` — calls `DeviceInformation.find_all_async()` with AQS selector for paired BT devices; extracts OS battery property `{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2`; returns `list[dict]` with `id, name, battery, type` keys.
- `gatt_battery(ble_address, timeout)` — connects via `BleakClient` and reads GATT Battery Service characteristic 0x2A19; returns `int | None`.
- `resolve_battery(device_info)` — three-tier chain: WinRT property first, GATT fallback, None if all fail.

`tests/test_bt_backend.py` — 9 unit tests (3 + 3 + 3) covering success paths, None/absent property, non-numeric type guard, BleakCharacteristicNotFoundError, BleakError, and tier short-circuit logic.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Install BLE/WinRT packages and update requirements.txt | 8375132 | requirements.txt |
| 2 (RED) | Failing tests for bt_backend | 4504347 | tests/test_bt_backend.py |
| 2 (GREEN) | Implement bt_backend.py | 6d25b0d | src/monitor/bt_backend.py |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] BleakClient moved from function-local to module-level import**
- **Found during:** Task 2 GREEN phase (test failure)
- **Issue:** Plan specified `bleak` imports inside `gatt_battery()` function body for graceful degradation. However, tests patch `monitor.bt_backend.BleakClient` at module namespace — this fails with `AttributeError: module does not have the attribute 'BleakClient'` when the import is function-local.
- **Fix:** Moved `from bleak import BleakClient, BleakError` and `from bleak.exc import BleakCharacteristicNotFoundError` to module-level imports. Since bleak is installed (confirmed in Task 1), graceful degradation is not needed.
- **Files modified:** `src/monitor/bt_backend.py`
- **Commit:** 6d25b0d

---

## TDD Gate Compliance

| Gate | Status |
|------|--------|
| RED commit (test) | 4504347 - 9 tests, all failing |
| GREEN commit (feat) | 6d25b0d - 9 tests, all passing |

RED gate verified: test collection error on missing module (not a false pass).
GREEN gate verified: all 9 bt_backend tests pass; full suite 161 tests pass.

---

## Known Stubs

None. All three functions are fully implemented and tested. Module-level imports make the code fully operational.

---

## Threat Flags

No new security surface beyond what was documented in the plan's threat model.

| Flag | File | Description |
|------|------|-------------|
| T-07-01 mitigated | src/monitor/bt_backend.py:42 | isinstance(battery_raw, (int, float)) guard before int() on WinRT property bag |
| T-07-02 mitigated | src/monitor/bt_backend.py:69 | data[:1] + `if data` guard before int.from_bytes() on GATT bytes |

---

## Self-Check

Files exist:
- [x] src/monitor/bt_backend.py
- [x] tests/test_bt_backend.py
- [x] requirements.txt (modified)

Commits:
- [x] 8375132 chore(07-01): install packages
- [x] 4504347 test(07-01): RED phase tests
- [x] 6d25b0d feat(07-01): GREEN phase implementation
