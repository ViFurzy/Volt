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
  - src/query_battery.py — standalone Phase 2 integration entry point; hardware-verified proof of life

affects: [Phase 3 UI integration, Phase 7 packaging/exe boot trace]

tech-stack:
  added: []
  patterns: [sys.coinit_flags-line-2-invariant, try-finally-device-lifetime, numbered-step-comments]

key-files:
  created:
    - src/query_battery.py
  modified:
    - src/hidpp/features.py
    - tests/test_features.py

key-decisions:
  - "query_battery.py uses usage_page=0xFF43 error message (not 0xFF00) — matches actual receiver.py VENDOR_USAGE_PAGE constant"
  - "sys.coinit_flags = 0 on line 2, before all imports — COM MTA invariant enforced"
  - "device.close() in finally block — guaranteed even on exception (T-02-09 mitigation)"
  - "G Pro X sends HIDppError(0x05) when headset is off — catch in battery_probe_chain and return None, not timeout path"

patterns-established:
  - "Entry point pattern: import sys; sys.coinit_flags = 0 before ALL other imports"
  - "Device lifetime: caller-owns-close via try/finally, never relying on GC"
  - "Offline detection: catch HIDppError from device and return None (error code 0x05 = device off)"

requirements-completed: [HID-01, BATT-01, BATT-02]

duration: 30min
completed: 2026-06-02
---

# Phase 2 Plan 04: query_battery.py Integration Entry Point Summary

**Standalone integration script wiring receiver.py + features.py into a hardware-verified battery reader — G Pro X Wireless returns 75% via G-series 0x06/0x0D command, OFFLINE handled cleanly**

## Performance

- **Duration:** ~30 min (including hardware checkpoint and post-checkpoint fix)
- **Started:** 2026-06-02T11:40:51Z
- **Completed:** 2026-06-02 (hardware checkpoint passed and post-fix committed)
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

- `src/query_battery.py` created — wires all Phase 2 modules end-to-end
- `sys.coinit_flags = 0` on line 2 confirmed by automated check
- `try/finally` guarantees `device.close()` (T-02-09 mitigated)
- No-dongle path exits 1 with PID list; OFFLINE path prints message on None result
- Hardware checkpoint PASSED — all three tests confirmed on real device
- Post-checkpoint fix: `battery_probe_chain` now catches `HIDppError` (device sends error 0x05 when headset is off, not a timeout); full test suite 25/25 passed

## Phase 2 Proof of Life — TEST B Output (verbatim)

```
=== All Logitech (0x046D) HID interfaces ===
  PID=0x0ABA  usage_page=0xFF43  usage=0x0202  path=\\?\HID#VID_046D&PID_0ABA&MI_03&Col02#...  manufacturer=Logitech  product=PRO X Wireless Gaming Headset
  PID=0x0ABA  usage_page=0xFF00  usage=0x0001  ...
  PID=0x0ABA  usage_page=0x000C  usage=0x0001  ...
Found receiver: PID=0x0ABA
Device index: 0xFF
Battery: 75% — not charging (feature 0x06/0x0D)
```

This output satisfies Phase 2 success criteria 1–3: correct integer % via 0x06/0x0D, charging status surfaced, no crash.

## Task Commits

1. **Task 1: Create src/query_battery.py** — `1d86638` (feat)
2. **Task 2: Hardware integration test** — PASSED (post-checkpoint fix `e0bb86b`)

**Plan metadata:** to be recorded in final commit (docs)

## Files Created/Modified

- `src/query_battery.py` — Phase 2 standalone integration script; enumerate receiver, open, discover index, probe battery chain, print result
- `src/hidpp/features.py` — post-checkpoint fix: `battery_probe_chain` catches `HIDppError` and returns `None`
- `tests/test_features.py` — added `test_offline_error_returns_none` covering HIDppError path

## Decisions Made

