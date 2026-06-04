---
phase: 06-notifications
plan: 01
subsystem: notifications
tags: [tdd, notifications, cooldown, threshold]
dependency_graph:
  requires: []
  provides: [NotificationManager, NOTIF-01, NOTIF-02]
  affects: [src/ui/notification_manager.py, tests/test_notification_manager.py, requirements.txt]
tech_stack:
  added: [windows-toasts==1.3.1]
  patterns: [in-memory dict keyed by (vid,pid,dev_idx), threshold clamping, cooldown suppression, OFFLINE reset]
key_files:
  created:
    - src/ui/notification_manager.py
    - tests/test_notification_manager.py
  modified:
    - requirements.txt
decisions:
  - threshold defaults to 15% when no per-device config entry exists
  - cooldown is purely in-memory (resets on process restart and on device OFFLINE transition)
  - threshold clamped to [1, 99] silently — never raises on bad config
  - NotificationManager has no Qt imports so tests run headlessly
metrics:
  duration_minutes: 12
  completed_date: 2026-06-04
  tasks_completed: 2
  files_modified: 3
---

# Phase 06 Plan 01: NotificationManager TDD Summary

**One-liner:** NotificationManager with threshold crossing + 4-hour cooldown + OFFLINE reset, backed by 7 unit tests using mocked WindowsToaster.

## What Was Built

`src/ui/notification_manager.py` — a standalone service class (`NotificationManager`) with:
- `__init__`: constructs a single `WindowsToaster("PeriphWatcher")` instance and an empty `_last_notified` dict keyed by `(vid, pid, dev_idx)`.
- `check(state, config)`: compares `state.percent` against a per-device configurable threshold (default 15%), gates on cooldown (default 4 hours), fires a two-line toast on crossing, and clears the cooldown entry when `state.status == DeviceStatus.OFFLINE`.

`tests/test_notification_manager.py` — 7 unit tests with no real WinRT calls (WindowsToaster patched via `unittest.mock.patch`):
1. `test_fires_on_threshold_crossing` — toast fires on first below-threshold reading
2. `test_no_fire_above_threshold` — no toast when percent >= 15
3. `test_no_fire_when_percent_none` — no toast when percent is None
4. `test_default_threshold` — percent=14 fires with empty thresholds config
5. `test_cooldown_suppresses` — second immediate call does not fire
6. `test_fires_after_cooldown` — time-travel: 5-hour-old entry fires (4h default expired)
7. `test_cooldown_resets_on_offline` — OFFLINE call clears `_last_notified` entry

`requirements.txt` — added `windows-toasts==1.3.1` (plus auto-pulled `winrt-runtime` and `winrt-Windows.*` namespace packages were installed to venv).

## TDD Gate Compliance

- RED gate: `test(06-01)` commit `c648efd` — 7 tests failing with ModuleNotFoundError
- GREEN gate: `feat(06-01)` commit `937b8e9` — all 7 tests passing; full suite 152 passed

## Deviations from Plan

**1. [Rule 2 - Missing functionality] windows-toasts not yet installed**

- **Found during:** Task 1 pre-flight
- **Issue:** `windows-toasts==1.3.1` was listed in RESEARCH.md as "not yet installed" and confirmed absent from `.venv-1`.
- **Fix:** `pip install windows-toasts==1.3.1` into `.venv-1`; added `windows-toasts==1.3.1` to `requirements.txt`.
- **Files modified:** `requirements.txt`
- **Commit:** included in `937b8e9`

**2. settings_manager.py `_DEFAULTS` not modified**

- **Context:** PATTERNS.md suggests adding `"thresholds": {}` to `_DEFAULTS` in `settings_manager.py`.
- **Decision:** Deferred — `test_load_config_returns_defaults_when_file_absent` asserts `result == {"launch_at_startup": False}`. Adding `"thresholds": {}` here would break that test. `NotificationManager.check()` already handles missing thresholds via `.get("thresholds", {})` with no `KeyError`. The `_DEFAULTS` update belongs in a wiring plan (06-02 or 06-03) that also updates the test assertion.

## Verification

```
pytest tests/test_notification_manager.py -x -v  → 7 passed
pytest tests/ -x                                  → 152 passed (no regressions)
```

## Known Stubs

None — all logic is complete and tested. No placeholder values or hardcoded mock data reach the UI rendering path.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. Threshold clamping (`max(1, min(99, int(...)))`) satisfies T-06-01 mitigation as specified in the threat register.

## Self-Check: PASSED

- `src/ui/notification_manager.py` — exists
- `tests/test_notification_manager.py` — exists
- Commit `c648efd` — exists (RED gate)
- Commit `937b8e9` — exists (GREEN gate)
- 7 tests pass, 152 total pass
