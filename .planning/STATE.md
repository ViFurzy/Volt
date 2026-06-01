# State: PeriphWatcher

## Project Reference

**Core Value:** Always know the battery level of every wireless peripheral at a glance, without installing bloatware.
**Milestone:** v1.0
**Total Phases:** 7
**Total Requirements:** 12 v1

---

## Current Position

**Current Phase:** 1 — HID Connectivity PoC
**Current Plan:** None started
**Status:** Not started

**Progress:**
```
Phase: [1][ ][ ][ ][ ][ ][ ]
        1  2  3  4  5  6  7
        ^
```

**Phases complete:** 0/7
**Plans complete:** 0 (across all phases)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 0/7 |
| Requirements delivered | 0/12 |
| Plans written | 0 |
| Plans complete | 0 |
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

### Todos

- (none yet)

### Blockers

- (none)

---

## Session Continuity

**Last session:** 2026-06-01 — Roadmap created
**Next action:** `/gsd:plan-phase 1` — plan Phase 1: HID Connectivity PoC

### Handoff Note

Start with Phase 1. The primary deliverable is not just a working script — it is proof that the two critical architecture risks are resolved before any protocol work begins:
1. HID Access Denied pitfall (usage_page=0xFF00 selection)
2. COM threading invariant (sys.coinit_flags=0 position)

Phase 2 may not begin until Phase 1 has confirmed both.

---
*Created: 2026-06-01*
*Last updated: 2026-06-01 after roadmap creation*
