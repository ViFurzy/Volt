---
plan: 07-05
phase: 07-bluetooth-device-discovery
status: complete
completed: 2026-06-05
---

# Plan 07-05 Summary: Hardware E2E Checkpoint

## Hardware Verification Results

**BT-01 (WinRT battery property):** NOT available on tested hardware. `{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2` returns None for all paired BT devices (Sound Blaster FRee, Stadia Z6ZK). OUTCOME C confirmed — tier (a) always falls through.

**BT-02 (GATT battery):** NOT available on tested hardware. Stadia controller uses Bluetooth Classic HID, not BLE — no GATT Battery Service. Battery shows "battery unknown"; this is the correct behaviour for devices that expose no battery information.

**BT-03 (Devices page scan + add/remove):** VERIFIED after fixes.
- Scan button enumerates connected BT devices by name (Sound Blaster FRee, StadiaZ6ZK-121b).
- Add to monitoring: device appears in "Currently monitored" list and in left sidebar sub-items.
- Remove from monitoring: device removed from list, sidebar entry cleared, service stops polling.

**BT-04 (Config persistence):** VERIFIED. Monitored devices survive app restart. After relaunch, persisted device appears in "Currently monitored" and on Dashboard within ~500ms (one drain cycle).

## Bugs Found and Fixed During Checkpoint

### 1. Sidebar Devices nav index wrong (sidebar.py)
`_NAV_ITEMS` had `("Devices", 0)` — clicking Devices showed Dashboard. Fixed to `("Devices", 1)`.

### 2. Scan showed all paired (not just connected) BT devices
`get_device_selector_from_pairing_state(True)` returns ALL ever-paired devices. Fixed by adding `System.Devices.Aep.IsConnected` to additional_props and filtering out non-connected entries.

### 3. Scan stored all results in `_bt_devices` (unmonitored devices got cards)
`_run_bt_scan()` was populating `_bt_devices` with every scanned BT device. On the next poll, all of them got emitted as BtDeviceInfo and dashboard cards were created for them. Fixed: scan no longer touches `_bt_devices`. Added `add_bt_device()` / `remove_bt_device()` thread-safe methods. `DevicesPage._on_add_clicked()` calls `add_bt_device()`; `remove_bt_card()` calls `remove_bt_device()`.

### 4. HID interfaces appeared as duplicates in scan list
`hid.enumerate()` returns every HID interface (multiple per physical device — Aerox 5 appeared twice, etc.). HID devices are already auto-discovered via the dongle path; removed HID entries from scan entirely.

### 5. Remove didn't clear sidebar sub-item or stop polling
`remove_bt_card()` removed the dashboard card but not the sidebar sub-item (`sidebar.remove_device()`) and did not stop the service from polling (`service.remove_bt_device()`). Both calls added.

### 6. Startup delay before BT device card appeared
`discover()` loaded persisted BT devices into `_bt_devices` but did not emit to `_ui_queue`. The card only appeared after the first poll cycle (~5s due to GATT timeout). Fixed: `discover()` now emits an initial `BtDeviceInfo(battery=None)` immediately; poll fills in battery later.

### 7. Window could be resized to hide dashboard cards
Added `setMinimumSize(760, 520)` to MainWindow. Added `container.setMinimumWidth(504)` to the dashboard scroll container so QScrollArea shows a horizontal scrollbar instead of squashing card widgets.

## Test Results

- 175 tests total: all pass
- No regressions introduced

## Self-Check: PASSED

All must-haves verified:
- ✓ BT-01: WinRT battery not available on hardware — documented
- ✓ BT-02: GATT battery not available for Stadia (Classic BT) — documented
- ✓ BT-03: Scan, add, remove flow verified on hardware
- ✓ BT-04: Config persists across restart, card appears on startup without delay
- ✓ All bugs found during checkpoint fixed; 175 tests green
