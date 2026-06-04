---
phase: 06-notifications
plan: 02
subsystem: notifications
tags: [wiring, notifications, settings, main]
dependency_graph:
  requires: [06-01]
  provides: [NOTIF-01-wired, NOTIF-02-wired]
  affects: [src/__main__.py, src/ui/settings_manager.py, tests/test_ui_settings.py]
tech_stack:
  added: []
  patterns: [lambda consumer wiring, _on_device_update helper, _DEFAULTS extension]
key_files:
  created: []
  modified:
    - src/__main__.py
    - src/ui/settings_manager.py
    - tests/test_ui_settings.py
decisions:
  - _DEFAULTS extended with "thresholds": {} so load_config() never raises KeyError on thresholds access
  - _on_device_update module-level helper decouples window update from notification check
  - MonitorApp consumer replaced with lambda routing through _on_device_update
  - sys.coinit_flags = 0 invariant preserved as line 2 of __main__.py
metrics:
  duration_minutes: 8
  completed_date: 2026-06-04
  tasks_completed: 2
  files_modified: 3
---

# Phase 06 Plan 02: Wire NotificationManager Summary

**One-liner:** NotificationManager wired into MonitorApp queue drain via _on_device_update helper; settings_manager _DEFAULTS extended with thresholds key.

## What Was Built

`src/__main__.py` — three surgical changes:
- Added imports: `from monitor.state import DeviceState`, `from ui.notification_manager import NotificationManager`, `from ui.settings_manager import load_config`
- Added module-level `_on_device_update(window, notif_manager, state)` helper that calls `window.on_device_update(state)` then `notif_manager.check(state, load_config())`
- Replaced `MonitorApp(consumer=window.on_device_update, ...)` with `notif_manager = NotificationManager()` + `MonitorApp(consumer=lambda s: _on_device_update(window, notif_manager, s), ...)`
- Architecture invariant preserved: `sys.coinit_flags = 0` remains on line 2

`src/ui/settings_manager.py` — single-line change:
- `_DEFAULTS` extended from `{"launch_at_startup": False}` to `{"launch_at_startup": False, "thresholds": {}}` so `load_config()` always returns a `thresholds` key regardless of config file state

`tests/test_ui_settings.py` — three assertion updates:
- `test_load_config_returns_defaults_when_file_absent`: updated expected dict to include `"thresholds": {}`
- `test_load_config_returns_defaults_on_malformed_json`: updated expected dict to include `"thresholds": {}`
- `test_save_and_load_config_roundtrip`: updated expected dict to include `"thresholds": {}`

## Deviations from Plan

**1. [Rule 1 - Bug] test_save_and_load_config_roundtrip also broke on _DEFAULTS change**

- **Found during:** Task 1 verification (pytest run after _DEFAULTS update)
- **Issue:** `test_save_and_load_config_roundtrip` asserts `result == {"launch_at_startup": True}` — the merge pattern `{**_DEFAULTS, **data}` now adds `"thresholds": {}` to the result, breaking this assertion too. The plan only mentioned `test_load_config_returns_defaults_when_file_absent` and `test_load_config_returns_defaults_on_malformed_json`.
- **Fix:** Updated the roundtrip test assertion to `{"launch_at_startup": True, "thresholds": {}}` which correctly reflects the new merge behavior.
- **Files modified:** `tests/test_ui_settings.py`
- **Commit:** included in `9e3d74d`

## Verification

```
python -c "from windows_toasts import Toast, WindowsToaster; print('OK')"  → OK
pytest tests/test_ui_settings.py -x -q                                     → 16 passed
pytest tests/ -x -q                                                         → 152 passed (no regressions)
sys.coinit_flags guard on line 2 of __main__.py                             → verified
```

## Known Stubs

None — all wiring is complete. NotificationManager.check() is called on every queue drain; no placeholder paths remain.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. T-06-04 mitigation (threshold clamping) was implemented in Plan 01 and remains in place.

## Self-Check: PASSED

- `src/__main__.py` — modified (NotificationManager wired, coinit guard on line 2)
- `src/ui/settings_manager.py` — modified (_DEFAULTS includes "thresholds": {})
- `tests/test_ui_settings.py` — modified (three assertion updates)
- Commit `9e3d74d` — Task 1: settings_manager _DEFAULTS + test updates
- Commit `ec5e681` — Task 2: __main__.py NotificationManager wiring
- 152 tests pass
