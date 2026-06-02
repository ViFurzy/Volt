---
phase: 03-monitorservice-deviceregistry
plan: 04
subsystem: api
tags: [python, pyside6, qtimer, queue, asyncio, threading, integration, coinit, sigint, hotplug]

# Dependency graph
requires:
  - phase: 03-01
    provides: DeviceState, DeviceStatus, KNOWN_DEVICES, DeviceRegistry
  - phase: 03-02
    provides: MonitorService.start/stop/rescan, asyncio polling loop
  - phase: 03-03
    provides: HotPlugWatcher.register/unregister, WM_DEVICECHANGE debounce

provides:
  - MonitorApp class: single wiring point for MonitorService + DeviceRegistry + HotPlugWatcher
  - drain() method: queue.Queue -> consumer callback on Qt main thread (QTimer-driven)
  - make_timer(): QTimer.timeout -> drain at 500ms cadence
  - build_hotplug(): constructs and registers HotPlugWatcher after QApplication exists
  - run_monitor.py: standalone Phase 3 entry point with sys.coinit_flags = 0 guard
  - mock_consumer: print-based Phase 3 stand-in for Phase 4 device-card UI
  - Hardware-verified: plug ONLINE within 1s, battery reads, unplug OFFLINE immediate, clean Ctrl+C

affects:
  - 04-qt-ui (Phase 4 replaces mock_consumer with real device-card UI; MonitorApp API unchanged)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MonitorApp does not own QApplication — entry point owns it (separation of concerns)"
    - "QTimer reference kept by entry point to prevent GC (T-03-11)"
    - "HotPlugWatcher reference kept by entry point to prevent GC before events arrive (T-03-11)"
    - "sys.coinit_flags = 0 on line 2 of entry point, before all other imports (T-03-09)"
    - "SIGINT + 200ms heartbeat QTimer: allows Python signal handler to fire inside Qt event loop"

key-files:
  created:
    - src/monitor/app.py
    - src/run_monitor.py
    - tests/test_integration.py
  modified:
    - src/monitor/service.py

key-decisions:
  - "MonitorApp does not call sys.coinit_flags — that belongs only in the entry point (CLAUDE.md invariant)"
  - "make_timer() and build_hotplug() return their objects; entry point holds references (T-03-11 GC guard)"
  - "Integration tests drive drain() directly without Qt or hardware — bg thread covered by test_service.py"
  - "drain_ms=500 default matches threading_stub.py cadence"
  - "SIGINT handler requires 200ms heartbeat QTimer so Python signal fires inside Qt event loop"
  - "discover() skips already-open handles to prevent false ONLINE+None on WM_DEVICECHANGE"
  - "stop() cancels _poll_task before stopping the asyncio loop (eliminates 'Task was destroyed' warning)"
  - "WM_DEVICECHANGE fast path: OFFLINE marked immediately on unplug, not deferred to next poll"

patterns-established:
  - "Entry point owns QApplication + explicit timer/hotplug references; MonitorApp owns service/registry"
  - "Integration tests: ui_queue.put() -> drain() -> consumer list — no Qt event loop required"

requirements-completed: [HID-03, HID-04]

# Metrics
duration: ~90min (including hardware verification round-trip)
completed: 2026-06-02
---

# Phase 3 Plan 04: MonitorApp Integration Wiring Summary

**Full Phase 3 stack hardware-verified: MonitorApp wires service + registry + hotplug behind a QTimer-drained queue pipe; plug triggers single ONLINE within ~1s, battery reads, unplug flips OFFLINE immediately, Ctrl+C exits cleanly with no asyncio warnings**

## Performance

- **Duration:** ~90 min (including hardware checkpoint round-trip)
- **Started:** 2026-06-02T16:35:00Z
- **Completed:** 2026-06-02
- **Tasks:** 2 (Task 1: implementation; Task 2: hardware checkpoint approved)
- **Files modified:** 4 (3 created, 1 modified with post-checkpoint fixes)

## Accomplishments

