---
phase: 2
plan: "02-03"
subsystem: hidpp-features
tags: [hid, battery, calibration, tdd, logitech-headset, voltage-to-percent]
dependency_graph:
  requires: [src/hidpp/protocol.py, tests/conftest.py]
  provides: [src/hidpp/features.py, tests/test_features.py]
  affects: [src/hidpp/receiver.py]
tech_stack:
  added: []
  patterns: [piecewise-linear-interpolation, dataclass-result-type, TDD-RED-GREEN]
key_files:
  created:
    - src/hidpp/features.py
    - tests/test_features.py
  modified: []
decisions:
  - "battery_probe_chain sends exactly 20 bytes: [0x11, device_idx, 0x06, 0x0D] + 16 zero bytes"
  - "Voltage parsed from response[4:6] big-endian; charging from response[6] == 0x03"
  - "voltage_to_percent uses 6-point piecewise linear calibration from HeadsetControl reference"
  - "None return on timeout — callers handle offline state without exception"
  - "OSError propagates to caller — hardware errors not swallowed here"
metrics:
  completed_date: "2026-06-02"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
---

# Phase 2 Plan 03: G Pro X Battery Reading Module Summary

## What Was Built

Two files implementing and testing the G Pro X Wireless battery read path:

- `src/hidpp/features.py` — `BatteryResult`, `voltage_to_percent`, `battery_probe_chain`
- `tests/test_features.py` — 11 unit tests covering all protocol paths

`features.py` exports:
- `BatteryResult` — dataclass with `percent: int`, `charging: bool`, `feature_used: str`
- `_CALIB` — 6-point calibration table `[(mV, pct), ...]` sorted ascending by mV
- `voltage_to_percent(mv: int) -> int` — piecewise linear interpolation with clamping
- `battery_probe_chain(device, device_idx: int) -> BatteryResult | None` — full read path

## Test Results

```
pytest tests/test_features.py -x -q
11 passed in 0.01s

pytest tests/ -x -q
19 passed in 0.02s
```

TDD cycle followed: RED confirmed (ModuleNotFoundError before features.py created), GREEN confirmed after implementation.

## Protocol Details

Battery command (20 bytes):
```
[0x11, 0xFF, 0x06, 0x0D, 0x00 × 16]
```

Response parsing:
```
response[4:6] = voltage mV big-endian
response[6]   = 0x01 discharging → charging=False
response[6]   = 0x03 charging    → charging=True
```

Calibration curve used (G Pro X Wireless, HeadsetControl reference):
```
mV:  3320 → 3670 → 3740 → 3780 → 3830 → 4150
pct:    0 →    5 →   20 →   30 →   50 →  100
```

Live hardware example from 02-01 probe:
```
[0x11, 0xFF, 0x06, 0x0D, 0x0D, 0xF4, 0x01, ...]
voltage = (0x0D << 8) | 0xF4 = 3572 mV → ~3-4% battery, discharging
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | d192fe4 | feat(02-03): implement G Pro X battery reading — features.py + 11 tests |

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

| Gate | Status |
|------|--------|
| RED (ModuleNotFoundError on import) | Confirmed before implementation |
| GREEN (11 tests pass) | Confirmed after implementation |

## Known Stubs

None — `battery_probe_chain` is fully wired to `send_and_recv` from `protocol.py`. No placeholder data.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. All surface is the existing HID device handle passed by the caller — unchanged trust boundary from `protocol.py`.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/hidpp/features.py | FOUND |
| tests/test_features.py | FOUND (11 tests pass) |
| voltage_to_percent(3830) == 50 | CONFIRMED |
| battery_probe_chain sends 20-byte command | CONFIRMED (test_command_bytes_correct) |
| No 0x1004/0x1000/0x1001 in features.py | CONFIRMED |
| Commit d192fe4 | FOUND |
