---
phase: 04-qt-ui-window-tray
plan: 04
subsystem: ui
tags: [pyside6, pytest-qt, integration-test, hidapi, hot-plug, tray, winreg]

# Dependency graph
requires:
  - phase: 04-03
    provides: DeviceCard widget, on_device_update, MainWindow._cards, dark-theme pipeline
  - phase: 03-04
    provides: MonitorApp consumer/drain contract, ui_queue, HotPlugWatcher
provides:
  - Headless end-to-end integration test for queue-drain → on_device_update → DeviceCard path
  - Hardware-verified Phase 4 stack: dark window, live device cards, close-to-tray, tray restore, startup persistence
  - Amber warning color finalized at #E5A300
affects: [05-steelseries-hid-backend, 06-notifications]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Headless integration test: MonitorApp(consumer=...) + direct ui_queue.put() + drain() — zero hardware, zero asyncio thread"
    - "Hardware checkpoint gate: executor pauses, user verifies all user-observable behaviors against real device, resumes on 'approved'"

key-files:
  created:
    - tests/test_ui_integration.py
  modified:
    - src/__main__.py
    - src/monitor/service.py
    - src/monitor/app.py

key-decisions:
  - "Amber warning color #E5A300 confirmed acceptable by user during visual checkpoint — no change required"
  - "poll_interval reduced from 60s to 2s for responsive state transitions during development/testing"
  - "HID handle kept open on OFFLINE state so device auto-recovers to ONLINE when headset is powered back on without dongle replug"
  - "percent==0 treated as transient OFFLINE; charging % hidden during CHARGING state to avoid misleading display"
  - "Known limitation: state transitions take 20-25s due to hidapi blocking the asyncio event loop on Windows — to be addressed with run_in_executor in a future pass"

patterns-established:
  - "Integration test pattern: construct MonitorApp with consumer= arg, use ui_queue directly, call drain() — tests real wiring without hardware or asyncio thread"
  - "Hardware checkpoint result documented in SUMMARY — outcome + any post-checkpoint fixes applied"

requirements-completed: [UI-01, UI-02, UI-03, SYS-01, SYS-02]

# Metrics
duration: ~90min (including hardware verification)
completed: 2026-06-02
---

# Phase 4 Plan 04: End-to-End Integration Test + Hardware Checkpoint Summary

**Full Phase 4 stack hardware-verified: dark window with live device card, close-to-tray, tray restore, startup persistence, and hot-plug ONLINE/OFFLINE — all 8 checkpoint checks passed; amber #E5A300 confirmed acceptable**

## Performance

- **Duration:** ~90 min (including hardware verification and post-checkpoint fixes)
- **Started:** 2026-06-02
- **Completed:** 2026-06-02
- **Tasks:** 2 (1 auto + 1 checkpoint:human-verify)
- **Files modified:** 4

## Accomplishments

- Created headless end-to-end integration test (`tests/test_ui_integration.py`) that drives the full queue → drain → on_device_update → DeviceCard path without hardware or an asyncio thread; covers create, update-in-place, and second-device cases
- Hardware checkpoint passed: all 8 user-observable Phase 4 behaviors confirmed against real LIGHTSPEED dongle (UI-01, UI-02, UI-03, SYS-01, SYS-02, HID-04 regression, sidebar placeholders, clean tray exit)
- Post-checkpoint fixes applied: sys.path fix for `python -m src`, poll_interval tuned to 2s, HID handle kept open across OFFLINE to allow auto-recovery, percent==0 treated as transient OFFLINE with CHARGING % hidden

## Task Commits

1. **Task 1: Headless integration test** - `0d210b4` (feat)
2. **Task 2: Hardware checkpoint (meta)** - `49db394` (docs)
3. **Post-checkpoint fix: sys.path** - `c8d76f9` (fix)
4. **Post-checkpoint fix: poll_interval + OFFLINE handle** - `c6709b0` (fix)
5. **Post-checkpoint fix: poll_interval 2s** - `556ff87` (fix)

**Plan metadata commit:** (this summary)

## Files Created/Modified

- `tests/test_ui_integration.py` — headless queue-drain-to-DeviceCard integration test; three scenarios (ONLINE 80%, OFFLINE update, second device)
- `src/__main__.py` — added `src/` to `sys.path` for `python -m src` invocation; reduced poll_interval to 2s
- `src/monitor/service.py` — reduced poll_interval to 2s
- `src/monitor/app.py` — keep HID handle open on OFFLINE; treat percent==0 as transient OFFLINE; hide % during CHARGING

## Decisions Made

