---
phase: 07-bluetooth-device-discovery
plan: "04"
subsystem: ui/devices_page, ui/main_window, monitor/app, __main__
tags: [bluetooth, ui, devices-page, main-window, wiring, tdd]
dependency_graph:
  requires:
    - 07-03 (BtDeviceInfo, BtScanResultEvent, scan_bt_devices in MonitorService)
  provides:
    - DevicesPage widget (scan, add, remove)
    - MainWindow.on_bt_device_update
    - MainWindow.remove_bt_card
    - MainWindow.on_scan_result
    - MonitorApp.drain() BT routing
  affects:
    - src/ui/devices_page.py
    - src/ui/main_window.py
    - src/monitor/app.py
    - src/__main__.py
    - tests/test_devices_page.py
tech_stack:
  added: []
  patterns:
    - DevicesPage(QWidget) with scan/add/remove and config persistence
    - fire-and-forget scan via service.scan_bt_devices() plain def returning Future
    - MainWindow extended with BT card create/update/remove methods
    - MonitorApp.drain() isinstance-based event routing
    - Back-patching consumer callbacks after window construction
key_files:
  created:
    - src/ui/devices_page.py
    - tests/test_devices_page.py
  modified:
    - src/ui/main_window.py
    - src/monitor/app.py
    - src/__main__.py
decisions:
  - "scan_bt_devices() is a plain def returning Future — DevicesPage calls it directly, no run_coroutine_threadsafe wrapper needed"
  - "_cards dict changed from typed dict[tuple,DeviceCard] to plain dict to support both tuple keys (HID) and str bt_id keys (BT)"
  - "MainWindow constructed after MonitorApp so service/loop are available; consumers back-patched immediately after"
  - "poll_interval set to 60.0 (production value) — was 2.0 in the old placeholder code"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-05"
  tasks_completed: 2
  files_created: 2
  files_modified: 3
---

# Phase 7 Plan 04: Devices Page UI and Wiring Summary

**One-liner:** DevicesPage widget implemented with scan/add/remove; wired into MainWindow at stack index 1 replacing placeholder; MonitorApp.drain() updated to route BtScanResultEvent and BtDeviceInfo to dedicated consumers.

---

## What Was Built

### src/ui/devices_page.py (new)

`DevicesPage(QWidget)` — the Devices tab for BT-03.

Constructor signature: `__init__(self, service, loop, remove_card_callback=None, parent=None)`

Layout:
- Heading "Devices" (20px bold)
- Scan row: label "Paired Bluetooth & HID devices" + "Scan" button (`_scan_btn`)
- `_scan_list` QListWidget (scan results)
- "Add to monitoring" (`_add_btn`) + "Remove" (`_remove_btn`) buttons
- "Currently monitored" heading
- `_monitored_list` QListWidget (pre-populated from config on construction)

Key behaviors:
- `_on_scan_clicked()`: calls `self._service.scan_bt_devices()` directly (plain def returning Future; fire-and-forget)
- `on_scan_result(devices)`: populates `_scan_list` with `name | TYPE | battery%` or `battery unknown`; handles both `type='bt'` and `type='hid'` entries
- `_on_add_clicked()`: persists selected entry to `config['monitored_devices']`; adds to `_monitored_list`
- `_on_remove_clicked()`: removes from config; calls `remove_card_callback(bt_id)` (when set)
- `paintEvent` override for QSS background support

### src/ui/main_window.py (modified)

Four changes:
1. Added imports: `BtDeviceInfo`, `BtScanResultEvent`, `DevicesPage`
2. `__init__` signature: `def __init__(self, service=None, loop=None, parent=None)`
3. Replaced Devices placeholder with `DevicesPage` at stack index 1; History/Profiles remain as placeholders at indices 2/3
4. `_cards` dict type loosened from `dict[tuple,DeviceCard]` to `dict` to support both HID tuple keys and BT string keys
5. Added `on_bt_device_update(info: BtDeviceInfo)` — creates synthetic `DeviceState` adapter (vid=0, pid=0, dev_idx=0) for `DeviceCard`; keyed by `info.bt_id`
6. Added `remove_bt_card(bt_id: str)` — pops from `_cards`, calls `card.setParent(None)`, updates count label
7. Added `on_scan_result(devices: list)` — delegates to `self._devices_page.on_scan_result(devices)`

### src/monitor/app.py (modified)

Two changes:
1. `__init__` signature extended: `bt_consumer=None, scan_consumer=None` kwargs stored as `self._bt_consumer`, `self._scan_consumer`
2. `drain()` updated: isinstance-based routing — `BtScanResultEvent` → `_scan_consumer(event.devices)`, `BtDeviceInfo` → `_bt_consumer(event)`, other (DeviceState) → `_consumer(event)` (existing HID path unchanged)

