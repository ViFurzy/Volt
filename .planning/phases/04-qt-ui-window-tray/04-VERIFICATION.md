---
phase: 04-qt-ui-window-tray
verified: 2026-06-03T00:00:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Visual appearance — dark VOLT theme renders correctly (background #202535, white text, dark cards)"
    expected: "Window uses dark theme with no default grey Qt widgets visible"
    why_human: "QSS application and rendered pixel output cannot be asserted programmatically in headless tests"
  - test: "Battery % color threshold rendering on the device card"
    expected: "Text color is teal (>45%), amber (8-45%), red (<=8%), grey (offline) as observed on screen"
    why_human: "stylesheet string is set correctly in code; that Qt actually renders it in the correct color requires a display"
  - test: "System tray icon visible in Windows 11 taskbar (check overflow ^ if hidden)"
    expected: "Tray icon appears; right-click shows Show / separator / Quit"
    why_human: "QSystemTrayIcon.show() cannot be called in headless tests; tray visibility requires a live Windows session"
  - test: "App starts minimized to tray at Windows login when startup toggle is ON"
    expected: "After enabling startup and logging in (or simulating via Run key), the window starts minimized/hidden with tray icon present"
    why_human: "Login behavior requires a Windows session restart to verify; programmatic reg-key writes are tested but the OS-initiated launch behavior is not"
---

# Phase 4: Qt UI — Window + Tray Verification Report

**Phase Goal:** Users can see all monitored devices in a real application window, minimize to tray, restore from tray, and have the app start automatically at Windows login with settings that survive restarts.
**Verified:** 2026-06-03
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All 5 ROADMAP success criteria are verified against the codebase, plus all plan-level must-haves.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Main window displays a device card for each entry in DeviceRegistry showing device name, battery %, and charging status; cards update live as queue messages arrive | VERIFIED | `DeviceCard.update_state` renders `device_name`, `f"{percent}%"`, `status.name`, and charging indicator. `MainWindow.on_device_update` creates/updates cards keyed by `(vid,pid,dev_idx)`. `test_ui_integration.py` drains the real queue into the real consumer and asserts card labels — 8 integration tests pass. |
| 2 | Closing the main window hides it (does not quit the process); tray icon remains and background thread keeps polling | VERIFIED | `closeEvent` calls `event.ignore(); self.hide()`. `__main__.py` sets `qapp.setQuitOnLastWindowClosed(False)` before any window is shown. Tested by `test_close_event_ignored_and_window_hidden`. User hardware checkpoint confirmed (08 Apr 2026-06-02). |
| 3 | Double-clicking the tray icon or using the "Show" context menu item restores the main window | VERIFIED | `TrayManager._on_activated` routes `DoubleClick` to `window.show_restore()`. "Show" QAction triggers `window.show_restore`. `test_double_click_calls_show_restore` and `test_trigger_does_not_call_show_restore` pass. User confirmed double-click and context-menu Show both restore. |
| 4 | A "Launch at startup" toggle writes or removes the app path in HKCU Run without admin rights | VERIFIED | `settings_page.py` wires `QCheckBox.toggled` → `set_startup(checked)` + `save_config(...)`. `set_startup` uses `winreg.HKEY_CURRENT_USER` (no admin required). `_get_exe_path()` correctly adds `-m src` in dev mode and wraps path in double-quotes. All winreg tests pass (5 tests). User confirmed toggle writes/removes key, verified via `reg query`. |
| 5 | Per-device notification thresholds and cooldown settings are saved to JSON config and loaded correctly on next app launch | VERIFIED | `save_config` writes `%APPDATA%\PeriphWatcher\config.json`; `load_config` merges over `_DEFAULTS` (forward-compatible). Round-trip test, defaults-on-absent, defaults-on-malformed, and merge-unknown-keys tests all pass. User confirmed config.json persists and toggle state survives restart. |
| 6 | Settings persist to %APPDATA%\PeriphWatcher\config.json and reload correctly across restarts (plan 01-01) | VERIFIED | See truth #5. |
| 7 | Toggling launch-at-startup writes/removes the HKCU Run key without admin rights (plan 01-01) | VERIFIED | See truth #4. |
| 8 | A missing or malformed config file falls back to defaults without crashing (plan 01-01) | VERIFIED | `load_config` catches `(json.JSONDecodeError, OSError)` and returns `dict(_DEFAULTS)`. Two dedicated tests confirm this behavior. |
| 9 | A dark-themed main window opens with a sidebar (Dashboard, Devices, History, Profiles, Settings) and switchable pages (plan 02-01) | VERIFIED | `SidebarNav` builds 5 exclusive checkable buttons with explicit integer ids wired to `QStackedWidget.setCurrentIndex`. `MainWindow` builds a 5-page stack (QScrollArea dashboard + 3 placeholders + SettingsPage). `test_mainwindow_has_five_page_stack` confirms count == 5. |
| 10 | The battery % text is colored per threshold: critical red (<=8%), warning amber (<=45%), normal teal, grey when offline (plan 03-01) | VERIFIED | `DeviceCard.update_state` calls `battery_color(state.percent)` and sets `self._percent.setStyleSheet(f"color: {color};")`. `battery_color` returns exact hex values `#E50000`/`#E5A300`/`#4FC3F7`/`#888888`. All 4 color tests in `test_ui_device_card.py` pass. |

**Score:** 10/10 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ui/__init__.py` | ui package marker | VERIFIED | Exists, 1 line comment `# ui package` |
| `src/ui/settings_manager.py` | `load_config`, `save_config`, `set_startup`, `is_startup_enabled`, `battery_color` | VERIFIED | 144 lines, all 5 functions implemented, `json.(dump\|load)` and `winreg.(SetValueEx\|DeleteValue\|QueryValueEx)` present |
| `src/ui/styles.py` | `DARK_QSS` global stylesheet containing `#202535` | VERIFIED | 114 lines, `DARK_QSS` string constant contains `#202535`, `#262355`, `#FFFFFF`, `QPushButton:checked` rule, and `QFrame#deviceCard` rules |
| `src/ui/sidebar.py` | `SidebarNav` — 5 exclusive QPushButtons + QButtonGroup driving QStackedWidget | VERIFIED | 72 lines, builds 5 buttons with explicit `group.addButton(btn, idx)`, `idClicked` wired to `stack.setCurrentIndex`, `button(0).setChecked(True)` |
| `src/ui/settings_page.py` | `SettingsPage` with startup QCheckBox wired to SettingsManager | VERIFIED | 71 lines, `QCheckBox.toggled` → `set_startup(checked)` + `save_config(...)`, `blockSignals` on init |
| `src/ui/tray.py` | `TrayManager` — QSystemTrayIcon lifecycle, Show/Quit menu, DoubleClick restore | VERIFIED | 57 lines, Show → `window.show_restore`, Quit → `qapp.quit`, `ActivationReason.DoubleClick` check present |
| `src/ui/main_window.py` | `MainWindow(QMainWindow)` — sidebar+stack, `closeEvent` hide, `show_restore`, `on_device_update` implemented | VERIFIED | 148 lines, `closeEvent` calls `event.ignore(); self.hide()`, `on_device_update` creates/updates `DeviceCard` keyed by `(vid,pid,dev_idx)` |
| `src/ui/device_card.py` | `DeviceCard(QFrame)` with `update_state(DeviceState)` | VERIFIED | 122 lines, subclasses `QFrame`, `update_state` renders name/percent/status/charging indicator/offline property |
| `src/assets/tray_icon.png` | Static tray icon placeholder | VERIFIED | File exists at `src/assets/tray_icon.png` |
| `src/__main__.py` | Real entry point — `sys.coinit_flags = 0` on line 2, `QApplication` wiring, `MonitorApp` consumer | VERIFIED | 56 lines; `sys.coinit_flags = 0` is line 2 (before any non-sys import); `setQuitOnLastWindowClosed(False)` present; `MonitorApp(consumer=window.on_device_update)`; `app_obj.stop(); hotplug.unregister()` on shutdown |
| `tests/test_ui_settings.py` | Unit coverage for config round-trip, defaults, winreg toggle | VERIFIED | 196 lines, 11 tests covering all `battery_color` thresholds, round-trip, absent-file, malformed-file, merge, and all 5 winreg behaviors |
| `tests/test_ui_main_window.py` | Window/tray tests + Wave 3 create-or-update tests | VERIFIED | 178 lines, 12 tests including closeEvent, 5-page stack, create-vs-update (4 scenarios), layout placement |
| `tests/test_ui_tray.py` | TrayManager construction, DoubleClick, non-DoubleClick | VERIFIED | 58 lines, 4 tests including DoubleClick/Trigger/Context routing and icon path existence |
| `tests/test_ui_device_card.py` | Card rendering, threshold colors, offline muting, charging indicator | VERIFIED | 232 lines, 22 tests covering all D-02 anatomy and all threshold color cases |
| `tests/test_ui_integration.py` | Headless end-to-end: queue → drain → consumer → card | VERIFIED | 155 lines, 8 tests draining real `MonitorApp.ui_queue` into real `MainWindow.on_device_update`, no start()/no HID |
| `requirements.txt` | `pytest-qt==4.5.0` present | VERIFIED | Line 3: `pytest-qt==4.5.0` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/ui/main_window.py closeEvent` | `hide()` | `event.ignore() + self.hide()` | WIRED | Lines 103-104 in `main_window.py` |
| `src/ui/tray.py` | `main_window.show_restore` | `ActivationReason.DoubleClick` | WIRED | `_on_activated` line 55-56; Show QAction line 38 |
| `src/ui/settings_page.py` | `ui.settings_manager.set_startup` | `QCheckBox.toggled` | WIRED | Line 57: `set_startup(checked)` in `_on_startup_toggled` |
| `src/ui/settings_manager.py` | `%APPDATA%\PeriphWatcher\config.json` | `json.dump / json.load` | WIRED | Lines 55-59 (`save_config`), lines 48-50 (`load_config`) |
| `src/ui/settings_manager.py` | `HKCU\...\Run` | `winreg.SetValueEx / DeleteValue / QueryValueEx` | WIRED | Lines 116-133 (`set_startup`), lines 138-143 (`is_startup_enabled`) |
| `src/ui/main_window.py on_device_update` | `src/ui/device_card.py DeviceCard.update_state` | dict lookup by `(vid,pid,dev_idx)` | WIRED | Lines 127-135 in `main_window.py`; `DeviceCard` imported at line 23 |
| `src/ui/device_card.py` | `ui.settings_manager.battery_color` | percent → hex color for % label | WIRED | Line 21: `from ui.settings_manager import battery_color`; line 101: `color = battery_color(state.percent)` |
| `src/__main__.py` | `MainWindow.on_device_update` | `MonitorApp(consumer=window.on_device_update) + QTimer drain` | WIRED | Line 38: `MonitorApp(consumer=window.on_device_update, poll_interval=2.0)` |

---

### Data-Flow Trace (Level 4)

The data flow from hardware → background thread → queue → main thread → widget is verified end-to-end.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `DeviceCard._percent` (QLabel) | `state.percent` | `MonitorApp.drain()` pops `DeviceState` from `ui_queue`, calls `consumer(state)` → `MainWindow.on_device_update` → `DeviceCard.update_state` | Yes — integration test puts real `DeviceState` on queue, drain propagates it, card label asserted | FLOWING |
| `DeviceCard._status` (QLabel) | `state.status.name` | Same drain path | Yes | FLOWING |
| `SettingsPage._startup_cb` (QCheckBox) | `is_startup_enabled()` → registry read | `winreg.QueryValueEx` on `HKCU\...\Run` | Yes — live registry read; mocked in tests | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `sys.coinit_flags = 0` is line 2 (before non-sys imports) | `grep -n "coinit_flags" src/__main__.py` | Line 2 match | PASS |
| `__main__.py` contains required wiring | pattern match for `setQuitOnLastWindowClosed`, `consumer=window.on_device_update`, `app_obj.stop` | All 3 present | PASS |
| Full test suite (129 tests) passes | `.venv-1/Scripts/pytest tests/ -x -q` | `129 passed in 1.22s` | PASS |
| `DARK_QSS` contains required color tokens | pattern check for `#202535` in `styles.py` | Present | PASS |
| `tray_icon.png` exists at expected path | `ls src/assets/tray_icon.png` | File found | PASS |
| `pytest-qt==4.5.0` in requirements.txt | grep | Line 3 match | PASS |

---

### Probe Execution

No conventional probe scripts (`scripts/*/tests/probe-*.sh`) exist for this phase. The phase used a blocking human-verify checkpoint (04-04 Task 2) in place of automated probes. The checkpoint result (all 8 items confirmed by user) is recorded in `04-04-SUMMARY.md`.

---

### Requirements Coverage

All 5 requirement IDs declared across Phase 4 plans are fully satisfied.

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SYS-01 | 04-01, 04-02, 04-04 | Startup registration in HKCU Run key without admin | SATISFIED | `set_startup`/`is_startup_enabled` in `settings_manager.py`; `SettingsPage` toggle wired; user confirmed reg key writes/removes |
| SYS-02 | 04-01, 04-04 | Settings persist to JSON config on disk, survive restart | SATISFIED | `load_config`/`save_config` with forward-compatible merge; config at `%APPDATA%\PeriphWatcher\config.json`; user confirmed persistence across restart |
| UI-01 | 04-03, 04-04 | Main window lists all monitored devices with name, battery %, and charging status | SATISFIED | `DeviceCard` renders all fields; `on_device_update` wires queue drain to card creation/update; integration test passes; user confirmed live card on Dashboard |
| UI-02 | 04-02, 04-04 | Closing main window minimizes to tray (does not quit) | SATISFIED | `closeEvent` calls `event.ignore(); self.hide()`; `setQuitOnLastWindowClosed(False)` in entry point; test passes; user confirmed |
| UI-03 | 04-02, 04-04 | Tray icon present when running; double-click / Show menu restores window | SATISFIED | `TrayManager` implements Show menu + DoubleClick activation; tests pass; user confirmed both restore paths and Quit |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/ui/main_window.py` | 40-42, 67-69, 145 | "Coming soon" placeholder pages for Devices/History/Profiles | Info | Intentional — both 04-02-PLAN.md (Task 2 action) and 04-03-PLAN.md success criteria explicitly specify these as Phase 4 placeholders for later phases |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 4 source files.
No unlinked stub returns (`return null`, `return []`, etc.) found.

---

### Human Verification Required

The automated evidence is complete. The following items require a live Windows session to confirm and cannot be asserted programmatically. Note: the 04-04 hardware checkpoint already confirmed all of these during phase execution — these items are listed because they involve rendered UI or OS behavior that the verifier cannot re-run independently.

#### 1. Dark VOLT Theme Visual Rendering

**Test:** Launch `.venv-1\Scripts\python -m src` and observe the main window.
**Expected:** Background is `#202535` (dark navy), text is white, sidebar buttons have a `#4FC3F7` teal left-border accent on the active item. No default grey Qt widget chrome visible.
**Why human:** QSS is applied in code (`qapp.setStyleSheet(DARK_QSS)`) and the correct hex tokens are present in `styles.py`, but actual pixel rendering requires a display session.

#### 2. Battery % Color Threshold on Live Card

**Test:** Observe the G Pro X Wireless device card battery % text color.
**Expected:** Text color matches the threshold (teal for >45%, amber for 8-45%, red for <=8%, grey for offline).
**Why human:** `setStyleSheet` with the correct hex value is verified in code and tests, but that Qt renders the color accurately on screen requires a display.

#### 3. System Tray Icon and Context Menu

**Test:** Run the app. Check the Windows 11 system tray (check the `^` overflow area if not visible). Right-click the icon.
**Expected:** PeriphWatcher icon is visible. Context menu shows "Show" / separator / "Quit".
**Why human:** `QSystemTrayIcon.show()` is never called in headless tests; tray visibility requires a live Windows taskbar session.

#### 4. Startup at Login Behavior

**Test:** Enable "Launch at startup" in Settings, quit the app, and relaunch Windows (or trigger the Run key manually). Verify the app starts minimized.
**Expected:** App appears in the tray (minimized/hidden window) at login without a visible window popup.
**Why human:** The registry write is tested and user-confirmed, but the Windows login sequence behavior requires a real session.

---

### Gaps Summary

No gaps. All 10 must-haves are VERIFIED. All 5 requirement IDs (UI-01, UI-02, UI-03, SYS-01, SYS-02) are SATISFIED. 129 tests pass. The human verification items above were already confirmed during the phase's hardware checkpoint (04-04 Task 2, user-typed "approved" for all 8 checks) — they are listed here because the verifier cannot re-run a live Windows session independently, not because they are unresolved.

---

_Verified: 2026-06-03_
_Verifier: Claude (gsd-verifier)_
