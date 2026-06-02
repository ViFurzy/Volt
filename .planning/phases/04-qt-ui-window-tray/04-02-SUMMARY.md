---
phase: 04-qt-ui-window-tray
plan: 02
subsystem: ui
tags: [python, pyside6, qss, qstackedwidget, qtrayicon, sidebar, close-to-tray, pytest-qt]

requires:
  - phase: 04-qt-ui-window-tray
    plan: 01
    provides: SettingsManager — load_config, save_config, set_startup, is_startup_enabled, battery_color

provides:
  - DARK_QSS global stylesheet constant (styles.py)
  - SidebarNav widget — exclusive checkable QPushButtons + QButtonGroup driving QStackedWidget (sidebar.py)
  - SettingsPage — startup toggle wired to SettingsManager (settings_page.py)
  - MainWindow — sidebar+stack layout, closeEvent hide, show_restore, on_device_update Wave-3 stub (main_window.py)
  - TrayManager — QSystemTrayIcon lifecycle, Show/Quit menu, DoubleClick restore (tray.py)
  - src/assets/tray_icon.png — 32x32 teal placeholder PNG
  - Real entry point src/__main__.py — QApplication + DARK_QSS + MonitorApp wired, coinit invariant preserved

affects:
  - 04-03-device-cards (MainWindow.on_device_update stub, dashboard_layout, _cards dict ready for Wave 3)
  - 04-04-visual-verify (dark window shell visible for manual checkpoint)

tech-stack:
  added: []
  patterns:
    - paintEvent override (QStyleOption + drawPrimitive PE_Widget) on all direct QWidget subclasses using QSS background-color
    - QButtonGroup.addButton(btn, idx) with explicit integer id + idClicked -> QStackedWidget.setCurrentIndex (Pitfall 5 avoidance)
    - closeEvent: event.ignore() + self.hide() (never event.accept()) paired with setQuitOnLastWindowClosed(False)
    - TrayManager: icon + menu set before show(); icon path resolved relative to __file__ (T-04-06)
    - sys.coinit_flags=0 on line 2 of __main__.py before all non-sys imports (Architecture Invariant)

key-files:
  created:
    - src/ui/styles.py
    - src/ui/sidebar.py
    - src/ui/settings_page.py
    - src/ui/main_window.py
    - src/ui/tray.py
    - src/assets/tray_icon.png
    - tests/test_ui_main_window.py
    - tests/test_ui_tray.py
  modified:
    - src/__main__.py

key-decisions:
  - "SidebarNav and SettingsPage both override paintEvent — QWidget subclasses require this for QSS background-color to render (Pitfall 1)"
  - "on_device_update is a documented no-op stub; Wave 3 fills card create/update without restructuring main_window.py"
  - "tray_icon.png generated programmatically via QPixmap.fill(#4FC3F7) — no external asset dependency"
  - "QStyleOption is in PySide6.QtWidgets, not PySide6.QtGui — import corrected during Task 1 execution (Rule 1 auto-fix)"

metrics:
  duration: 30min
  completed: 2026-06-02
  tasks: 3
  tests_added: 11
  tests_total: 89
---

# Phase 04 Plan 02: Application Shell Summary

**Dark-themed MainWindow with 5-page sidebar nav, close-to-tray TrayManager, Settings startup toggle, and real __main__ entry point wiring MonitorApp to the Wave-3-ready on_device_update hook**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-06-02
- **Completed:** 2026-06-02
- **Tasks:** 3 / 3
- **Files created:** 8, modified: 1
- **Tests added:** 11 (89 total — all passing, 0 regressions)

## Accomplishments

