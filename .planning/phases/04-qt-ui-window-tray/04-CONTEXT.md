# Phase 4: Qt UI — Window + Tray - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace `mock_consumer` in `run_monitor.py` with a real PySide6 main window that displays
all monitored devices. Window minimises to system tray on close; tray icon restores it.
Startup toggle in Settings tab. Per-device thresholds are NOT in scope (Phase 6).

Out of scope: notifications (Phase 6), SteelSeries backend (Phase 5), battery history,
profiles, circular gauge (text-only display this phase).
</domain>

<decisions>
## Implementation Decisions

### Visual style
- **D-01:** Apply the VOLT | POWER CENTER dark theme from the design spec in Phase 4.
  The visual foundation must be set now; styling retroactively is harder than styling forward.
  Key tokens: background `#202535`, elevated surface `#262355`, text `#FFFFFF`.
  Battery status colors: normal (> 45%) = teal/neutral, warning (≤ 45%) = amber, critical (≤ 8%) = red.
  Use a global Qt stylesheet on QApplication.

### Battery display in device card
- **D-02:** Text-only battery display in Phase 4 — no circular gauge.
  Each device card shows: device name (large), battery % as large text, a coloured status dot
  or label (ONLINE / OFFLINE / CHARGING), and the charging indicator.
  Circular ring gauge is deferred to a future polish phase.
  The % text uses the amber/red threshold colouring from D-01.

### Window structure — sidebar layout
- **D-03:** Full sidebar skeleton with all navigation items, even if most are placeholders.
  Sidebar items (top to bottom): Dashboard, Devices, History, Profiles, Settings.
  Active in Phase 4: Dashboard (device card grid) and Settings (startup toggle).
  History, Profiles: show a "Coming soon" placeholder QLabel when selected.
  This avoids a structural refactor when Phase 5/6 add content to those tabs.

- **D-04:** Sidebar uses icon + label style matching the design spec.
  Active item: filled/highlighted indicator. Inactive: outline/muted.
  Width: ~64px (icons-only or ~160px with labels) — Claude's discretion.

### Startup toggle
- **D-05:** "Launch at startup" toggle lives in the Settings tab of the sidebar.
  It writes/removes the app executable path in
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` key `PeriphWatcher`
  using Python's stdlib `winreg` module — no admin rights required.

### Settings file
- **D-06:** Phase 4 writes a minimal JSON settings file:
  `{"launch_at_startup": false}` (or true when toggled on).
  File path: `%APPDATA%\PeriphWatcher\config.json` — create the directory if absent.
  Phase 6 adds `"devices": {"<vid>_<pid>": {"threshold": 15, "cooldown_hours": 4}}`
  to the same file without breaking the Phase 4 schema.

### Tray icon behaviour
- **D-07:** Static tray icon (PNG/ICO) in Phase 4 — no dynamic battery % in icon (that's v2 UIV2-02).
  Tray context menu: "Show" + separator + "Quit".
  Double-click tray icon: show/restore main window.
  Dynamic colour-coded tray icon is deferred to v2.

### Close behaviour
- **D-08:** Closing the main window (X button) hides it — does NOT quit the process.
  Override `closeEvent` to call `hide()` and suppress the default close.
  `QApplication.quit()` is only called from the tray "Quit" menu item.

### Claude's Discretion
- Exact sidebar width and whether labels appear alongside icons
- Specific icon assets (SVG/PNG) for sidebar and tray (create minimal placeholders)
- Device card grid layout (1-column vs 2-column vs wrapping)
- Window default size and whether size is persisted (not required by SYS-02)
- Config file load/save helper implementation details
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MonitorApp API (Phase 3 output — stable contract)
- `src/monitor/app.py` — MonitorApp.make_timer(), build_hotplug(), drain(), start(), stop().
  Phase 4 creates QApplication, calls these same methods, replaces mock_consumer with a real callback.
- `src/run_monitor.py` — Current entry point to extend (or replace with a proper __main__.py).
  sys.coinit_flags = 0 placement and SIGINT handler pattern must be preserved.
- `src/monitor/state.py` — DeviceState(frozen=True), DeviceStatus enum, KNOWN_DEVICES.

### Architecture invariants
- `CLAUDE.md` §Architecture Invariants — sys.coinit_flags = 0 first; HID I/O on bg thread;
  cross-thread only via queue.Queue.

### Design spec
- `memory/design_system.md` — VOLT | POWER CENTER color palette, typography, device card anatomy,
  battery threshold values (warning ≤45%, critical ≤8%), sidebar nav items.
  NOTE: Read via the memory system at
  `C:\Users\mzvea\.claude\projects\f--Cursor-batteryChecker\memory\design_system.md`.

### Windows startup registry
- `winreg` stdlib — HKCU\Software\Microsoft\Windows\CurrentVersion\Run, key "PeriphWatcher".
  No admin rights required for HKCU writes.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/run_monitor.py` — `main()` structure to extend: QApplication creation, MonitorApp lifecycle,
  hotplug watcher, timer, app.exec(), clean shutdown. Phase 4 extends or replaces this.
- `src/monitor/app.py:drain()` — already decoupled from mock_consumer via the consumer callback arg.
  Phase 4 passes a real UI update function instead.

### Established Patterns
- `sys.coinit_flags = 0` on line 2 of every entry point (invariant).
- `signal.signal(SIGINT, lambda *_: qapp.quit())` + 200ms QTimer heartbeat (from run_monitor.py).
- `QTimer.timeout.connect(app_obj.drain)` at 500ms — queue drain pattern.
- `app_obj.build_hotplug()` must be called after QApplication exists; caller keeps reference alive.

### Integration Points
- Phase 4's `consumer` callback replaces `mock_consumer(state: DeviceState)`.
  It receives full DeviceState snapshots and must update the matching device card in the UI.
- The device card lookup key is `(state.vid, state.pid, state.dev_idx)`.
- On `DeviceStatus.OFFLINE`, the card should grey out or show a disconnected indicator.
</code_context>

<specifics>
## Specific Ideas

- VOLT | POWER CENTER branding from design spec — use the dark color palette, not Qt default grey.
- "Coming soon" placeholder for History/Profiles tabs keeps the sidebar structure without
  requiring those features to be implemented this phase.
</specifics>

<deferred>
## Deferred Ideas

- Circular ring battery gauge — design spec feature, deferred to a future polish phase
- Dynamic tray icon with battery % (v2 requirement UIV2-02)
- Settings screen UI for notification thresholds (v2 requirement UIV2-04)
- Window geometry persistence (not in SYS-02 requirements)
</deferred>

---

*Phase: 04-qt-ui-window-tray*
*Context gathered: 2026-06-02*
