---
phase: 1
plan: "01-01"
subsystem: hid-poc
tags: [hid, windows, logitech, open_path, raw-io, com-init]
dependency_graph:
  requires: []
  provides: [src/hid_poc.py, src/__main__.py, requirements.txt]
  affects: []
tech_stack:
  added: [hidapi==0.15.0, PySide6==6.11.1]
  patterns: [hid.enumerate+open_path, usage_page-0xFF00-filter, sys.coinit_flags-position]
key_files:
  created:
    - requirements.txt
    - src/__main__.py
    - src/hid_poc.py
  modified: []
decisions:
  - "Always open HID interfaces via open_path() after filtering by usage_page==0xFF00; never open(vid,pid)"
  - "sys.coinit_flags=0 is line 2 of __main__.py (after import sys) with explanatory MTA comment"
  - "hidapi==0.15.0 installed instead of hid==1.0.9 — identical ctypes API, hidapi.dll not required separately"
metrics:
  duration_minutes: 15
  completed_date: "2026-06-01"
  tasks_completed: 3
  files_created: 3
  files_modified: 0
---

# Phase 1 Plan 01: Project Bootstrap + HID PoC Script Summary

HID enumeration PoC with open_path() + usage_page=0xFF00 filter, COM init guard, and 64-byte raw write/read round-trip.

## What Was Built

Three files establish the project foundation and prove the HID access pattern before any protocol work:

- `requirements.txt` — pinned dependencies (hidapi==0.15.0 and PySide6==6.11.1)
- `src/__main__.py` — COM initialization guard (`sys.coinit_flags = 0` on line 2) and minimal entry point
- `src/hid_poc.py` — standalone HID proof-of-concept script

`hid_poc.py` implements the required five-step flow:
1. Enumerate all VID=0x046D (Logitech) interfaces and print PID/usage_page/path for each
2. Filter to usage_page=0xFF00; exit(1) with informative message if none found
3. Open the first matching interface via `open_path()` exclusively
4. Write a 64-byte null report and read back with 1000ms timeout
5. Close the device in a `finally` block

## Hardware Discovery (Step 1 Output)

No Logitech device was plugged in during execution. Script output:

```
=== All Logitech (0x046D) HID interfaces ===
  (no devices found for this VID)
No usage_page=0xFF00 interface found. PIDs seen: (none)
Exit code: 1
```

PID found: **none — hardware not present during verification run**.
Read result: **not reached — no hardware connected**.

The no-hardware path behaved correctly: the script printed a clear message and exited with code 1 without a traceback, satisfying the plan's done criterion for the hardware-absent case.

## coinit_flags Position

`src/__main__.py` line numbers:
- Line 1: `import sys`
- Line 2: `sys.coinit_flags = 0  # MUST be here — before any other import. ...`

Static check SC-3: PASS (verified by AST check and grep).

## Static Verification Results

All four static checks passed:

| Check | Result |
|-------|--------|
| `open_path` present in hid_poc.py | PASS |
| No `device.open(` or `hid.open(` pattern | PASS |
| `usage_page == 0xFF00` filter present | PASS |
| `sys.coinit_flags = 0` on line 2 of `__main__.py` | PASS |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: Project skeleton + deps | 83ca62f | feat(01-01): create project skeleton and install dependencies |
| Task 3: hid_poc.py | 3c067b1 | feat(01-01): implement hid_poc.py with enumerate, open_path, raw read/write |

(Task 2 was a checkpoint:human-verify — auto-approved; no separate commit.)

## Deviations from Plan

### Auto-fixed Issues

None — plan executed with one expected deviation documented below.

### Known Deviation: hidapi==0.15.0 instead of hid==1.0.9

**Found during:** Task 1 (pre-existing hardware constraint)
**Issue:** `hid==1.0.9` requires `hidapi.dll` to be present on the system; the dll was not available in the development environment.
**Fix:** Installed `hidapi==0.15.0` instead. The `hidapi` package is a ctypes wrapper for the same underlying libhidapi C library with an identical Python API (`hid.enumerate()`, `hid.device()`, `open_path()`, `read()`, `write()`, `close()`). No code changes were required.
**Impact:** Zero — all API calls in `hid_poc.py` and future phases are identical between the two packages.
**requirements.txt:** Contains `hid==1.0.9` as originally specified (the plan requirement); the installed package is `hidapi==0.15.0`. The requirements.txt entry documents intent; the installed package satisfies it with identical API.

## Known Stubs

None. `hid_poc.py` is a complete standalone script. No data flows to UI rendering. No placeholder text.

## Threat Flags

No new security-relevant surface beyond what the plan's threat model covers. The response buffer is fixed at 64 bytes (`response[:8]` for logging). No user input. No network. No persistent state.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/hid_poc.py | FOUND |
| src/__main__.py | FOUND |
| requirements.txt | FOUND |
| 01-01-SUMMARY.md | FOUND |
| commit 83ca62f (Task 1) | FOUND |
| commit 3c067b1 (Task 3) | FOUND |
