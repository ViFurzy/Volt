---
phase: 2
plan: "02-02"
subsystem: hidpp-receiver-layer
tags: [hid, hidpp, receiver, enumeration, device-discovery, pytest, tdd]
dependency_graph:
  requires: [src/hidpp/protocol.py, src/hid_poc.py]
  provides: [src/hidpp/receiver.py, tests/test_receiver.py]
  affects: [src/hidpp/features.py, src/hidpp/query_battery.py]
tech_stack:
  added: []
  patterns: [open_path-only, bytes-path-guard, per-index-exception-handling]
key_files:
  created:
    - src/hidpp/receiver.py
    - tests/test_receiver.py
  modified: []
decisions:
  - "VENDOR_USAGE_PAGE=0xFF43 — G Pro X Wireless uses 0xFF43 not 0xFF00 (confirmed 02-01 hardware probe)"
  - "discover_device_index probes 0x01-0x06 for generic HID++ 2.0; G Pro X battery path uses 0xFF (handled upstream)"
  - "open_receiver() does not try/finally — caller (query_battery.py) owns device lifetime"
  - "Per-index HIDppError and OSError caught and skipped for stale-handle resilience (T-02-04)"
metrics:
  duration_seconds: 154
  completed_date: "2026-06-02"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
---

# Phase 2 Plan 02: Receiver Layer Summary

## What Was Built

Two files implementing the HID receiver enumeration and device discovery layer:

- `src/hidpp/receiver.py` — `find_receiver`, `open_receiver`, `discover_device_index`
- `tests/test_receiver.py` — 4 unit tests covering index discovery with mocked hid

`receiver.py` exports:
- `LOGITECH_VID = 0x046D`, `VENDOR_USAGE_PAGE = 0xFF43`
- `DEVICE_INDEX_MIN = 0x01`, `DEVICE_INDEX_MAX = 0x06`
- `find_receiver(vid)` — enumerates VID=0x046D, filters for usage_page=0xFF43, prints all interfaces to stdout
- `open_receiver(info)` — opens via `open_path()` only; caller owns device lifetime; raises OSError on failure
- `discover_device_index(device)` — probes indices 0x01-0x06 via Root feature 0x0000 query; returns first responding index or None; never passes 0xFF as device_idx

## Test Results

```
pytest tests/test_receiver.py -x -q
4 passed in 0.01s
```

Full suite:
```
pytest -x -q
12 passed in 0.03s
```

TDD cycle followed: RED confirmed (ModuleNotFoundError before receiver.py), GREEN confirmed after implementation.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 (RED) | 98bfaf3 | test(02-02): add failing tests for receiver device index discovery |
| Task 1 (GREEN) | cd75e4d | feat(02-02): implement receiver.py — enumerate 0xFF43, open, discover device index |

## Deviations from Plan

### Deviation 1: VENDOR_USAGE_PAGE = 0xFF43 (not 0xFF00)

**Rule:** Rule 1/2 — Bug fix / missing critical functionality  
**Found during:** Plan start (reading 02-01-SUMMARY.md as instructed by action block)  
**Issue:** Plan's `must_haves.truths` specified `usage_page=0xFF00` for `find_receiver()`. The 02-01 hardware probe confirmed the G Pro X Wireless HID++ interface is on `usage_page=0xFF43`. Implementing 0xFF00 would enumerate the wrong interface and produce no results on the actual hardware.  
**Fix:** `VENDOR_USAGE_PAGE = 0xFF43` in receiver.py with explanatory comment referencing the 02-01 hardware probe.  
**Impact:** `find_receiver()` correctly enumerates the working interface. Unit tests are mock-based and unaffected by this change.  
**Files modified:** src/hidpp/receiver.py

### Deviation 2: Plan's discover_device_index behavior vs. hardware reality

**Rule:** Documentation only — no code change needed  
**Found during:** Reading 02-01-SUMMARY.md  
**Issue:** The plan specifies `discover_device_index` probing 0x01-0x06 and explicitly states "Device index 0xFF is never passed as device_idx to Root probe queries." Hardware probe confirmed the G Pro X Wireless uses device_idx=0xFF (fixed), not a discoverable index. The probe range 0x01-0x06 is for generic HID++ 2.0 paired-device discovery.  
**Resolution:** Implemented as specified (0x01-0x06 probe, never 0xFF). The G-specific 0xFF is handled by query_battery.py (Wave 3), not by this layer. Added docstring and comment explaining the split.  
**No code deviation** — plan behavior implemented exactly; only documentation adapted.

## Threat Mitigations Applied

| Threat ID | Mitigation | Location |
|-----------|-----------|----------|
| T-02-03 | Only `open_path()` after `usage_page==0xFF43` filter; never `hid.open(vid,pid)` | `open_receiver()` |
| T-02-04 | `OSError` caught per-index in `discover_device_index`; continues probing | `discover_device_index()` |
| T-02-05 | `path.decode("utf-8", errors="replace")` guard in `find_receiver()` | `find_receiver()` |

## Known Stubs

None — all exported functions are fully implemented with no hardcoded empty returns, placeholder text, or TODO stubs.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/hidpp/receiver.py | FOUND |
| tests/test_receiver.py | FOUND (4 tests pass) |
| find_receiver exported | CONFIRMED |
| open_receiver exported | CONFIRMED |
| discover_device_index exported | CONFIRMED |
| No hid.open() as code | CONFIRMED (only in comment) |
| 0xFF not in build_short_msg calls | CONFIRMED (idx ranges 0x01-0x06) |
| Commit 98bfaf3 (RED) | FOUND |
| Commit cd75e4d (GREEN) | FOUND |
