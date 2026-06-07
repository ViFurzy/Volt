---
phase: 05-steelseries-hid-backend
plan: "02"
subsystem: monitor-service-dispatch
tags: [steelseries, device-probes, dispatch, polling, service, tests]
dependency_graph:
  requires:
    - src/steelseries/driver.py (ss_battery_probe, find_dongle, open_dongle, SS_DEVICE_IDX)
    - src/hidpp/features.py (battery_probe_chain, BatteryResult)
    - src/hidpp/receiver.py (find_receiver, open_receiver, DEVICE_IDX)
  provides:
    - src/monitor/state.py (KNOWN_DEVICES updated + DEVICE_PROBES new)
    - src/monitor/service.py (device-agnostic discover + poll_once dispatch)
  affects:
    - tests/test_service.py (migrated patches + 4 new SS tests)
tech_stack:
  added: []
  patterns:
    - DEVICE_PROBES dispatch dict: (vid,pid) -> probe_fn for device-agnostic polling
    - info-dict-in-_open pattern: SteelSeries stores info dict instead of open handle
    - per-poll open/close: open_dongle + probe + close per poll_once iteration for SS
    - voltage_mv==0 guard: bypasses smoothing deque for devices without voltage sensor
    - AttributeError guard on handle.close(): handles dict vs hid.device in _open
key_files:
  created: []
  modified:
    - src/monitor/state.py
    - src/monitor/service.py
    - tests/test_service.py
decisions:
  - "DEVICE_PROBES in state.py maps (vid,pid) to probe callables; service.py imports it — no circular import because hidpp/steelseries don't import monitor"
  - "SteelSeries stored as info dict in _open (not open handle); poll_once detects via probe_fn is ss_battery_probe and does open/close per poll"
  - "voltage_mv==0 guard uses result.percent directly without updating _voltage_history (SteelSeries has no voltage sensor)"
  - "discover() guarded with try/except AttributeError for close() on dict entries (T-05-04 mitigation)"
  - "test_zero_voltage_skips_smoothing uses real ss_battery_probe with mock handle read side_effect rather than patching ss_battery_probe — keeps the identity check (probe_fn is ss_battery_probe) valid while controlling output"
metrics:
  duration_minutes: 25
  completed_date: "2026-06-04"
  tasks_completed: 2
  files_created: 0
  files_modified: 3
---

# Phase 5 Plan 2: MonitorService DEVICE_PROBES Dispatch Summary

**One-liner:** MonitorService made device-agnostic via DEVICE_PROBES dispatch dict — SteelSeries Aerox 5 Wireless wired with per-poll open/close lifecycle and voltage_mv==0 smoothing bypass.

## What Was Built

### Task 1 — state.py + service.py

**`src/monitor/state.py`:**
- Extended `KNOWN_DEVICES` to add `(0x1038, 0x1852): "Aerox 5 Wireless"`
- Added `DEVICE_PROBES: dict[tuple[int,int], callable]` immediately after `KNOWN_DEVICES`, mapping Logitech VID/PID to `battery_probe_chain` and SS VID/PID to `ss_battery_probe`
- Added imports for `battery_probe_chain` and `ss_battery_probe` at module level (no circular import: neither hidpp nor steelseries imports from monitor)

**`src/monitor/service.py`:**
- Removed direct `battery_probe_chain` import; added `DEVICE_PROBES` to monitor.state import
- Added `from steelseries.driver import SS_DEVICE_IDX, find_dongle, open_dongle, ss_battery_probe`
- `discover()`: now enumerates both `find_receiver()` (Logitech) and `find_dongle()` (SteelSeries); builds `found_keys` from both; stores persistent handle for Logitech, info dict for SteelSeries; guards `handle.close()` with `except AttributeError` for dict entries
- `poll_once()`: dispatches via `DEVICE_PROBES.get((vid, pid))`; SteelSeries branch (`probe_fn is ss_battery_probe`) opens fresh handle via `open_dongle`, probes, closes in `finally`; `voltage_mv==0` guard uses `result.percent` directly without updating `_voltage_history`

### Task 2 — tests/test_service.py