- `src/monitor/app.py`: `MonitorApp` class wires all Phase 3 components; `drain()` loops `get_nowait()` -> consumer until `queue.Empty`; `make_timer()` and `build_hotplug()` return references the entry point must keep alive (T-03-11); no HID I/O in this file
- `src/run_monitor.py`: standalone entry point; `sys.coinit_flags = 0` on line 2 before all imports (T-03-09 mitigated); `mock_consumer` prints device_name/percent/status/charging; SIGINT handler + 200ms heartbeat for clean Ctrl+C; clean shutdown mirrors threading_stub pattern
- `tests/test_integration.py`: 5 tests — FIFO delivery, queue-empty-after-drain, empty-queue-no-raise, OFFLINE forwarding, multi-cycle drain; 62/62 full suite passing
- Hardware checkpoint: all 5 scenarios passed on real G Pro X Wireless dongle

## Task Commits

1. **Task 1: MonitorApp wiring + run_monitor.py entry point + integration test** - `83e92fc` (feat)

_Task 2 hardware checkpoint approved. Post-checkpoint fixes applied:_

- `d842d20` — SIGINT handler + 200ms heartbeat timer for Ctrl+C in Qt loop
- `700b52d` — discover() skips already-open handles (no false ONLINE+None on WM_DEVICECHANGE)
- `db92152` — fast unplug detection (OFFLINE immediately on WM_DEVICECHANGE) + stop() cancels _poll_task cleanly

**Plan metadata:** *(this commit)*

## Hardware Checkpoint Results (Task 2)

All 5 hardware scenarios passed on real G Pro X Wireless hardware:

| # | Scenario | Result |
|---|----------|--------|
| 1 | No dongle — start | Clean start, no crash, no traceback |
| 2 | Plug in (headset ON) | ONLINE within ~1s; battery % read within 60s; single discovery (debounce collapses 5-6 WM_DEVICECHANGE events) |
| 3 | Unplug dongle | OFFLINE appeared immediately via WM_DEVICECHANGE fast path (not deferred to next poll) |
| 4 | Plug back in | ONLINE again, polling resumed |
| 5 | Ctrl+C | Clean exit, no "Task was destroyed" warning |

## Files Created/Modified

- `src/monitor/app.py` — MonitorApp: wiring layer + drain + make_timer + build_hotplug (created)
- `src/run_monitor.py` — Phase 3 standalone entry point with coinit guard + mock_consumer + SIGINT handler (created)
- `tests/test_integration.py` — 5 queue-pipe integration tests (created)
- `src/monitor/service.py` — Bug fixes: skip open handles, fast OFFLINE on unplug, clean _poll_task cancellation (modified)

## Decisions Made

- **MonitorApp does not own QApplication**: Entry point creates `QApplication([])`; `MonitorApp.__init__` only creates `queue.Queue`, `DeviceRegistry`, and `MonitorService`. This keeps the wiring class testable without a display server and matches the Phase 4 handoff.
- **Explicit timer/hotplug reference return**: `make_timer()` and `build_hotplug()` both return their objects so the entry point keeps references. If the caller discards them, GC silently disables queue drain / hot-plug (T-03-11).
- **Integration tests drive drain() directly**: No `QApplication` needed in tests — `drain()` is a pure Python loop over `queue.Queue`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SIGINT (Ctrl+C) had no effect inside Qt event loop**
- **Found during:** Task 2 hardware checkpoint (step 5)
- **Issue:** Qt's `exec()` event loop does not yield to Python's signal handler without a periodic wakeup. Pressing Ctrl+C appeared to hang.
- **Fix:** Added `signal.signal(SIGINT, lambda *_: qapp.quit())` + a 200ms `QTimer` heartbeat so the Python handler fires reliably.
- **Files modified:** `src/run_monitor.py`
- **Verification:** Ctrl+C exited cleanly with no hang or warning (hardware checkpoint step 5 confirmed)
- **Committed in:** `d842d20`