- **Amber #E5A300 accepted:** User confirmed the placeholder amber hex is visually acceptable during the checkpoint visual review. No styles.py change needed.
- **poll_interval = 2s for dev:** Reduced from 60s to 2s to make state transitions visible during development. Phase 5+ can re-evaluate for production use.
- **Keep handle open on OFFLINE:** Closed handle on OFFLINE previously caused the headset to not recover to ONLINE when powered back on (without replugging dongle). Keeping it open lets the next poll re-detect presence.
- **percent==0 is OFFLINE transient:** A zero-percent reading from the device indicates the headset is off/disconnecting, not truly dead battery. Treat as OFFLINE rather than showing "0%".
- **CHARGING hides %:** During CHARGING status, the percent value is hidden to avoid displaying a potentially stale/misleading reading.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] sys.path missing for `python -m src` invocation**
- **Found during:** Task 2 hardware checkpoint (app launch step)
- **Issue:** Running `.venv-1\Scripts\python -m src` failed because `src/` was not on `sys.path`, causing import errors
- **Fix:** Added `sys.path.insert(0, ...)` for the `src/` directory in `src/__main__.py`
- **Files modified:** `src/__main__.py`
- **Committed in:** `c8d76f9`

**2. [Rule 1 - Bug] poll_interval too high for observable state transitions**
- **Found during:** Task 2 hardware checkpoint (HID-04 hot-plug step)
- **Issue:** 60s poll_interval meant dongle unplug showed OFFLINE quickly but replug recovery took up to 60s — unacceptable for real use
- **Fix:** Reduced poll_interval to 2s in both `service.py` and `__main__.py`
- **Files modified:** `src/monitor/service.py`, `src/__main__.py`
- **Committed in:** `c6709b0`, `556ff87`

**3. [Rule 1 - Bug] HID handle closed on OFFLINE prevented auto-recovery**
- **Found during:** Task 2 hardware checkpoint (HID-04 step — headset power cycle without dongle replug)
- **Issue:** Closing the HID handle when marking OFFLINE meant the next poll couldn't re-open the device (device still enumerated by OS), so headset never recovered to ONLINE when powered back on
- **Fix:** Keep handle open on OFFLINE; let poll_once detect the next successful read and update status to ONLINE
- **Files modified:** `src/monitor/app.py`
- **Committed in:** `c6709b0`

**4. [Rule 1 - Bug] percent==0 shown as valid battery; CHARGING showed stale %**
- **Found during:** Task 2 hardware checkpoint (device card visual review)
- **Issue:** A zero-percent reading is a protocol transient when device is disconnecting, not real battery empty. Showing "0%" to user is misleading. Similarly, showing % during CHARGING can display stale values.
- **Fix:** Treat percent==0 as OFFLINE transient; suppress % display during CHARGING state
- **Files modified:** `src/monitor/app.py`
- **Committed in:** `c6709b0`

---

**Total deviations:** 4 auto-fixed (1 blocking, 3 bugs)
**Impact on plan:** All fixes were necessary for correct user-visible behavior discovered during hardware verification. No scope creep.

## Known Limitation

**State transitions 20-25s on Windows due to hidapi blocking asyncio event loop**

During HID state transitions (particularly unplug → replug recovery), the asyncio event loop can block for 20-25 seconds because `hid.device.read()` calls are synchronous and block the event loop thread. This is a known Windows hidapi behavior.

**Future fix path:** Wrap HID read/write calls with `loop.run_in_executor(None, ...)` to move blocking I/O off the event loop thread. This was acknowledged and deferred — Phase 4 is complete as the behavior is functional, just slower than ideal. The 2s poll_interval ensures recovery happens within one poll cycle once the event loop unblocks.

## Issues Encountered

- App failed to launch via `python -m src` on first hardware test run (sys.path missing) — resolved as deviation fix above
- Tray icon appeared in Windows 11 tray overflow (`^`) not main tray bar — expected behavior per RESEARCH Pitfall 3; no fix needed

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 4 fully complete: all 5 requirements (UI-01, UI-02, UI-03, SYS-01, SYS-02) hardware-verified
- 129 tests pass; dark VOLT theme, device cards, tray, startup persistence all confirmed working
- Phase 5 entry: wire SteelSeries Aerox 5 Wireless raw HID driver into MonitorService; device will appear alongside G Pro X Wireless in the existing UI
- Known limitation (asyncio blocking) should be addressed before Phase 5 adds a second polling device — concurrent blocking reads will compound the delay

---
*Phase: 04-qt-ui-window-tray*
*Completed: 2026-06-02*
