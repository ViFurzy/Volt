# State: PeriphWatcher

## Project Reference

**Core Value:** Always know the battery level of every wireless peripheral at a glance, without installing bloatware.
**Milestone:** v1.0
**Total Phases:** 7
**Total Requirements:** 12 v1

---

## Current Position

**Current Phase:** 2 — HID++ 2.0 Protocol
**Current Plan:** None started
**Status:** Phase 1 complete — ready for Phase 2

**Progress:**
```
Phase: [✓][2][ ][ ][ ][ ][ ]
        1  2  3  4  5  6  7
           ^
```

**Phases complete:** 1/7
**Plans complete:** 2 (across all phases)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 1/7 |
| Requirements delivered | 0/12 |
| Plans written | 2 |
| Plans complete | 2 |
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

### Todos

- Run hid_poc.py with LIGHTSPEED dongle plugged in to confirm no Access Denied and verify exact PID

### Blockers

- (none)

---

## Session Continuity

**Last session:** 2026-06-01 — Phase 1 complete
**Next action:** `/gsd:plan-phase 2` — plan Phase 2: HID++ 2.0 Protocol

### Handoff Note

Phase 1 complete. Both architecture risks resolved:
1. ✓ HID access via usage_page=0xFF00 confirmed on real hardware (PRO X Wireless Headset, PID=0x0ABA)
2. ✓ sys.coinit_flags=0 invariant enforced in both __main__.py and threading_stub.py
3. ✓ asyncio + queue.Queue + QTimer threading pattern proven end-to-end

Phase 2 focus: HID++ 2.0 protocol. Read battery from Logitech G Pro X Wireless.
Key: probe feature chain 0x1004 → 0x1000 → 0x1001. Discover device index at runtime via Root feature 0x0000.

---
*Created: 2026-06-01*
*Last updated: 2026-06-01 after roadmap creation*
