# Phase 4: Qt UI — Window + Tray - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 04-CONTEXT.md.

**Date:** 2026-06-02
**Phase:** 04-qt-ui-window-tray
**Mode:** discuss
**Areas discussed:** Visual style fidelity, Window structure, Settings persistence scope

---

## Area 1: Visual style fidelity

| Question | Options | Choice |
|----------|---------|--------|
| Apply VOLT theme now or plain UI first? | Apply dark theme now / Plain functional UI first | **Apply dark theme now** |
| Battery gauge in Phase 4? | Circular ring (QPainter) / Horizontal bar / Text only | **Text only** |

---

## Area 2: Window structure

| Question | Options | Choice |
|----------|---------|--------|
| Sidebar layout? | Full skeleton / No sidebar / Active-tabs-only | **Full sidebar skeleton** |

---

## Area 3: Settings persistence scope

| Question | Options | Choice |
|----------|---------|--------|
| What goes in settings JSON? | Startup toggle only / Full schema with placeholders | **Startup toggle only** |

---

## Not discussed (Claude's Discretion)
- Sidebar width and icon/label layout
- Specific icon assets
- Device card grid layout
- Window default size / geometry persistence
- Config file helper implementation
