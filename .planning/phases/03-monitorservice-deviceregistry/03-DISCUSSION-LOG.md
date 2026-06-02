# Phase 3: MonitorService + DeviceRegistry - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 03-CONTEXT.md.

**Date:** 2026-06-02
**Phase:** 03-monitorservice-deviceregistry
**Mode:** discuss
**Areas discussed:** DeviceState shape, VID/PID known-device registry, Hot-plug reception

---

## Area 1: DeviceState shape

| Question | Options | Choice |
|----------|---------|--------|
| What should a DeviceState entry carry? | Minimal (percent+charging+status) / Full snapshot (identity+battery+status) / Flat (name+percent+charging+status) | **Full snapshot** |
| What status values? | ONLINE/OFFLINE only / ONLINE/OFFLINE/CHARGING / ONLINE/OFFLINE/UNKNOWN | **ONLINE/OFFLINE/CHARGING** |

---

## Area 2: VID/PID known-device registry

| Question | Options | Choice |
|----------|---------|--------|
| How should MonitorService know which dongles to look for? | Hardcoded dict / JSON file / Auto-detect any 0xFF43 | **Hardcoded dict in Python** |

---

## Area 3: Hot-plug reception

| Question | Options | Choice |
|----------|---------|--------|
| Where should WM_DEVICECHANGE live? | Qt main thread / Dedicated ctypes thread / Polling fallback | **Qt main thread** |
| Phase 3 has no real window — what owns the HWND? | Hidden QWidget message sink / QApplication nativeEventFilter / Defer to Phase 4 | **Hidden QWidget as message sink** |

---

## Not discussed (Claude's Discretion)
- DeviceRegistry thread-safety mechanism
- Queue drain interval
- Polling failure mid-session handling
