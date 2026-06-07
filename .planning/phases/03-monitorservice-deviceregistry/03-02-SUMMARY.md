---
phase: 03-monitorservice-deviceregistry
plan: 02
subsystem: api
tags: [python, asyncio, threading, hidpp, queue, monitorservice, polling]

# Dependency graph
requires:
  - phase: 03-01
    provides: DeviceState, DeviceStatus, KNOWN_DEVICES, DeviceRegistry
  - phase: 02-hidpp-20-protocol
    provides: battery_probe_chain, BatteryResult, find_receiver, open_receiver, DEVICE_IDX
provides:
  - MonitorService class with asyncio daemon-thread polling loop
  - discover() — enumerates receiver, filters KNOWN_DEVICES, registers ONLINE DeviceState
  - poll_once() — reads battery, maps charging status, handles mid-session OFFLINE teardown
  - rescan() — thread-safe run_coroutine_threadsafe entry for hot-plug (03-03)
  - find_receiver(verbose=False) — silent background polling (WR-03)
affects:
  - 03-03-HotPlugWatcher (calls rescan() via run_coroutine_threadsafe)
  - 03-04-integration (MonitorService is the core engine)
  - 04-qt-ui (consumes DeviceState snapshots from queue)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.new_event_loop() + threading.Thread(daemon=True) + run_forever() — matches threading_stub.py canonical pattern"
    - "loop.call_soon_threadsafe(loop.stop) + thread.join(timeout=5.0) — clean shutdown sequence"
    - "asyncio.run_coroutine_threadsafe() for main-thread → bg-loop scheduling (rescan)"
    - "self._open dict[tuple[int,int,int], hid.device] keyed by (vid,pid,dev_idx) — handle lifetime management on bg thread"

key-files:
  created:
    - src/monitor/service.py
    - tests/test_service.py
  modified:
    - src/hidpp/receiver.py
    - tests/test_receiver.py

key-decisions:
  - "verbose=False default False for background use; verbose=True default for interactive query_battery.py (WR-03)"
  - "poll_once() removes closed handles immediately on None result — never re-polls a closed handle (T-03-03)"
  - "discover() skips non-KNOWN_DEVICES interfaces without opening or registering (T-03-05)"
  - "rescan() returns Future — 03-03 will wrap with 500ms debounce (D-08)"

patterns-established:
  - "MonitorService._open: all HID handles owned exclusively by bg asyncio coroutines — never accessed from main thread"
  - "Battery→status mapping: charging=True→CHARGING, False+reachable→ONLINE, None→OFFLINE (D-03)"
  - "AST-based test for hid.open() prohibition — more reliable than string grep for docstring-containing source"

requirements-completed: [HID-03, HID-04]

# Metrics
duration: 6min
completed: 2026-06-02
---

# Phase 3 Plan 02: MonitorService Asyncio Polling Engine Summary

**MonitorService on a daemon asyncio thread polls the G Pro X Wireless via battery_probe_chain, pushing full DeviceState snapshots to queue.Queue with ONLINE/CHARGING/OFFLINE status and mid-session handle teardown on None response**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-02T16:22:00Z
- **Completed:** 2026-06-02T16:28:18Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `src/hidpp/receiver.py`: Added `verbose: bool = True` parameter to `find_receiver()` wrapping all three `print()` calls in `if verbose:` guards; background polling uses `find_receiver(verbose=False)` (WR-03)
- `src/monitor/service.py`: Full `MonitorService` class — daemon asyncio thread, `discover()`, `poll_once()`, `rescan()`, `start()`, `stop()` — zero PySide6 imports, zero `hid.open()` calls
- `tests/test_service.py`: 11 unit tests covering all 5 acceptance criteria (discover/poll mapping cases, OFFLINE teardown, unknown device skip, safety invariants)
- Full suite 52/52 passing (no regressions on Phases 1-3 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add verbose flag to find_receiver** - `93db920` (feat)
2. **Task 2: Implement MonitorService asyncio polling engine** - `41c0af3` (feat)

## Files Created/Modified

- `src/monitor/service.py` — MonitorService: asyncio bg-thread polling engine (created)
- `tests/test_service.py` — 11 unit tests for MonitorService discover/poll/safety (created)
- `src/hidpp/receiver.py` — Added verbose=False flag to find_receiver (modified)
- `tests/test_receiver.py` — Added test_find_receiver_silent_when_not_verbose (modified)

## Decisions Made

- **AST-based no-hid-open test**: The string-grep approach in the acceptance criteria matches docstring mentions of `hid.open()`. Used `ast.walk()` instead to check only actual Call nodes — more precise and immune to docstring false positives.
- **Immediate handle teardown on None**: When `battery_probe_chain` returns None, the handle is closed and removed from `self._open` immediately in `poll_once()`. Re-open waits for the next WM_DEVICECHANGE event (T-03-03 mitigation).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AST-based safety test instead of string grep**
- **Found during:** Task 2 (test_no_hid_open_direct_call)
- **Issue:** Plan's acceptance criterion `grep -v '^#' src/monitor/service.py | grep -c 'hid.open('` would have matched the docstring comment `hid device opens use open_receiver() — never hid.open(vid, pid)` — producing a false positive even with no actual call
- **Fix:** Used `ast.parse()` + `ast.walk()` to inspect only Call nodes; also updated service.py docstring to avoid the literal substring `hid.open(` to keep both approaches consistent
- **Files modified:** tests/test_service.py, src/monitor/service.py
- **Committed in:** 41c0af3 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — correctness fix for test false positive)
**Impact on plan:** Minimal — test correctness only. The actual prohibition (no `hid.open()` calls in service logic) is fully enforced.

## Issues Encountered

None beyond the test false-positive noted above.

## User Setup Required

None — no external service configuration required. No new dependencies (stdlib asyncio/threading/queue plus existing hid + hidpp modules).

## Threat Model Compliance

| Threat | Mitigation | Verified |
|--------|------------|---------|
| T-03-03: DoS on dead handle | poll_once() closes handle and removes from self._open on None result | test_none_result_marks_offline_and_removes_handle passes |
| T-03-04: HID handle cross-thread | All HID I/O in coroutines on self._loop; rescan() only schedules onto loop | AST scan confirms no hid calls outside coroutines |
| T-03-05: Unknown VID/PID spoofing | discover() checks (vid,pid) in KNOWN_DEVICES before open | test_skips_unknown_vid_pid passes |
| T-03-SC: No new pip installs | stdlib asyncio/threading/queue only | Confirmed |

## Next Phase Readiness

- `MonitorService.rescan()` is the thread-safe entry point for 03-03 (HotPlugWatcher WM_DEVICECHANGE callback)
- `service.start()` / `service.stop()` lifecycle is complete and tested
- Phase 4 Qt UI wires `QTimer.drain_queue()` to consume DeviceState snapshots from the queue

---
*Phase: 03-monitorservice-deviceregistry*
*Completed: 2026-06-02*