- `src/ui/styles.py`: `DARK_QSS` with full VOLT | POWER CENTER token set — `#202535` background, `#262355` elevated, `#FFFFFF` text, `#4FC3F7` teal accent for checked sidebar items.
- `src/ui/sidebar.py`: `SidebarNav` with QButtonGroup (exclusive, explicit integer ids) + `idClicked` -> `QStackedWidget.setCurrentIndex`. Starts on Dashboard. `paintEvent` override for QSS background.
- `src/ui/settings_page.py`: `SettingsPage` with startup toggle wired to both `set_startup` (registry) and `save_config` (JSON). Initial state loaded from `is_startup_enabled()` with signals blocked. `paintEvent` override.
- `src/ui/main_window.py`: `MainWindow(QMainWindow)` with 5-page stack (Dashboard scroll area + 3 "Coming soon" placeholders + SettingsPage). `closeEvent` calls `event.ignore() + self.hide()`. `show_restore` brings window to front. `on_device_update` is a Wave-3 stub with `_cards` dict ready.
- `src/ui/tray.py`: `TrayManager` — icon set before `show()`, Show/Quit context menu, DoubleClick restores window, icon path resolved relative to `__file__` (T-04-06).
- `src/assets/tray_icon.png`: 32x32 teal placeholder generated programmatically via `QPixmap.fill`.
- `src/__main__.py`: Real entry point — `sys.coinit_flags=0` on line 2, `setQuitOnLastWindowClosed(False)`, `DARK_QSS` applied, `MonitorApp(consumer=window.on_device_update)`, SIGINT heartbeat, hotplug+timer refs kept alive, clean shutdown via `stop()+unregister()`.

## Task Commits

1. **Task 1: Dark theme, sidebar, settings page** — `9cc2984`
2. **Task 2: MainWindow, TrayManager, tray icon, UI tests** — `46828a3`
3. **Task 3: Real entry point** — `e0c955b`

## Files Created/Modified

- `src/ui/styles.py` — DARK_QSS global stylesheet
- `src/ui/sidebar.py` — SidebarNav widget
- `src/ui/settings_page.py` — SettingsPage with startup toggle
- `src/ui/main_window.py` — MainWindow application shell
- `src/ui/tray.py` — TrayManager
- `src/assets/tray_icon.png` — 32x32 placeholder icon
- `tests/test_ui_main_window.py` — 6 window tests
- `tests/test_ui_tray.py` — 5 tray tests
- `src/__main__.py` — replaced stub with real entry point

## Decisions Made

- `QStyleOption` is in `PySide6.QtWidgets`, not `PySide6.QtGui` — import corrected auto-fix during Task 1.
- `paintEvent` override added to both `SidebarNav` and `SettingsPage` (direct `QWidget` subclasses) — required for QSS background-color rendering (Pitfall 1 / Research Pattern 3).
- `on_device_update` left as a documented no-op so Wave 3 drops device cards without restructuring `main_window.py`.
- `_gen_icon.py` generation script left untracked (not committed) — one-shot tool that produced `tray_icon.png`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] QStyleOption import from wrong module**
- **Found during:** Task 1 verification
- **Issue:** `QStyleOption` was initially imported from `PySide6.QtGui`, but it lives in `PySide6.QtWidgets` in PySide6 6.11.1.
- **Fix:** Moved the import to `PySide6.QtWidgets` in both `sidebar.py` and `settings_page.py`.
- **Files modified:** `src/ui/sidebar.py`, `src/ui/settings_page.py`
- **Commit:** Included in `9cc2984`

## Known Stubs

- `MainWindow.on_device_update`: documented Wave-3 stub (no-op body). Does not flow to UI rendering — `_cards` dict is initialized but no DeviceCard objects exist. Wave 3 (04-03) implements card create/update. This is intentional per plan design.

## Threat Surface Scan

All threat mitigations from plan implemented:
- T-04-05: `on_device_update` is the only place widget mutation will occur; bg thread only calls `queue.put` (architecture invariant unchanged).
- T-04-06: `_ICON_PATH = Path(__file__).parent.parent / "assets" / "tray_icon.png"` — cwd-independent.
- T-04-07: `sys.coinit_flags = 0` is statement 2 in `__main__.py`, verified by AST check.
- T-04-08: `setQuitOnLastWindowClosed(False)` + explicit "Quit" action calling `qapp.quit()` — both in place.

No new network endpoints, auth paths, or external trust boundaries introduced.

## Self-Check: PASSED

- `src/ui/styles.py` — EXISTS
- `src/ui/sidebar.py` — EXISTS
- `src/ui/settings_page.py` — EXISTS
- `src/ui/main_window.py` — EXISTS
- `src/ui/tray.py` — EXISTS
- `src/assets/tray_icon.png` — EXISTS
- `tests/test_ui_main_window.py` — EXISTS
- `tests/test_ui_tray.py` — EXISTS
- `src/__main__.py` — MODIFIED
- Commits `9cc2984`, `46828a3`, `e0c955b` — all present in git log
- Full test suite: 89 passed, 0 failed

---
*Phase: 04-qt-ui-window-tray*
*Completed: 2026-06-02*
