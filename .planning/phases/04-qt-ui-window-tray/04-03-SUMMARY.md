---
phase: 04-qt-ui-window-tray
plan: 03
subsystem: ui
tags: [python, pyside6, qframe, device-card, battery-threshold, tdd, pytest-qt]

requires:
  - phase: 04-qt-ui-window-tray
    plan: 02
    provides: MainWindow with on_device_update stub, _cards dict, dashboard_layout
  - phase: 04-qt-ui-window-tray
    plan: 01
    provides: battery_color threshold helper from settings_manager.py

provides:
  - DeviceCard(QFrame) with update_state(DeviceState) — name/percent/status/charging display
  - MainWindow.on_device_update implemented — create-or-update keyed by (vid,pid,dev_idx)
  - QFrame#deviceCard QSS rules in styles.py
  - 32 tests for DeviceCard, 14 tests for MainWindow (8 new Wave-3 tests)

affects:
  - 04-04-visual-verify (live device cards now rendered on dashboard page)
  - src/__main__.py consumer=window.on_device_update now fully functional

tech-stack:
  added: []
  patterns:
    - DeviceCard subclasses QFrame (not QWidget) to avoid paintEvent workaround for QSS background-color (Research Pitfall 1)
    - setProperty("offline", bool) + style().unpolish/polish for QSS property-driven muting
    - insertWidget(stretch_idx, card) before trailing stretch keeps cards top-down with stretch last
    - TDD RED/GREEN cycle — failing tests committed before implementation

key-files:
  created:
    - src/ui/device_card.py
    - tests/test_ui_device_card.py
  modified:
    - src/ui/main_window.py
    - src/ui/styles.py
    - tests/test_ui_main_window.py

key-decisions:
  - "DeviceCard subclasses QFrame to get QSS background-color without paintEvent override (Research Pitfall 1)"
  - "isHidden() used in charging indicator tests instead of isVisible() — parent not shown in headless tests"
  - "on_device_update inserts at count-1 (before stretch) so layout order is always cards then stretch"
  - "offline property set via setProperty + unpolish/polish so QSS [offline=true] selector responds to runtime changes"

metrics:
  duration: 25min
  completed: 2026-06-02
  tasks: 2
  tests_added: 32
  tests_total: 121
---

# Phase 04 Plan 03: Device Cards Summary

**DeviceCard(QFrame) with threshold-colored battery display and MainWindow.on_device_update wired to create-or-update cards keyed by (vid,pid,dev_idx), closing the visible-data loop for UI-01**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-02
- **Completed:** 2026-06-02
- **Tasks:** 2 / 2
- **Files created:** 2, modified: 3
- **Tests added:** 32 (121 total — all passing, 0 regressions)

## Accomplishments

- `src/ui/device_card.py`: `DeviceCard(QFrame)` with `_name`, `_percent`, `_status`, `_charging_indicator` labels. `update_state(DeviceState)` sets threshold-colored percent via `battery_color()`, shows/hides charging indicator, sets `offline` Qt property + re-polishes for QSS muting.
- `src/ui/main_window.py`: `on_device_update` fully implemented — looks up `(state.vid, state.pid, state.dev_idx)` key, creates `DeviceCard(state)` on first sight (inserting before layout stretch), calls `card.update_state(state)` on repeat calls. `DeviceCard` imported at module level (safe in Wave 3).
- `src/ui/styles.py`: Added `QFrame#deviceCard` rules (elevated `#262355` background, rounded border) and `QFrame#deviceCard[offline="true"]` muting rules.
- `tests/test_ui_device_card.py`: 24 tests covering QFrame subclass, name/percent/status labels, all threshold colors (critical/warning/normal/None), OFFLINE muted property, charging indicator visibility.
- `tests/test_ui_main_window.py`: Extended with 8 new tests — first-state creates card, repeat-state no duplicate, two distinct devices, layout insertion, stretch stays last. All 6 Wave-2 tests still pass.

## Task Commits

| Task | Name | Phase | Commit |
|------|------|-------|--------|
| 1 RED | DeviceCard failing tests | test | `17320df` |
| 1 GREEN | DeviceCard implementation | feat | `93a3c4e` |
| 2 RED | on_device_update failing tests | test | `19b3f33` |
| 2 GREEN | on_device_update implementation | feat | `f00f8eb` |

## Files Created/Modified

- `src/ui/device_card.py` — DeviceCard(QFrame) widget (created)
- `src/ui/main_window.py` — on_device_update implemented, DeviceCard imported (modified)
- `src/ui/styles.py` — QFrame#deviceCard QSS rules added (modified)
- `tests/test_ui_device_card.py` — 24 DeviceCard unit tests (created)
- `tests/test_ui_main_window.py` — 8 Wave-3 on_device_update tests added (modified)

## Decisions Made

- `DeviceCard` subclasses `QFrame` not `QWidget` — avoids the `paintEvent` + `QStyleOption` overhead required for raw `QWidget` subclasses to receive `QSS background-color` (Research Pitfall 1).
- `isHidden()` used instead of `isVisible()` in charging indicator tests — in headless pytest-qt, a widget whose parent has never been shown returns `isVisible() == False` even if `setVisible(True)` was called. `isHidden()` reflects the explicit show/hide state correctly.
- `insertWidget(count - 1, card)` places cards before the trailing stretch item, preserving the top-down stacking contract.
- `setProperty("offline", bool)` + `style().unpolish(self)/polish(self)` required to trigger QSS property selector re-evaluation at runtime.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] isVisible() unreliable for hidden-parent widgets in headless tests**
- **Found during:** Task 1 GREEN verification
- **Issue:** `_charging_indicator.isVisible()` returned `False` even after `setVisible(True)` because the parent `DeviceCard` was never shown (headless test environment). This caused 1 test to fail despite correct implementation.
- **Fix:** Changed charging indicator assertions to use `isHidden()` which reflects the explicit widget show/hide state, not the full parent-chain visibility.
- **Files modified:** `tests/test_ui_device_card.py`
- **Commit:** Included in `93a3c4e`

## Known Stubs

None — all D-02 card anatomy fields are live and wired to real DeviceState data.

## Threat Surface Scan

All threat mitigations from plan implemented:
- T-04-09: `on_device_update` has explicit create-if-absent branch; verified by `test_first_state_creates_card`.
- T-04-10: Keyed `_cards` dict ensures one card per `(vid,pid,dev_idx)`; verified by `test_repeat_state_does_not_create_duplicate`.
- T-04-11: `state.device_name` used directly (sourced from `KNOWN_DEVICES` in Phase 3) — accepted.

No new network endpoints, auth paths, or external trust boundaries introduced.

## Self-Check: PASSED

- `src/ui/device_card.py` — EXISTS
- `src/ui/main_window.py` — MODIFIED (on_device_update implemented)
- `src/ui/styles.py` — MODIFIED (deviceCard QSS added)
- `tests/test_ui_device_card.py` — EXISTS
- `tests/test_ui_main_window.py` — MODIFIED (8 new tests)
- Commits `17320df`, `93a3c4e`, `19b3f33`, `f00f8eb` — all present in git log
- Target test files: 38 passed, 0 failed
- Full test suite: 121 passed, 0 failed

---
*Phase: 04-qt-ui-window-tray*
*Completed: 2026-06-02*
