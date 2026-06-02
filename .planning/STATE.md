---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 03
current_plan: 1
status: executing
last_updated: "2026-06-02T16:38:20.179Z"
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 10
  completed_plans: 10
  percent: 43
---

# State: PeriphWatcher

## Project Reference

**Core Value:** Always know the battery level of every wireless peripheral at a glance, without installing bloatware.
**Milestone:** v1.0
**Total Phases:** 7
**Total Requirements:** 12 v1

---

## Current Position

**Current Phase:** 03
**Current Plan:** 1
**Status:** Ready to execute

**Progress:**

[██████████] 100%
Phase: 03 (monitorservice-deviceregistry) — EXECUTING
Plan: 2 of 4
Phase: 03 (MonitorService + DeviceRegistry) — Not started
        1  2  3  4  5  6  7
              ^

```

**Phases complete:** 2/7
**Plans complete:** 7 (across all phases)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 2/7 |
| Requirements delivered | 3/12 (HID-01, BATT-01, BATT-02) |
| Plans written | 6 |
| Plans complete | 7 |
| Blockers outstanding | 0 |

---

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

### Todos

None

### Blockers

- (none)

---

## Session Continuity

**Last session:** 2026-06-02T16:38:20.172Z
**Next action:** Plan Phase 3 (MonitorService + DeviceRegistry) via `/gsd:plan-phase 3`

### Handoff Note

Phase 2 is fully complete. All 4 plans executed and hardware-verified:

- 02-01: Protocol layer + pytest bootstrap
- 02-02: receiver.py (enumerate 0xFF43, open, discover index)
- 02-03: features.py (BatteryResult, battery_probe_chain, voltage calibration)
- 02-04: query_battery.py (integration entry point — hardware proof of life)

Key finding: G Pro X Wireless uses G-series protocol (usage_page=0xFF43, feature 0x06/0x0D), not standard HID++ 2.0 Root discovery. Device index is fixed 0xFF. Headset-off sends HIDppError(0x05), not a timeout.

Phase 3 entry: consume find_receiver + battery_probe_chain from hidpp/ package in a 60s polling loop on asyncio background thread.

---
*Created: 2026-06-01*
*Last updated: 2026-06-01 after roadmap creation*
