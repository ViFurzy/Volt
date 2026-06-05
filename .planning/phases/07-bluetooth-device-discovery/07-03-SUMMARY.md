---
phase: 07-bluetooth-device-discovery
plan: "03"
subsystem: monitor/service, monitor/state, ui/settings_manager
tags: [bluetooth, service, polling, state-model, config]
dependency_graph:
  requires:
    - 07-01 (bt_backend.py — winrt_enumerate_bt, resolve_battery)
    - 07-02 (bt_backend.py fix — ble_address field in returned dicts)
  provides:
    - BtDeviceInfo
    - BtScanResultEvent
    - MonitorService.scan_bt_devices
    - MonitorService._run_bt_scan
    - MonitorService._bt_devices
    - monitored_devices config default
  affects:
    - src/monitor/state.py
    - src/monitor/service.py
    - src/ui/settings_manager.py
    - tests/test_service.py
    - tests/test_ui_settings.py
tech_stack:
  added: []
  patterns:
    - BtDeviceInfo frozen dataclass (same convention as DeviceState)
    - BtScanResultEvent frozen dataclass with list[dict] devices field
    - _bt_devices dict keyed by bt_id str (analogous to _open for HID)
    - scan_bt_devices() thread-safe Future scheduling (mirrors rescan() pattern)
    - _run_bt_scan() coroutine merging WinRT + HID entries into single event
    - BT battery refresh loop in poll_once() using bt_backend.resolve_battery()
    - Persisted device loading from config['monitored_devices'] in discover()
key_files:
  created: []
  modified:
    - src/monitor/state.py
    - src/monitor/service.py
    - src/ui/settings_manager.py
    - tests/test_service.py
    - tests/test_ui_settings.py
decisions:
  - "BtDeviceInfo.status always ONLINE — 'battery unknown' represented by battery=None, not OFFLINE; BT devices may be on but not exposing battery"
  - "poll_once() passes bt_info.battery (WinRT cached value) to resolve_battery() so tier (a) can short-circuit; not hardcoded None"
  - "discover() extends config loading with .get() for all keys (T-07-03-01 mitigation)"
  - "hid.enumerate() path decoded with errors=replace per T-07-03-03"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-05"
  tasks_completed: 2
  files_created: 0
  files_modified: 5
---

# Phase 7 Plan 03: BT Service Integration Summary

**One-liner:** MonitorService extended with BT scan coroutine, _bt_devices dict, and poll_once() refresh loop; BtDeviceInfo/BtScanResultEvent added to state model; monitored_devices config default wired in.

---

## What Was Built

### src/monitor/state.py

Two new frozen dataclasses added after `DeviceState`:

- `BtDeviceInfo` — snapshot of a discovered BT device with fields `bt_id`, `name`, `battery`, `ble_address`, `status`. Used as the per-poll update event put on `_ui_queue`.
- `BtScanResultEvent` — event put on `_ui_queue` when `_run_bt_scan()` completes; `devices` field is a `list[dict]` containing both WinRT BT entries (`type='bt'`) and HID entries (`type='hid'`).

Added `from __future__ import annotations` for forward-ref compatibility.

### src/ui/settings_manager.py

`_DEFAULTS` extended from 3 keys to 5:
- `"cooldown_hours": 4` — already noted as potentially absent in Phase 6 plans; added
- `"monitored_devices": []` — backward-compatible default; existing configs without this key get `[]` from the `{**_DEFAULTS, **data}` merge

### src/monitor/service.py

Four changes:

1. **Imports**: Added `hid`, `monitor.bt_backend as bt_backend`, `BtDeviceInfo`, `BtScanResultEvent`, `load_config`
2. **`__init__`**: Added `self._bt_devices: dict[str, BtDeviceInfo] = {}`
3. **`scan_bt_devices()`** public method — thread-safe entry point for the Devices page scan button; schedules `_run_bt_scan()` on bg loop, returns Future
4. **`_run_bt_scan()`** coroutine — runs `winrt_enumerate_bt()` and `hid.enumerate()`, stores `BtDeviceInfo` entries in `_bt_devices`, puts `BtScanResultEvent` on `_ui_queue`
5. **`discover()`** extension — after SteelSeries block, reads `load_config()["monitored_devices"]` and pre-populates `_bt_devices` with config-persisted devices (idempotent — skips already-tracked bt_ids)
6. **`poll_once()`** extension — BT refresh loop iterates `_bt_devices`, calls `bt_backend.resolve_battery()` with `battery=bt_info.battery` (WinRT cached) and `ble_address=bt_info.ble_address`, puts updated `BtDeviceInfo` on queue

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add BtDeviceInfo, BtScanResultEvent, extend settings defaults | 3505f14 | src/monitor/state.py, src/ui/settings_manager.py, tests/test_ui_settings.py |
| 2 (RED) | 5 failing tests for BT device tracking | 4b82e78 | tests/test_service.py |
| 2 (GREEN) | Implement BT scan, polling, config loading in MonitorService | fb20cbc | src/monitor/service.py |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_ui_settings.py tests hardcoded against old _DEFAULTS**

- **Found during:** Task 1 — 3 tests failed after extending _DEFAULTS
- **Issue:** `test_load_config_returns_defaults_when_file_absent`, `test_load_config_returns_defaults_on_malformed_json`, and `test_save_and_load_config_roundtrip` compared `load_config()` return value against the old 3-key dict, missing `cooldown_hours` and `monitored_devices`
- **Fix:** Updated all 3 test assertions to include the new default keys
- **Files modified:** `tests/test_ui_settings.py`
- **Commit:** 3505f14

---

## TDD Gate Compliance

| Gate | Status |
|------|--------|
| RED commit (test) | 4b82e78 — 5 tests, all failing (AttributeError on missing bt_backend/hid/load_config attributes) |
| GREEN commit (feat) | fb20cbc — 5 tests, all passing; full suite 166 tests pass |

RED gate verified: tests fail with AttributeError because service.py lacked bt_backend, hid, and load_config imports.
GREEN gate verified: all 5 new tests pass; full suite 166/166.

---

## Known Stubs

None. All functions fully implemented and tested.

---

## Threat Flags

Threat mitigations applied per plan threat model:

| Mitigation | File | Description |
|------------|------|-------------|
| T-07-03-01 | src/monitor/service.py:discover() | .get() with defaults for all config entry keys (id, name, ble_address) |
| T-07-03-03 | src/monitor/service.py:_run_bt_scan() | hid path decoded with errors="replace"; product_string empty-check before use |

---

## Self-Check

Files modified exist:
- [x] src/monitor/state.py — BtDeviceInfo, BtScanResultEvent present
- [x] src/ui/settings_manager.py — monitored_devices in _DEFAULTS
- [x] src/monitor/service.py — scan_bt_devices(), _run_bt_scan(), _bt_devices, BT poll loop
- [x] tests/test_service.py — TestBtDevices class with 5 tests
- [x] tests/test_ui_settings.py — updated assertions for new defaults

Commits:
- [x] 3505f14 feat(07-03): add BtDeviceInfo, BtScanResultEvent to state.py; extend settings_manager defaults
- [x] 4b82e78 test(07-03): RED phase — 5 failing tests for BT device tracking in MonitorService
- [x] fb20cbc feat(07-03): extend MonitorService with BT scan, polling, and config-persisted devices

Test results: 166 passed, 0 failed

## Self-Check: PASSED
