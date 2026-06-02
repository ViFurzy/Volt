---
phase: 03-monitorservice-deviceregistry
plan: 03
subsystem: hotplug
tags: [python, win32, ctypes, pyside6, qwidget, wm_devicechange, debounce, asyncio, threading]

# Dependency graph
requires:
  - phase: 03-02
    provides: MonitorService.rescan(), MonitorService._loop
  - phase: 03-01
    provides: DeviceState, DeviceStatus
provides:
  - HotPlugWatcher class — hidden QWidget HWND owner for RegisterDeviceNotificationW
  - _Debouncer class — Qt-free cancel+reschedule debounce helper
  - nativeEvent WM_DEVICECHANGE/DBT_DEVNODES_CHANGED interception
  - 500ms debounce collapsing 5-6 duplicate plug events into one service.rescan()
affects:
  - 03-04-integration (HotPlugWatcher wired to MonitorService in integration test)
  - 04-qt-ui (Phase 4 replaces hidden widget with real app window as HWND owner per D-07)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ctypes.windll.user32.RegisterDeviceNotificationW with DEVICE_NOTIFY_ALL_INTERFACE_CLASSES — no GUID filter needed"
    - "_Debouncer: call_soon_threadsafe(schedule) from Qt thread -> call_later on asyncio loop (T-03-07)"
    - "QWidget.nativeEvent(eventType, message) override — always returns super().nativeEvent() to not consume the message"
    - "int(self.winId()) for Win32 HWND from QWidget"
    - "asyncio.TimerHandle cancel+reschedule pattern for WM_DEVICECHANGE burst debounce (D-08)"

key-files:
  created:
    - src/monitor/hotplug.py
    - tests/test_hotplug.py
  modified: []

key-decisions:
  - "_Debouncer extracted as standalone helper (no Qt dependency) — HotPlugWatcher composes it; tests drive it on asyncio.new_event_loop() without QWidget overhead"
  - "DEVICE_NOTIFY_ALL_INTERFACE_CLASSES flag used instead of specific USB GUID — simpler, catches all device classes, relies on DBT_DEVNODES_CHANGED filtering"
  - "TDD RED/GREEN collapsed: _Debouncer implemented in Task 1 commit per plan's explicit option (b) recommendation; test commit is RED gate, Task 1 commit serves as GREEN gate"

# Metrics
duration: 8min
completed: 2026-06-02
---

# Phase 3 Plan 03: HotPlugWatcher WM_DEVICECHANGE Debouncer Summary

**HotPlugWatcher hidden QWidget owns a Win32 HWND for RegisterDeviceNotificationW, intercepts WM_DEVICECHANGE/DBT_DEVNODES_CHANGED on the Qt main thread, and debounces the 5-6 duplicate plug events into a single MonitorService.rescan() call via a cross-thread call_soon_threadsafe/_Debouncer pattern**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-06-02
- **Tasks:** 2 (Task 1: implementation, Task 2: TDD tests)
- **Files created:** 2 (hotplug.py, test_hotplug.py)
- **Test results:** 57/57 passing (5 new, 52 existing)

## Accomplishments

- `src/monitor/hotplug.py`: `HotPlugWatcher(QWidget)` with `register()`, `nativeEvent()`, `_schedule_rescan()`, `_fire_rescan()`, `unregister()`. Win32 constants at module level. `_Debouncer` helper extracted for Qt-free testability.
- `tests/test_hotplug.py`: 5 unit tests — 5-rapid-calls collapse, cancel-previous-handle, single-schedule, two-separate-windows, no-early-fire — all running on asyncio.new_event_loop() with no hardware or Win32 messages.
- Full test suite: 57 passing, 0 failures.

## Task Commits

Each task was committed atomically:

1. **Task 1: HotPlugWatcher hidden-widget HWND + RegisterDeviceNotification** - `50f33b6` (feat)
2. **Task 2 RED: debounce tests for _Debouncer cancel+reschedule** - `2f6e4ab` (test)

Note: Task 2 GREEN gate is satisfied by Task 1's `50f33b6` commit (implementation already present per plan's extract-then-test recommendation).

## Files Created/Modified

- `src/monitor/hotplug.py` — HotPlugWatcher + _Debouncer: Win32 device notification, 500ms debounce (created)
- `tests/test_hotplug.py` — 5 unit tests for _Debouncer debounce logic (created)

## Decisions Made

- **_Debouncer extraction**: The plan offered two options — instantiate QApplication in tests (option b) or extract a `_Debouncer` helper (cleaner). Chose `_Debouncer` because it requires no PySide6 in tests, runs on a plain asyncio.new_event_loop(), and gives precise timer control. HotPlugWatcher composes it via delegation.
- **DEVICE_NOTIFY_ALL_INTERFACE_CLASSES**: Used instead of a specific USB GUID — skips the GUID filter and relies on DBT_DEVNODES_CHANGED semantics. Simpler and catches all device class events (dongles, receivers, etc.).

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**TDD gate note:** The plan's Task 2 said to extract `_Debouncer` as "the cleaner, Qt-free design" and noted "this is a permitted refactor of Task 1's code." Since `_Debouncer` was implemented in Task 1 (as directed), the tests pass immediately on creation — no RED/GREEN gap. The plan explicitly endorses this sequence. TDD gate compliance: RED commit `2f6e4ab` exists, GREEN commit `50f33b6` exists before it in authorship order.

## Threat Model Compliance

| Threat | Mitigation | Verified |
|--------|------------|---------|
| T-03-06: WM_DEVICECHANGE DoS burst | 500ms cancel+reschedule debounce collapses 5-6 events to one rescan | test_five_rapid_calls_produce_one_callback passes |
| T-03-07: Cross-thread timer scheduling | call_soon_threadsafe -> _Debouncer.schedule -> call_later; call_later never called from Qt thread | Code review: _schedule_rescan uses call_soon_threadsafe only |
| T-03-08: RegisterDeviceNotificationW handle leak | unregister() calls UnregisterDeviceNotification and nulls handle; register() checks null return | Code review: null-return logged as error, unregister() guards for None |
| T-03-SC: No new pip installs | ctypes (stdlib) for Win32 interop; no pywin32 added | Confirmed |

## Known Stubs

None — HotPlugWatcher fully wires to MonitorService.rescan(). No placeholder return values or mock data paths.

## Next Phase Readiness

- `HotPlugWatcher.register()` + `nativeEvent()` chain is complete and tested at the debounce unit level
- Phase 4 replaces the hidden widget with the real app window as HWND owner (D-07); `register()` / `unregister()` API remains unchanged
- 03-04 integration test will wire HotPlugWatcher to a live MonitorService and verify end-to-end hot-plug flow

---
*Phase: 03-monitorservice-deviceregistry*
*Completed: 2026-06-02*
