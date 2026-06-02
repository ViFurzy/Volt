---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 04
current_plan: 1
status: executing
last_updated: "2026-06-02T21:59:10.445Z"
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 14
  completed_plans: 14
  percent: 57
---

# State: PeriphWatcher

## Project Reference

**Core Value:** Always know the battery level of every wireless peripheral at a glance, without installing bloatware.
**Milestone:** v1.0
**Total Phases:** 7
**Total Requirements:** 12 v1

---

## Current Position

**Current Phase:** 04
**Current Plan:** 1
**Status:** Ready to execute

**Progress:**

[██████████] 100%
Phase: 04 (qt-ui-window-tray) — EXECUTING
Plan: 4 of 4
Phase: 04 (qt-ui-window-tray) — Not started
        1  2  3  4  5  6  7
                 ^

**Phases complete:** 3/7
**Plans complete:** 11 (across all phases)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 3/7 |
| Requirements delivered | 5/12 (HID-01, BATT-01, BATT-02, HID-03, HID-04) |
| Plans written | 11 |
| Plans complete | 11 |
| Blockers outstanding | 0 |

---
| Phase 03-monitorservice-deviceregistry P04 | 90 | 2 tasks | 4 files |
| Phase 04-qt-ui-window-tray P01 | 25 | 3 tasks | 4 files |

## Accumulated Context

### Architecture Decisions (locked)

| Decision | Value | Rationale |
|----------|-------|-----------|
| COM initialization | `sys.coinit_flags = 0` first in `__main__` | Prevents STA/MTA conflict between Qt and bleak WinRT |
| Threading model | asyncio loop on daemon background thread; Qt on main thread | Required separation; communicate via queue.Queue only |
| HID interface selection | `usage_page=0xFF00` vendor-specific page | Primary interface locked by Windows; Access Denied otherwise |
| HID++ feature discovery | Runtime via Root feature 0x0000 | Feature indices are firmware-assigned; never hardcode |
| HID++ battery probe order | 0x1004 → 0x1000 → 0x1001 | 0x1004 is newest; fall back in priority order |
| HotPlug debounce | 500ms after WM_DEVICECHANGE | DBT_DEVNODES_CHANGED fires 5-6x per plug event |

### Stack (locked)

| Role | Library | Version |
|------|---------|---------|
| HID | hid (ctypes-hidapi) | 1.0.9 |
| UI + Tray | PySide6 | 6.11.1 |
| Notifications | Windows-Toasts | 1.3.1 |
| Startup | winreg | stdlib |
| Packaging | PyInstaller | 6.17+ |

### Known Risks

| Risk | Phase | Mitigation |
|------|-------|------------|
| SteelSeries exact command bytes unknown until hardware test | Phase 5 | Budget discovery time; reference rivalcfg and HeadsetControl projects |
| G Pro X battery feature variant (0x1000 vs 0x1004) unknown until test | Phase 2 | Probe chain handles all variants |
| PyInstaller entry-point may reorder imports before `sys.coinit_flags` | Phase 7 | Validate import order in packaged exe boot trace |

### Decisions (from Plan 01-01)

- HID interfaces opened exclusively via open_path() after filtering usage_page==0xFF00
- sys.coinit_flags=0 is line 2 of __main__.py with explanatory MTA comment (architecture invariant confirmed)
- hidapi==0.15.0 installed instead of hid==1.0.9 — identical ctypes API, no separate hidapi.dll required

### Decisions (from Phase 2)

- G Pro X Wireless uses G-series protocol (0xFF43 + feature 0x06/0x0D), not HID++ 2.0 Root feature discovery — receiver_device_index is always 0xFF
- battery_probe_chain catches HIDppError (code 0x05) and returns None — device sends error when headset is off, not a timeout
- Voltage-to-percent calibration hardcoded to 6-point curve [3500mV=0%, 3600mV=5%, 3700mV=30%, 3800mV=60%, 3900mV=90%, 4000mV=100%]

### Decisions (from Phase 3)

- MonitorApp does not own QApplication — entry point owns it for testability and Phase 4 handoff compatibility
- SIGINT in Qt event loop requires 200ms heartbeat QTimer to yield to Python signal handler (otherwise Ctrl+C hangs)
- discover() skips already-open HID handles to prevent false ONLINE+None spurious event on WM_DEVICECHANGE during unplug
- stop() cancels _poll_task before stopping the asyncio loop to eliminate "Task was destroyed but it is pending!" warning
- WM_DEVICECHANGE fast path: device marked OFFLINE immediately on unplug (not deferred to next 60s poll)

### Todos

None

### Blockers

- (none)

---

## Session Continuity

**Last session:** 2026-06-02T21:59:10.438Z
**Next action:** Plan Phase 4 (Qt UI — Window + Tray) via `/gsd:plan-phase 4`

### Handoff Note

Phase 3 is fully complete. All 4 plans executed and hardware-verified:

- 03-01: DeviceState, DeviceStatus, KNOWN_DEVICES, thread-safe DeviceRegistry
- 03-02: MonitorService asyncio polling engine (60s interval, discover, poll_once, rescan)
- 03-03: HotPlugWatcher hidden QWidget + RegisterDeviceNotification + 500ms debounce
- 03-04: MonitorApp wiring + run_monitor.py + integration test + hardware end-to-end verified

Key findings from hardware checkpoint (03-04):

- Plug triggers single ONLINE discovery within ~1s (WM_DEVICECHANGE + 500ms debounce works correctly)
- Unplug marks device OFFLINE immediately via WM_DEVICECHANGE fast path
- Ctrl+C exits cleanly (SIGINT + 200ms heartbeat QTimer pattern confirmed)
- All 62 tests pass

Phase 4 entry: replace mock_consumer in run_monitor.py with real PySide6 main window consuming DeviceState snapshots from the same ui_queue. MonitorApp API is stable — Phase 4 adds window/tray shell only.

---
*Created: 2026-06-01*
*Last updated: 2026-06-01 after roadmap creation*