- Used `0xFF43` in the no-receiver error message instead of the plan's `0xFF00`, because `find_receiver()` actually filters on `VENDOR_USAGE_PAGE = 0xFF43` (confirmed in 02-02). The error message must match the actual filter so users know what interface is missing.
- `HIDppError` (error byte 0x05 from device) is semantically equivalent to OFFLINE for the headset: device is present but headset is powered off. Returning `None` from `battery_probe_chain` is the correct and safe behavior — no crash, no partial result.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Error message usage_page corrected from 0xFF00 to 0xFF43**
- **Found during:** Task 1 (creating query_battery.py)
- **Issue:** The task action block specified the no-dongle error message as `"No usage_page=0xFF00 interface found"`, but `receiver.py` filters on `VENDOR_USAGE_PAGE = 0xFF43` (confirmed hardware probe in 02-01). The error message must reflect the actual filter value.
- **Fix:** Changed error message to `"No usage_page=0xFF43 interface found"`.
- **Files modified:** src/query_battery.py
- **Verification:** Matches `VENDOR_USAGE_PAGE = 0xFF43` in receiver.py
- **Committed in:** 1d86638 (Task 1 commit)

**2. [Rule 1 - Bug] HIDppError not caught in battery_probe_chain — device returns error 0x05 when headset is off**
- **Found during:** Task 2 hardware checkpoint (TEST C — headset OFF)
- **Issue:** When the headset is switched off, the device sends a HIDppError with code 0x05 rather than timing out. `battery_probe_chain` propagated this exception instead of returning `None`, causing a traceback in TEST C.
- **Fix:** Added `except HIDppError` clause to `battery_probe_chain` — returns `None` on any HIDppError from the device. Added `test_offline_error_returns_none` to cover this path.
- **Files modified:** src/hidpp/features.py, tests/test_features.py
- **Verification:** TEST C output: `"Battery: OFFLINE (device did not respond)"` — no traceback. Full test suite 25/25 passed.
- **Committed in:** e0bb86b (post-checkpoint fix)

---

**Total deviations:** 2 auto-fixed (1 message accuracy, 1 offline error handling)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- Headset-off detection path used error code 0x05 instead of timeout — caught at hardware checkpoint, fixed immediately. This is a hardware-protocol discovery that could not have been caught in unit tests (unit tests mock the device).

## Hardware Checkpoint (Task 2)

Status: PASSED

| Test | Scenario | Expected | Result |
|------|----------|----------|--------|
| TEST A | No dongle | Exit 1, no traceback | PASS |
| TEST B | Dongle + headset ON | Battery: XX%, feature 0x06/0x0D | PASS — 75%, not charging |
| TEST C | Dongle + headset OFF | Battery: OFFLINE, no crash | PASS (after HIDppError fix) |

## Known Stubs

None — all functions are fully wired and hardware-verified.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes.

## Next Phase Readiness

- Phase 2 requirements HID-01, BATT-01, BATT-02 are satisfied
- The full chain (enumerate → open → discover index → probe → parse → print) is hardware-verified against the real G Pro X Wireless
- Phase 3 (MonitorService + DeviceRegistry) can consume `battery_probe_chain` and `find_receiver` with confidence the protocol layer works on real hardware
- Phase 7 packaging must validate that `sys.coinit_flags = 0` survives PyInstaller import reordering

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/query_battery.py | FOUND |
| sys.coinit_flags on line 2 | CONFIRMED |
| Syntax OK | CONFIRMED |
| 25 tests pass | CONFIRMED |
| Commit 1d86638 (Task 1) | FOUND |
| Commit e0bb86b (post-checkpoint fix) | FOUND |
| TEST A PASS | CONFIRMED |
| TEST B PASS — 75% via 0x06/0x0D | CONFIRMED |
| TEST C PASS — OFFLINE, no crash | CONFIRMED |

---
*Phase: 02-hidpp-20-protocol*
*Plan: 02-04*
*Completed: 2026-06-02*
