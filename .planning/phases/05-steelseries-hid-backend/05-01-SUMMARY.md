---
phase: 05-steelseries-hid-backend
plan: "01"
subsystem: steelseries-driver
tags: [hid, steelseries, driver, battery]
dependency_graph:
  requires:
    - src/hidpp/features.py (BatteryResult dataclass)
  provides:
    - src/steelseries/driver.py (find_dongle, open_dongle, ss_battery_probe)
    - src/steelseries/__init__.py (package marker)
  affects:
    - MonitorService (Phase 05-02 will wire DEVICE_PROBES dispatch)
tech_stack:
  added: []
  patterns:
    - interface_number==3 filter (not usage_page) for SteelSeries HID enumeration
    - open_path() exclusively — never hid.open(vid, pid)
    - 3-warmup-read + write + 20-packet-scan probe sequence
    - level_byte decode: raw=(byte & 0x7F), pct=(raw-1)*5; charging=bool(byte & 0x80)
key_files:
  created:
    - src/steelseries/__init__.py
    - src/steelseries/driver.py
    - tests/test_steelseries_driver.py
  modified: []
decisions:
  - "Filter by interface_number==3 (not usage_page): SteelSeries uses 0xFFC0, not 0xFF00"
  - "SS_DEVICE_IDX=0x00 as placeholder for (vid, pid, dev_idx) key; not used in command payload"
  - "Percent clamped via max(0, min(100, pct)) to satisfy T-05-01 threat mitigation"
metrics:
  duration_minutes: 10
  completed_date: "2026-06-04"
  tasks_completed: 2
  files_created: 3
  files_modified: 0
---

# Phase 5 Plan 1: SteelSeries Driver Package Summary

**One-liner:** SteelSeries Aerox 5 Wireless HID driver with interface_number=3 filter, 3-warmup-read probe sequence, and rivalcfg-derived level_byte formula returning BatteryResult.

## What Was Built

Created `src/steelseries/` package implementing the Aerox 5 Wireless 2.4GHz dongle protocol:

- **`find_dongle()`** — enumerates HID interfaces and filters by `interface_number==3` (the vendor-specific interface that accepts battery commands; interfaces 0–2 are locked by Windows)
- **`open_dongle()`** — opens a device handle via `open_path()` only; never `hid.open(vid, pid)`
- **`ss_battery_probe(device, dev_idx)`** — issues 3 warmup reads, writes `[0x00, 0xD2]`, scans up to 20 response packets skipping `0x61` async notification packets, parses `level_byte` per rivalcfg formula, returns `BatteryResult(voltage_mv=0, feature_used="0xD2")` or `None` on timeout

Complete unit test suite (12 tests) covering all behaviors including AST verification that `hid.open()` is never called.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | Failing test suite | d9357ac | tests/test_steelseries_driver.py |
| GREEN | Driver implementation | ffda1fb | src/steelseries/__init__.py, src/steelseries/driver.py |

## Deviations from Plan

None — plan executed exactly as written.

The two TDD tasks were implemented as separate RED/GREEN commits following the TDD gate sequence as required.

## Threat Model Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-05-01 | `pct = max(0, min(100, pct))` clamp added after level_byte parse |
| T-05-02 | `interface_number == SS_VENDOR_INTERFACE` filter in `find_dongle()` prevents opening primary mouse interface (Access Denied) |

## TDD Gate Compliance

- RED gate: `test(05-01)` commit `d9357ac` — 12 failing tests (ModuleNotFoundError on missing steelseries package)
- GREEN gate: `feat(05-01)` commit `ffda1fb` — all 12 tests pass, full suite 141/141 green

## Known Stubs

None. Driver returns real `BatteryResult` data from the hardware protocol. No placeholder values in data paths.

## Verification Results

```
pytest tests/test_steelseries_driver.py -v  → 12 passed
pytest tests/ -x                            → 141 passed (no regressions from prior 129)
python -c "from steelseries.driver import ..."  → imports without error
AST check: no hid.open() call found in driver.py
```

## Self-Check: PASSED

- [x] `src/steelseries/__init__.py` exists
- [x] `src/steelseries/driver.py` exists with all required exports
- [x] `tests/test_steelseries_driver.py` exists with 12 tests
- [x] Commit `d9357ac` (RED) exists in git log
- [x] Commit `ffda1fb` (GREEN) exists in git log
- [x] No `hid.open(vid, pid)` in driver.py (AST-verified)
- [x] `SS_VENDOR_INTERFACE=3` filters `interface_number`, not `usage_page`
- [x] `voltage_mv=0` in all BatteryResult returns
- [x] `feature_used="0xD2"` in all BatteryResult returns