- Added SS test constants (`SS_VID`, `SS_PID`, `SS_KEY`, `SS_INTERFACE`) and imports (`SS_DEVICE_IDX`, `_ss_battery_probe`)
- Added `find_dongle=[]` patch to all 5 existing `TestDiscover` tests (without it, real hardware enumeration contaminates results after discover() gained SS support)
- Migrated 4 `battery_probe_chain` patches to `mocker.patch.dict("monitor.service.DEVICE_PROBES", ...)`
- **New `TestDiscover` tests:**
  - `test_ss_dongle_unplug_marks_offline` — SS key removed from `_open`, registry OFFLINE when `find_dongle` returns empty
  - `test_ss_discover_stores_info_dict` — `_open[SS_KEY]` is a dict, not a hid.device handle
- **New `TestPollOnce` tests:**
  - `test_dispatches_via_device_probes` — MagicMock probe_fn called with correct (handle, dev_idx)
  - `test_zero_voltage_skips_smoothing` — real `ss_battery_probe` with mocked handle read returning `[0xD2, 0x05]`; asserts `percent==20` and `SS_KEY not in _voltage_history`

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update state.py + service.py | 719335a | src/monitor/state.py, src/monitor/service.py |
| 2 | Migrate and extend test_service.py | 2cd5556 | tests/test_service.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] All existing TestDiscover tests needed find_dongle=[] patches**
- **Found during:** Task 2 — first test run after Task 1 showed 2 unexpected discover failures
- **Issue:** `test_skips_unknown_vid_pid` and `test_skips_device_on_oserror` (and 3 others) did not patch `find_dongle`, so the real HID enumeration found the actual SS dongle on the dev machine, causing unexpected ONLINE registry entries
- **Fix:** Added `mocker.patch("monitor.service.find_dongle", return_value=[])` to all 5 existing `TestDiscover` tests
- **Files modified:** tests/test_service.py (no separate commit — part of Task 2)

**2. [Rule 1 - Bug] test_zero_voltage_skips_smoothing needed real probe response, not patched ss_battery_probe**
- **Found during:** Task 2 — test initially patched `steelseries.driver.ss_battery_probe` but poll_once's `probe_fn is ss_battery_probe` identity check uses the function object from `DEVICE_PROBES`, which pointed to the original unpatched `_ss_battery_probe`. The patched version in `steelseries.driver` module was not called.
- **Fix:** Used real `ss_battery_probe` with mock handle `read.side_effect = [[], [], [], [0xD2, 0x05, ...]]` so the real parsing logic runs and returns `BatteryResult(percent=20, voltage_mv=0, ...)`
- **Files modified:** tests/test_service.py

## Threat Model Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-05-03 | `except OSError` around `open_dongle` in `poll_once()`; result=None → existing OFFLINE path |
| T-05-04 | `except AttributeError` around `handle.close()` in `discover()` — dict has no `.close()` |

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, or trust boundary changes introduced.

## Verification Results

```
pytest tests/test_service.py -v  → 15 passed (4 migrated + 2 new discover + 2 new poll + 2 safety)
pytest tests/ -x                 → 145 passed (no regressions from prior 141)
python -c "from monitor.state import DEVICE_PROBES; ..."  → DEVICE_PROBES OK
python -c "from monitor.service import MonitorService; ..."  → service import OK
```

## Self-Check: PASSED

- [x] `src/monitor/state.py` — `KNOWN_DEVICES` has `(0x1038, 0x1852): "Aerox 5 Wireless"`; `DEVICE_PROBES` defined with both keys
- [x] `src/monitor/service.py` — `battery_probe_chain` no longer imported; `DEVICE_PROBES`, `find_dongle`, `open_dongle`, `SS_DEVICE_IDX`, `ss_battery_probe` imported
- [x] `src/monitor/service.py` — `discover()` calls both `find_receiver()` and `find_dongle()`; stores info dict for SS
- [x] `src/monitor/service.py` — `poll_once()` dispatches via `DEVICE_PROBES`; SS branch does per-poll open/close; voltage_mv==0 guard present
- [x] `tests/test_service.py` — 4 `battery_probe_chain` patches migrated to `mocker.patch.dict(DEVICE_PROBES)`
- [x] `tests/test_service.py` — 4 new tests added (SS unplug, SS info dict, dispatch, smoothing guard)
- [x] Commit `719335a` exists in git log
- [x] Commit `2cd5556` exists in git log
- [x] Full suite: 145/145 green