**2. [Rule 1 - Bug] False ONLINE+None update on WM_DEVICECHANGE during unplug**
- **Found during:** Task 2 hardware checkpoint (steps 3/4)
- **Issue:** `discover()` was opening handles already held open by the polling loop. On WM_DEVICECHANGE (unplug), the rescan re-opened the same interface and immediately found it gone, producing a spurious ONLINE event with `percent=None` before the OFFLINE update.
- **Fix:** `discover()` now checks if a handle is already open for a given path and skips it.
- **Files modified:** `src/monitor/service.py`
- **Verification:** Unplug produced a single clean OFFLINE update (hardware checkpoint confirmed)
- **Committed in:** `700b52d`

**3. [Rule 1 - Bug] Device not marked OFFLINE immediately on unplug — waited for next poll**
- **Found during:** Task 2 hardware checkpoint (step 3)
- **Issue:** `rescan()` called by HotPlugWatcher on unplug only discovered new devices; it did not fast-path mark known devices as OFFLINE when their handle was gone.
- **Fix:** Added fast-path logic in `discover()` / `rescan()` to mark devices OFFLINE immediately when WM_DEVICECHANGE fires and the handle is no longer accessible.
- **Files modified:** `src/monitor/service.py`
- **Verification:** OFFLINE appeared immediately on unplug, not deferred to next 60s poll (hardware confirmed)
- **Committed in:** `db92152`

**4. [Rule 1 - Bug] "Task was destroyed but it is pending!" asyncio warning on exit**
- **Found during:** Task 2 hardware checkpoint (step 5)
- **Issue:** `stop()` was calling `loop.stop()` before cancelling `_poll_task`. The asyncio loop exited while the poll task was still in-flight, triggering the warning.
- **Fix:** `stop()` now cancels `_poll_task` and waits for it to finish before stopping the loop.
- **Files modified:** `src/monitor/service.py`
- **Verification:** Ctrl+C exit showed no asyncio warnings (hardware confirmed)
- **Committed in:** `db92152`

---

**Total deviations:** 4 auto-fixed (4 x Rule 1 bugs — all surfaced by hardware checkpoint)
**Impact on plan:** All fixes correctness issues, no scope creep. Post-fix test suite: 62/62 passing.

## Issues Encountered

None beyond the auto-fixed bugs above. The plan's queue pipe architecture and threading model worked as designed on first attempt; issues were edge cases in signal handling and handle lifecycle.

## Threat Model Compliance

| Threat | Mitigation | Verified |
|--------|------------|---------|
| T-03-09: coinit_flags import order | run_monitor.py line 2 is `sys.coinit_flags = 0` before all imports | Automated check: `python -c "... assert t[1].strip().startswith('sys.coinit_flags = 0')"` passes |
| T-03-10: bg thread never joined | stop() cancels _poll_task then calls loop.call_soon_threadsafe(stop) + thread.join(timeout=5) | Hardware checkpoint step 5: clean exit confirmed |
| T-03-11: hotplug/timer GC'd | build_hotplug() and make_timer() return objects; run_monitor.py keeps explicit references | Code review + hardware checkpoint: no spurious GC during session |

## Known Stubs

- `mock_consumer` in `run_monitor.py` — prints DeviceState to stdout. Intentional Phase 3 stand-in; Phase 4 replaces it with the real device-card UI update.

## User Setup Required

None — no new dependencies. PySide6, hid, stdlib queue/threading/signal only.

## Next Phase Readiness

Phase 3 is fully complete. All 4 plans executed and hardware-verified:

- 03-01: DeviceState, DeviceStatus, KNOWN_DEVICES, thread-safe DeviceRegistry
- 03-02: MonitorService asyncio polling engine (60s interval, discover, poll_once, rescan)
- 03-03: HotPlugWatcher hidden QWidget + RegisterDeviceNotification + 500ms debounce
- 03-04: MonitorApp wiring + run_monitor.py + integration test + hardware end-to-end verified

Phase 4 entry: replace `mock_consumer` reference with a `MonitorApp` consumer wired to a real device-card `QWidget`. `MonitorApp` API is stable — Phase 4 only adds the window/tray shell.

---
*Phase: 03-monitorservice-deviceregistry*
*Completed: 2026-06-02*