### src/__main__.py (modified)

Construction order refactored:
1. `MonitorApp` created with placeholder `consumer=lambda s: None`, `bt_consumer=None`, `scan_consumer=None`, `poll_interval=60.0`
2. `MainWindow` created with `service=app_obj.service, loop=app_obj.service._loop`
3. Three consumers back-patched: `_consumer`, `_bt_consumer`, `_scan_consumer`
4. `poll_interval` corrected from 2.0 to 60.0 (production value)

`sys.coinit_flags = 0` remains as line 1 (architecture invariant preserved).

### tests/test_devices_page.py (new)

8 tests across 4 classes:

| Class | Tests |
|-------|-------|
| `TestDevicesPageConstruction` | constructs_without_raising, is_qwidget, has_scan_button, has_scan_results_list |
| `TestDevicesPageScanResults` | on_scan_result_populates_list (BT + HID + battery% + unknown) |
| `TestDevicesPageAddRemove` | add_device_saves_to_config (monkeypatched config), remove_triggers_remove_callback |
| `TestMainWindowBt` | remove_card_from_dashboard (card in _cards after update, removed after remove_bt_card) |

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | 7 failing tests for DevicesPage | dcc9694 | tests/test_devices_page.py |
| 1 (GREEN) | Implement DevicesPage widget | 8f1df8c | src/ui/devices_page.py |
| 2 | Wire DevicesPage, update drain(), update __main__ | d50fbec | src/ui/main_window.py, src/monitor/app.py, src/__main__.py, tests/test_devices_page.py |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _cards dict type annotation incompatible with BT string keys**

- **Found during:** Task 2
- **Issue:** `_cards` was typed as `dict[tuple[int, int, int], DeviceCard]` which would cause a type error when `on_bt_device_update()` uses `info.bt_id` (str) as key
- **Fix:** Changed annotation to `dict` to accept both tuple keys (HID) and str bt_id keys (BT)
- **Files modified:** `src/ui/main_window.py`
- **Commit:** d50fbec

**2. [Rule 1 - Bug] Duplicate window creation in __main__.py**

- **Found during:** Task 2 — after inserting new construction sequence, the old `window = MainWindow()` / `tray = TrayManager(window, qapp)` block remained
- **Issue:** Would create two MainWindow instances; `tray` would be bound to the old one lacking service/loop
- **Fix:** Removed old construction block; placed `TrayManager` creation after the new window construction with service/loop
- **Files modified:** `src/__main__.py`
- **Commit:** d50fbec

---

## TDD Gate Compliance

| Gate | Status |
|------|--------|
| RED commit (test) | dcc9694 — 7 tests, all failing (ModuleNotFoundError: No module named 'ui.devices_page') |
| GREEN commit (feat) | 8f1df8c — 7 tests, all passing; then extended to 8 tests in Task 2 commit |

RED gate verified: all 7 tests fail with ModuleNotFoundError before `devices_page.py` exists.
GREEN gate verified: all 8 tests pass; full suite 174/174.

---

## Threat Mitigations Applied

| Mitigation | File | Description |
|------------|------|-------------|
| T-07-04-01 | src/ui/devices_page.py:__init__ | `entry.get('name', 'Unknown')`, `entry.get('type', 'bt')` — missing keys produce safe defaults |
| T-07-04-01 | src/ui/devices_page.py:_on_scan_clicked | `d.get("type", "bt")`, `d.get("battery")` with None guard |

---

## Known Stubs

None. All UI flows fully implemented and tested.

---

## Self-Check

Files created/modified exist:
- [x] src/ui/devices_page.py — DevicesPage with _scan_btn, _scan_list, _add_btn, _remove_btn, _monitored_list
- [x] tests/test_devices_page.py — 8 tests, all passing
- [x] src/ui/main_window.py — DevicesPage at index 1, on_bt_device_update, remove_bt_card, on_scan_result
- [x] src/monitor/app.py — drain() with BtScanResultEvent/BtDeviceInfo routing
- [x] src/__main__.py — poll_interval=60.0, three consumers back-patched

Commits:
- [x] dcc9694 test(07-04): RED phase — 7 failing tests for DevicesPage widget
- [x] 8f1df8c feat(07-04): implement DevicesPage widget with scan, add, remove
- [x] d50fbec feat(07-04): wire DevicesPage into MainWindow; update MonitorApp.drain() routing

Test results: 174 passed, 0 failed

## Self-Check: PASSED
