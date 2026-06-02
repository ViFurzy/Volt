---
phase: 03-monitorservice-deviceregistry
plan: 04
subsystem: api
tags: [python, pyside6, qtimer, queue, asyncio, threading, integration, coinit]

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
  - drain() method: queue.Queue → consumer callback on Qt main thread (QTimer-driven)
  - make_timer(): QTimer.timeout → drain at 500ms cadence
  - build_hotplug(): constructs and registers HotPlugWatcher after QApplication exists
  - run_monitor.py: standalone Phase 3 entry point with sys.coinit_flags = 0 guard
  - mock_consumer: print-based Phase 3 stand-in for Phase 4 device-card UI

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

key-files:
  created:
    - src/monitor/app.py
    - src/run_monitor.py
    - tests/test_integration.py
  modified: []

key-decisions:
  - "MonitorApp does not call sys.coinit_flags — that belongs only in the entry point (CLAUDE.md invariant)"
  - "make_timer() and build_hotplug() return their objects; entry point holds references (T-03-11 GC guard)"
  - "Integration tests drive drain() directly without Qt or hardware — bg thread covered by test_service.py"
  - "drain_ms=500 default matches threading_stub.py cadence (CONTEXT D-08)"

patterns-established:
  - "Entry point owns QApplication + explicit timer/hotplug references; MonitorApp owns service/registry"
  - "Integration tests: ui_queue.put() → drain() → consumer list — no Qt event loop required"

requirements-completed: [HID-03, HID-04]

# Metrics
duration: 10min
completed: 2026-06-02
---

# Phase 3 Plan 04: MonitorApp Integration Wiring Summary

**MonitorApp wires MonitorService + DeviceRegistry + HotPlugWatcher behind a QTimer-drained queue.Queue pipe to a consumer callback, with run_monitor.py entry point preserving sys.coinit_flags=0 before all imports; hardware checkpoint pending**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-02T16:35:00Z
- **Completed:** 2026-06-02T16:45:00Z
- **Tasks:** 1 of 2 executed (Task 2 is hardware checkpoint — awaiting user verification)
- **Files modified:** 3 created

## Accomplishments

- `src/monitor/app.py`: `MonitorApp` class wires all Phase 3 components; `drain()` loops `get_nowait()` → consumer until `queue.Empty`; `make_timer()` and `build_hotplug()` return references the entry point must keep alive (T-03-11); no HID I/O in this file
- `src/run_monitor.py`: standalone entry point; `sys.coinit_flags = 0` on line 2 before all imports (T-03-09 mitigated); `mock_consumer` prints device_name/percent/status/charging; clean shutdown mirrors threading_stub pattern
- `tests/test_integration.py`: 5 tests — FIFO delivery, queue-empty-after-drain, empty-queue-no-raise, OFFLINE forwarding, multi-cycle drain; 62/62 full suite passing

## Task Commits

Each task was committed atomically:

1. **Task 1: MonitorApp wiring + run_monitor.py entry point + integration test** - `83e92fc` (feat)

_Task 2 is a hardware checkpoint — not a code commit._

## Files Created/Modified

- `src/monitor/app.py` — MonitorApp: wiring layer + drain + make_timer + build_hotplug (created)
- `src/run_monitor.py` — Phase 3 standalone entry point with coinit guard + mock_consumer (created)
- `tests/test_integration.py` — 5 queue-pipe integration tests (created)

## Decisions Made

- **MonitorApp does not own QApplication**: Entry point creates `QApplication([])`; `MonitorApp.__init__` only creates `queue.Queue`, `DeviceRegistry`, and `MonitorService`. This keeps the wiring class testable without a display server and matches the Phase 4 handoff (Phase 4 will own the real `QApplication`).
- **Explicit timer/hotplug reference return**: `make_timer()` and `build_hotplug()` both return their objects so the entry point keeps references. If the caller discards them, GC silently disables queue drain / hot-plug (T-03-11). Returning forces the caller to decide.
- **Integration tests drive drain() directly**: No `QApplication` needed in tests — `drain()` is a pure Python loop over `queue.Queue`. This isolates the drain/consumer contract without requiring a display environment.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Tests passed on first run.

## User Setup Required

None — no new dependencies. PySide6, hid, stdlib queue/threading only.

## Threat Model Compliance

| Threat | Mitigation | Verified |
|--------|------------|---------|
| T-03-09: coinit_flags import order | run_monitor.py line 2 is `sys.coinit_flags = 0` before all imports | Automated check passes: `python -c "... assert t[1].strip().startswith('sys.coinit_flags = 0')"` |
| T-03-10: bg thread never joined | stop() delegates to MonitorService.stop() which calls loop.call_soon_threadsafe(stop) + thread.join(timeout=5) | Inherited from 03-02 verified implementation |
| T-03-11: hotplug/timer GC'd | build_hotplug() and make_timer() return objects; run_monitor.py keeps explicit references | Code review confirms `hotplug = app_obj.build_hotplug()` and `timer = app_obj.make_timer()` |

## Known Stubs

- `mock_consumer` in `run_monitor.py` — prints DeviceState to stdout. This is the intentional Phase 3 stand-in; Phase 4 replaces it with the real device-card UI update.

## Next Phase Readiness

- Task 2 (hardware checkpoint) awaits user verification of plug/unplug/offline/shutdown behavior on the real G Pro X Wireless dongle
- Phase 4 entry: replace `mock_consumer` reference with a `MonitorApp` consumer wired to the device-card `QWidget`; `MonitorApp` API is stable

---
*Phase: 03-monitorservice-deviceregistry*
*Completed: 2026-06-02 (Task 1 only; Task 2 hardware checkpoint pending)*
