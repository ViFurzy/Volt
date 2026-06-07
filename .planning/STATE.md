---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 8
current_plan: Not started
status: ready
last_updated: "2026-06-07T00:25:00.000Z"
progress:
  total_phases: 8
  completed_phases: 7
  total_plans: 35
  completed_plans: 25
  percent: 88
---

# State: Volt

## Project Reference

**Core Value:** Always know the battery level of every wireless peripheral at a glance, without installing bloatware.
**Milestone:** v1.0
**Total Phases:** 7
**Total Requirements:** 12 v1

---

## Current Position

**Current Phase:** 8
**Current Plan:** Not started
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

### Decisions (from Bluetooth & UI Fixes)

- BLE MAC address parsing supports both BTHLE/BTHLEDevice raw hex (12-char) and standard colon-separated formats.
- Bluetooth and BLE battery levels resolved generically by mapping the Association Endpoint to its physical DEVICE container and querying its cached properties.
- Safely cast WinRT properties (handling primitive integers, GUIDs, and booleans) via custom `_get_winrt_prop` helper to prevent python truthiness issues.
- Bluetooth status polling moved to a dedicated secondary background loop running every 5 seconds, combined with immediate polling on hotplug events, ensuring disconnections/connections update UI instantly.
- UI drag-and-drop utilizes IgnoreAction in dropEvent to prevent double-deletion and model index corruption in QListWidgets.

### Decisions (from Phase 5 & Bug Fixes)

- MonitorService.stop() converted to async coroutine, awaiting asyncio.gather on cancelled tasks before stopping loop (BUG-01). Guards prevent RuntimeError on never-started service instances.
- KnownDevicesDict is cached in memory. It invalidates and reads from config only when the config save generation counter increments, eliminating high disk I/O on the background thread poll cycle (BUG-02, BUG-08).
- UI monitored devices cache built using the same generation tracking mechanism, eliminating disk I/O on the UI thread's queue drain tick (BUG-04).
- QGraphicsOpacityEffect is created once in DeviceCard.__init__ and updated in-place via setOpacity(), eliminating Qt object allocation churn per poll cycle (BUG-05).
- Background scan probe skips temp-handle opens for unmonitored devices, returning percent=None to prevent double-open conflicts on Windows (BUG-03).

### Decisions (from Battery History Graph - FEAT-01)

- Battery history data is saved in config JSON, debounced by suppressing consecutive identical percentages unless 10 minutes have elapsed, and capped to the last 200 items per device.
- HistoryPage displays a single-device history graph without tabs. HistoryGraph uses QPainter to draw grid lines, blue line paths, and linear fading gradients with correct closeSubpath() calls.
- Device sub-items under "Devices" collapsible list in sidebar are made checkable and clickable. Selecting one switches to stacked page index 2 (History page) and configures the active graph.
- Clicking "Show battery history" in a card's dots menu programmatically triggers the sidebar selection, expanding the list and highlighting the device.
- Device history entries are deleted from configuration JSON when the device is removed from monitored status.

### Decisions (from Phase 8 - Packaging & Distribution)

- Renamed application globally from "PeriphWatcher" to "Volt".
- Implemented `scripts/build.py` using PyInstaller to build a standalone `dist/Volt` directory.
- Implemented `scripts/installer.iss` using Inno Setup to create a `Volt_Setup.exe` installer wizard.
- Integrated an Auto-Updater (`src/ui/updater.py`) that checks `https://api.github.com/repos/ViFurzy/Volt/releases/latest`, downloads the `.exe`, and installs silently.
- Added a "Check for Updates" button and version display to the Settings Page.

### Todos

None

### Blockers

- (none)

---

## Session Continuity

**Last session:** 2026-06-07T00:25:00.000Z
**Next action:** Perform packaging / deployment validation or final quality checks.

### Handoff Note

Battery History Graph (FEAT-01) and all bug fixes (BUG-01 to BUG-08) are fully completed, verified, and test-covered:

- **Clean Async Shutdown**: Awaits task gather before stopping loop, with guards for never-started service.
- **Config / Generation Cache**: Caches known devices and monitored device sets, invalidating cache on config writes to optimize disk I/O.
- **Double-Open Guard**: Avoids interface conflicts during scan by reusing active handles.
- **Visual Churn Fix**: Reuses `QGraphicsOpacityEffect` on device cards.
- **Battery History Graph**: Recorded under `"history"` key in JSON, debounced at 10 minutes for identical values, capped at 200 items. Single-device graph displays custom `QPainter` drawing with blue gradient fill.
- **Checkable Sidebar Sub-Items**: Clicking a device sub-item under "Devices" lists in the sidebar navigates to History tab (index 2) showing that specific device's history. Highlights check/selection state visually. Card dots menu action `"Show battery history"` links to this sidebar selection.
- **Auto-Updater Integration**: Background worker checks GitHub releases (`ViFurzy/Volt`) and silently installs updates.
- **Packaging System**: `build.py` + `installer.iss` pipeline creates `Volt_Setup.exe`.
- All 221 tests pass successfully.

---
*Created: 2026-06-01*
*Last updated: 2026-06-07 after packaging, auto-updater implementation, and global rename to Volt*

