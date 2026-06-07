---
phase: 03-monitorservice-deviceregistry
plan: 01
subsystem: database
tags: [python, dataclass, enum, threading, hidpp, device-registry]

# Dependency graph
requires:
  - phase: 02-hidpp-20-protocol
    provides: BatteryResult dataclass shape and LOGITECH_VID/DEVICE_IDX constants referenced in DeviceState design
provides:
  - DeviceState snapshot dataclass with 7 locked fields (vid, pid, dev_idx, device_name, percent, charging, status)
  - DeviceStatus enum with ONLINE/OFFLINE/CHARGING members
  - KNOWN_DEVICES hardcoded dict mapping (0x046D, 0x0ABA) to "G Pro X Wireless"
  - DeviceRegistry thread-safe store with upsert/get/all/mark_offline
affects:
  - 03-02-MonitorService (imports DeviceState, DeviceStatus, DeviceRegistry)
  - 03-03-HotPlugWatcher (uses mark_offline teardown primitive)
  - 03-04-integration (consumes full registry + queue pipe)
  - 04-qt-ui (reads DeviceState from queue to populate device cards)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "threading.Lock around plain dict for cross-thread shared state"
    - "dataclasses.replace() for immutable snapshot updates"
    - "KNOWN_DEVICES hardcoded dict (no config file) until multi-user customisation needed"

key-files:
  created:
    - src/monitor/__init__.py
    - src/monitor/state.py
    - src/monitor/registry.py
    - tests/test_registry.py
  modified: []

key-decisions:
  - "DeviceRegistry uses threading.Lock around a plain dict (simplest model matching threading_stub.py pattern)"
  - "KNOWN_DEVICES is a hardcoded Python dict — no config file or JSON loader (D-04 deferral)"
  - "device_name comes from KNOWN_DEVICES lookup, not hid.enumerate product_string (D-05 stability invariant)"
  - "mark_offline uses dataclasses.replace() to produce immutable updated snapshot, not in-place mutation"

patterns-established:
  - "DeviceState: always a full snapshot — consumers never merge deltas (D-02)"
  - "Registry all() returns list copy, not live view — safe to iterate without holding the lock"
  - "All DeviceRegistry methods use 'with self._lock' for their entire body"

requirements-completed: [HID-03]

# Metrics
duration: 3min
completed: 2026-06-02
---

# Phase 3 Plan 01: DeviceState, DeviceStatus, KNOWN_DEVICES, and DeviceRegistry Summary

**Thread-safe DeviceRegistry keyed by (vid, pid, dev_idx) storing immutable DeviceState snapshots, with hardcoded KNOWN_DEVICES dict and three-member DeviceStatus enum as the locked Phase 3 data-model contract**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-02T16:22:11Z
- **Completed:** 2026-06-02T16:22:46Z
- **Tasks:** 2 (TDD)
- **Files modified:** 4 created

## Accomplishments

- `src/monitor/state.py`: DeviceState dataclass (7 locked D-01 fields), DeviceStatus enum (3 D-03 members), KNOWN_DEVICES with G Pro X Wireless entry (D-04/D-05)
- `src/monitor/registry.py`: thread-safe DeviceRegistry with threading.Lock; upsert/get/all/mark_offline; all() returns snapshot copy per T-03-01 mitigation
- `tests/test_registry.py`: 15 tests covering all behavior including a multi-threaded concurrency test (10 threads x 100 upserts, unique dev_idx per thread)
- Full suite 40/40 passing (no regressions on Phase 2 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — Failing tests** - `0662c34` (test)
2. **Task 1+2: GREEN — Implementation** - `3ace398` (feat)

_Note: TDD tasks combined into a single GREEN commit because test_registry.py imports both monitor.state and monitor.registry at the top-level — the tests could not be collected until both modules existed._

## Files Created/Modified

- `src/monitor/__init__.py` — Package marker with cross-thread invariant docstring
- `src/monitor/state.py` — DeviceState, DeviceStatus, KNOWN_DEVICES (D-01/D-03/D-04/D-05)
- `src/monitor/registry.py` — DeviceRegistry thread-safe store (T-03-01 mitigated)
- `tests/test_registry.py` — 15 unit tests including concurrency test

## Decisions Made

- **threading.Lock around plain dict**: Matches the threading_stub.py pattern. No asyncio locks (DeviceRegistry must be safe from both bg thread and main thread).
- **dataclasses.replace() in mark_offline**: Produces an immutable snapshot copy rather than mutating the stored object in-place — consistent with D-02 (snapshots, not diffs).
- **Test file imports both modules at module level**: Required splitting RED into a partial failure (collection error) rather than individual test failures — documented in Task Commits above.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Tests collected cleanly once both modules existed; threading.Lock concurrency test passed on first run.

## User Setup Required

None — no external service configuration required. Only stdlib modules used (enum, dataclasses, threading).

## Threat Model Compliance

| Threat | Mitigation | Verified |
|--------|------------|---------|
| T-03-01: Tampering via concurrent dict access | All 4 DeviceRegistry methods use `with self._lock` | Grep confirms 4 lock usages; concurrency test passes |
| T-03-SC: No new pip installs | stdlib only (enum, dataclasses, threading) | Confirmed |

## Next Phase Readiness

- `src/monitor/state.py` and `src/monitor/registry.py` are ready to import in 03-02 (MonitorService)
- `mark_offline` is the teardown primitive for 03-03 (HotPlugWatcher unplug path)
- Phase 5 SteelSeries entry: append `(0x1038, <pid>): "SteelSeries Aerox 5 Wireless"` to KNOWN_DEVICES

---
*Phase: 03-monitorservice-deviceregistry*
*Completed: 2026-06-02*
