---
phase: 02-hidpp-20-protocol
plan: "02-04"
subsystem: hidpp-integration
tags: [hid, hidpp, battery, logitech, integration, entry-point]

requires:
  - phase: 02-hidpp-20-protocol
    provides: src/hidpp/receiver.py (find_receiver, open_receiver, discover_device_index)
  - phase: 02-hidpp-20-protocol
    provides: src/hidpp/features.py (battery_probe_chain, BatteryResult)

provides:
  - src/query_battery.py — standalone Phase 2 integration entry point

affects: [Phase 3 UI integration, Phase 7 packaging/exe boot trace]

tech-stack:
  added: []
  patterns: [sys.coinit_flags-line-2-invariant, try-finally-device-lifetime, numbered-step-comments]

key-files:
  created:
    - src/query_battery.py
  modified: []

key-decisions:
  - "query_battery.py uses usage_page=0xFF43 error message (not 0xFF00) — matches actual receiver.py VENDOR_USAGE_PAGE constant"
  - "sys.coinit_flags = 0 on line 2, before all imports — COM MTA invariant enforced"
  - "device.close() in finally block — guaranteed even on exception (T-02-09 mitigation)"

patterns-established:
  - "Entry point pattern: import sys; sys.coinit_flags = 0 before ALL other imports"
  - "Device lifetime: caller-owns-close via try/finally, never relying on GC"

requirements-completed: [HID-01, BATT-01, BATT-02]

duration: 8min
completed: 2026-06-02
---

# Phase 2 Plan 04: query_battery.py Integration Entry Point Summary

**Standalone integration script wiring receiver.py + features.py into a runnable battery reader for G Pro X Wireless via G-series 0x06/0x0D command — awaiting hardware checkpoint**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-02T11:40:51Z
- **Completed:** 2026-06-02T11:49:00Z (Task 1); Task 2 awaiting hardware verification
- **Tasks:** 1/2 (Task 2 is checkpoint:human-verify)
- **Files modified:** 1

## Accomplishments

- `src/query_battery.py` created — wires all Phase 2 modules end-to-end
- `sys.coinit_flags = 0` on line 2 confirmed by automated check
- `try/finally` guarantees `device.close()` (T-02-09 mitigated)
- No-dongle path exits 1 with PID list; OFFLINE path prints message on None result
- All 24 existing tests pass (no regressions)

## Task Commits

1. **Task 1: Create src/query_battery.py** — `1d86638` (feat)
2. **Task 2: Hardware integration test** — CHECKPOINT (awaiting human)

## Files Created/Modified

- `src/query_battery.py` — Phase 2 standalone integration script; enumerate receiver, open, discover index, probe battery chain, print result

## Decisions Made

- Used `0xFF43` in the no-receiver error message instead of the plan's `0xFF00`, because `find_receiver()` actually filters on `VENDOR_USAGE_PAGE = 0xFF43` (confirmed in 02-02). The error message must match the actual filter so users know what interface is missing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Error message usage_page corrected from 0xFF00 to 0xFF43**
- **Found during:** Task 1 (creating query_battery.py)
- **Issue:** The task action block specified the no-dongle error message as `"No usage_page=0xFF00 interface found"`, but `receiver.py` filters on `VENDOR_USAGE_PAGE = 0xFF43` (confirmed hardware probe in 02-01). The error message must reflect the actual filter value so it accurately describes what is being looked for.
- **Fix:** Changed error message to `"No usage_page=0xFF43 interface found"`.
- **Files modified:** src/query_battery.py
- **Verification:** Matches `VENDOR_USAGE_PAGE = 0xFF43` in receiver.py
- **Committed in:** 1d86638 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - message accuracy)
**Impact on plan:** Trivial one-line string correction. No scope change.

## Issues Encountered

None — Task 1 executed cleanly. Python syntax check and coinit_flags position check both passed. Full test suite 24/24 passed.

## Hardware Checkpoint (Task 2)

Status: PENDING — user must run TEST A (no dongle), TEST B (headset ON), TEST C (headset OFF) and report results. The TEST B output is the Phase 2 proof of life.

TEST B expected output:
```
=== All Logitech (0x046D) HID interfaces ===
  PID=0x0ABA  usage_page=0xFF43  ...
Found receiver: PID=0x0ABA
Device index: 0xFF
Battery: XX% — not charging (feature 0x06/0x0D)
```

## Known Stubs

None — all functions are fully wired. `query_battery.py` calls real `find_receiver`, `open_receiver`, `discover_device_index`, and `battery_probe_chain`.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes.

## Next Phase Readiness

After Task 2 hardware checkpoint passes:
- Phase 2 requirements HID-01, BATT-01, BATT-02 are satisfied
- Phase 3 (UI layer) can consume `battery_probe_chain` and `find_receiver` with confidence the protocol layer is hardware-verified
- Phase 7 packaging must validate that `sys.coinit_flags = 0` survives PyInstaller import reordering

## Self-Check: PASSED (Task 1 only — Task 2 pending hardware)

| Item | Status |
|------|--------|
| src/query_battery.py | FOUND |
| sys.coinit_flags on line 2 | CONFIRMED (automated check passed) |
| Syntax OK | CONFIRMED |
| 24 tests pass | CONFIRMED |
| Commit 1d86638 | FOUND |
| Task 2 hardware checkpoint | PENDING |

---
*Phase: 02-hidpp-20-protocol*
*Plan: 02-04*
*Completed: 2026-06-02 (partial — awaiting hardware checkpoint)*
