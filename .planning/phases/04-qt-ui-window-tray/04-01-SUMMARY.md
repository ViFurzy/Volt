---
phase: 04-qt-ui-window-tray
plan: 01
subsystem: ui
tags: [python, json, winreg, pathlib, settings, pytest-qt]

requires:
  - phase: 03-monitor-core
    provides: DeviceState, DeviceStatus — consumed in future battery_color calls

provides:
  - SettingsManager module: load_config, save_config, battery_color, set_startup, is_startup_enabled
  - src/ui/ package initialised as Phase 4 UI home
  - Headless settings layer fully unit-tested before any Qt widget exists

affects:
  - 04-02-main-window (imports battery_color, load_config, save_config)
  - 04-03-settings-page (imports set_startup, is_startup_enabled, save_config)
  - 04-04-visual-verify (battery_color thresholds flagged for visual check — amber #E5A300)

tech-stack:
  added:
    - pytest-qt==4.5.0 (test-only; QApplication singleton management in pytest)
  patterns:
    - Forward-compatible config merge: {**_DEFAULTS, **loaded_data} so Phase 6 device keys survive Phase 4 reads
    - Module-level CONFIG_DIR/CONFIG_FILE constants overridable via monkeypatch for zero-side-effect tests
    - winreg context-manager pattern (OpenKey as context manager) with FileNotFoundError swallowed for idempotent delete
    - Outer-quoted exe path in REG_SZ value to handle paths with spaces (Pitfall 4 / T-04-03)

key-files:
  created:
    - src/ui/__init__.py
    - src/ui/settings_manager.py
    - tests/test_ui_settings.py
  modified:
    - requirements.txt

key-decisions:
  - "CONFIG_DIR/CONFIG_FILE are module-level Path constants, not hardcoded in function bodies, so tests can monkeypatch them without filesystem side-effects"
  - "battery_color None-check comes first (before numeric comparisons) to handle offline devices"
  - "All winreg calls mocked in tests — no test touches the real HKCU registry"
  - "pytest-qt added as test-only dependency; gate was approved by user (pytest-dev org, 10+ yr history)"

patterns-established:
  - "settings_manager: no Qt imports — pure stdlib so all tests run headlessly without QApplication"
  - "TDD red-green: failing import error confirmed RED before writing implementation"

requirements-completed: [SYS-01, SYS-02]

duration: 25min
completed: 2026-06-02
---

# Phase 04 Plan 01: Settings Layer Summary

**Headless JSON config persistence and HKCU Run-key startup registration behind a fully unit-tested pure-stdlib module; 16 tests, zero real filesystem or registry side-effects**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-02T00:00:00Z
- **Completed:** 2026-06-02
- **Tasks:** 3 (task 1 was checkpoint, tasks 2+3 executed this session)
- **Files modified:** 4

## Accomplishments

- `src/ui/settings_manager.py` implements load_config, save_config (forward-compatible merge), battery_color thresholds, set_startup, is_startup_enabled — all pure stdlib, no Qt
- 16 unit tests in `tests/test_ui_settings.py` covering every behavior bullet: round-trip, defaults-on-missing, defaults-on-malformed, battery_color six cases, winreg mocked enable/disable/idempotent/query
- pytest-qt 4.5.0 supply-chain gate approved by user and installed; pinned in requirements.txt
- Full suite (78 tests) remains green — zero regressions

## Task Commits

1. **Task 1: pytest-qt legitimacy gate** - `f6b8e57` (chore — requirements.txt)
2. **Task 2+3 RED: failing tests** - `ee7556d` (test — test_ui_settings.py + src/ui/__init__.py)
3. **Task 2+3 GREEN: implementation** - `dd11aac` (feat — settings_manager.py)

## Files Created/Modified

- `src/ui/__init__.py` — package marker for the Phase 4 ui package
- `src/ui/settings_manager.py` — all settings logic: JSON config, battery threshold color, winreg startup toggle
- `tests/test_ui_settings.py` — 16 unit tests; uses tmp_path + monkeypatch for config, mocker for winreg
- `requirements.txt` — added pytest-qt==4.5.0 (test-only)

## Decisions Made

- CONFIG_DIR and CONFIG_FILE are module-level constants so tests can monkeypatch them directly without filesystem coupling.
- The `None` case in `battery_color` is checked first to avoid TypeError when comparing None to an integer threshold.
- All winreg calls in tests are mocked via `mocker.patch("ui.settings_manager.winreg.*")` — no test reads or writes the real registry.
- TDD was applied across Tasks 2 and 3 together: one RED commit (all tests for both tasks), one GREEN commit (full implementation).

## Deviations from Plan

None — plan executed exactly as written. Tasks 2 and 3 were combined into a single RED/GREEN cycle because both live in the same module and test file; this is consistent with the plan's file list.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — all functions return real values; no placeholder data flows to UI rendering in this module.

## Threat Surface Scan

No new network endpoints, auth paths, or external trust boundaries introduced. Threat mitigations from plan implemented:
- T-04-01: `json.JSONDecodeError + OSError` caught in load_config, falls back to _DEFAULTS
- T-04-02: `{**_DEFAULTS, **data}` merge on load ensures missing keys are restored
- T-04-03: `_get_exe_path()` wraps sys.executable in outer double-quotes
- T-04-04: HKCU only (no HKLM) — no admin rights required by design

## Next Phase Readiness

- `src/ui/settings_manager` is a stable, verified contract for Wave 2 plans (04-02 main window, 04-03 settings page)
- Wave 2 plans import `from ui.settings_manager import load_config, save_config, battery_color, set_startup, is_startup_enabled`
- Visual verification of amber `#E5A300` against the VOLT | POWER CENTER design spec is flagged for 04-04 checkpoint

---
*Phase: 04-qt-ui-window-tray*
*Completed: 2026-06-02*
