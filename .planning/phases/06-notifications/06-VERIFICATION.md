---
phase: 06-notifications
verified: 2026-06-04T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Confirm Windows toast notification appears in Action Center when device battery drops below configured threshold"
    expected: "Toast titled '[Device] battery low' with body 'Battery at XX% — charge soon' visible in Windows Action Center within one poll cycle"
    why_human: "06-03 SUMMARY documents hardware approval and smoke-test pass, but the verifier cannot run the WinRT toast API or observe Action Center in a headless session"
  - test: "Confirm cooldown suppresses repeated toasts within 4-hour window"
    expected: "No second toast fires for the same device within the 4-hour cooldown window after first alert"
    why_human: "Requires real-time observation on the target machine with a connected device; cannot be automated headlessly"
  - test: "Confirm cooldown resets after dongle unplug and replug"
    expected: "A fresh toast fires after unplugging and re-plugging the dongle even though the cooldown has not expired"
    why_human: "Requires physical hardware interaction; cannot be simulated in the test suite"
---

# Phase 6: Notifications Verification Report

**Phase Goal:** Users receive a Windows toast notification when any device drops below its configured battery threshold, without being spammed by repeated alerts
**Verified:** 2026-06-04
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Toast fires when battery crosses below per-device threshold for the first time | VERIFIED | `test_fires_on_threshold_crossing` passes; `check()` calls `show_toast()` exactly once on first crossing; hardware checkpoint in 06-03 SUMMARY confirms live toast in Action Center |
| 2 | Threshold read from persisted settings (SYS-02), defaults to 15% | VERIFIED | `settings_manager._DEFAULTS` contains `"thresholds": {}`; `NotificationManager.check()` reads `config.get("thresholds", {})` and falls back to 15 via `device_cfg.get("threshold_pct", 15)`; `test_default_threshold` confirms percent=14 fires |
| 3 | No further notification until cooldown elapsed (default 4h) | VERIFIED | `test_cooldown_suppresses` confirms second call within window does not fire; `test_fires_after_cooldown` confirms fire resumes after 5-hour time-travel; default 4h from `device_cfg.get("cooldown_hours", 4)` |
| 4 | Cooldown resets when device goes offline and returns online | VERIFIED | `self._last_notified.pop(key, None)` on `DeviceStatus.OFFLINE` at line 24 of `notification_manager.py`; `test_cooldown_resets_on_offline` asserts key absent after OFFLINE call; hardware unplug/replug confirmed in 06-03 |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/ui/notification_manager.py` | NotificationManager class with `__init__` and `check()` | VERIFIED | File exists, 50 lines, substantive implementation; no Qt imports; wired into `__main__.py` via `_on_device_update` |
| `tests/test_notification_manager.py` | 7 unit tests with mocked WindowsToaster | VERIFIED | 7 test functions present; all pass (confirmed via `.venv-1/Scripts/python.exe -m pytest`); no real WinRT calls |
| `requirements.txt` | Contains `windows-toasts==1.3.1` | VERIFIED | Line 4: `windows-toasts==1.3.1`; import `from windows_toasts import Toast, WindowsToaster` confirmed importable |
| `src/ui/settings_manager.py` | `_DEFAULTS` includes `"thresholds": {}` | VERIFIED | Line 23: `_DEFAULTS: dict = {"launch_at_startup": False, "thresholds": {}}` |
| `src/__main__.py` | NotificationManager instantiated and wired into MonitorApp consumer | VERIFIED | `notif_manager = NotificationManager()` at line 47; `lambda s: _on_device_update(window, notif_manager, s)` at line 48; `_on_device_update` helper calls both `window.on_device_update(state)` and `notif_manager.check(state, cfg)` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_notification_manager.py` | `src/ui/notification_manager.py` | `patch("ui.notification_manager.WindowsToaster")` | WIRED | Import at line 8; patch path confirmed in all 7 tests |
| `src/ui/notification_manager.py` | `src/monitor/state.py` | `from monitor.state import DeviceState, DeviceStatus` | WIRED | Line 12; `DeviceStatus.OFFLINE` used at line 23 |
| `src/__main__.py` | `src/ui/notification_manager.py` | `from ui.notification_manager import NotificationManager` | WIRED | Line 19; instantiated at line 47; used via lambda at line 48 |
| `src/__main__.py` | `src/ui/settings_manager.py` | `from ui.settings_manager import load_config` | WIRED | Line 20; called inside `_on_device_update` at line 27 |
| `src/__main__.py` | Windows Action Center | `WindowsToaster.show_toast()` on Qt main thread drain | WIRED (hardware-verified) | `show_toast()` called at `notification_manager.py` line 48; hardware smoke test in 06-03 confirmed no exception and toast visible |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `notification_manager.py` | `state.percent` | `DeviceState` from `MonitorApp` queue drain | Yes — real HID device data via polling | FLOWING |
| `notification_manager.py` | `config` | `load_config()` reading `%APPDATA%\PeriphWatcher\config.json` | Yes — disk-persisted JSON with defaults fallback | FLOWING |
| `notification_manager.py` | `self._last_notified` | In-memory dict populated by `check()` on each alert | Yes — populated on first crossing, governs cooldown | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 7 notification unit tests pass | `.venv-1/Scripts/python.exe -m pytest tests/test_notification_manager.py -v` | 7 passed in 0.10s | PASS |
| Full test suite (152 tests) still green | `.venv-1/Scripts/python.exe -m pytest tests/ -q` | 152 passed in 1.22s | PASS |
| `windows-toasts` importable | `.venv-1/Scripts/python.exe -c "from windows_toasts import Toast, WindowsToaster; print('OK')"` | OK | PASS |
| `sys.coinit_flags` set before COM-initializing imports | Line scan of `__main__.py` | `import sys` on line 1, `sys.coinit_flags = 0` on line 2, PySide6/ui imports begin at line 13 | PASS (see note) |

**Note on `sys.coinit_flags` position:** The ROADMAP invariant states "first line of `__main__`, before all imports." Literally, `import sys` is on line 1 and `sys.coinit_flags = 0` is on line 2. However, `import sys` is the stdlib `sys` module — it does not initialize COM in any mode. The invariant's intent (no COM-initializing library imported before the flag) is preserved: PySide6, pywin32, and bleak imports all occur after line 2. This is a WARNING, not a BLOCKER. The architecture constraint that matters — flag set before any WinRT/COM initialization — is satisfied.

---

### Probe Execution

No probes declared in plan frontmatter. No conventional `scripts/*/tests/probe-*.sh` files found. Step 7c: SKIPPED (no probe scripts).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| NOTIF-01 | 06-01, 06-02, 06-03 | App sends Windows toast when battery drops below per-device configurable threshold | SATISFIED | `NotificationManager.check()` implements threshold comparison; `test_fires_on_threshold_crossing` and `test_default_threshold` verify; hardware checkpoint in 06-03 confirms live toast |
| NOTIF-02 | 06-01, 06-02, 06-03 | Notification cooldown prevents repeat alerts within configurable time window | SATISFIED | Cooldown dict `_last_notified` keyed by `(vid, pid, dev_idx)`; `test_cooldown_suppresses`, `test_fires_after_cooldown`, `test_cooldown_resets_on_offline` verify all branches; hardware unplug/replug confirmed |

**Note:** REQUIREMENTS.md lines 28-29 still show `NOTIF-01` and `NOTIF-02` with `[ ]` (unchecked). This is a documentation artifact — the checkboxes were not updated. The implementation is complete and verified. The traceability table (line 79-80) correctly maps both to Phase 6.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

Scanned `src/ui/notification_manager.py`, `src/__main__.py`, `src/ui/settings_manager.py`, `tests/test_notification_manager.py` for TODO, FIXME, TBD, XXX, placeholder, hardcoded empty returns. Zero matches.

---

### Human Verification Required

The unit tests and wiring checks are fully automated and pass. The following behaviors require a human with the target hardware because the verifier cannot invoke the WinRT toast API or observe Windows Action Center in a headless environment. Note: 06-03 SUMMARY documents these were already verified by the developer — this section serves as the formal gate record.

#### 1. Toast Visible in Action Center (NOTIF-01)

**Test:** Start the app with a device threshold set to 90% and cooldown 0. Wait for one poll cycle (60s).
**Expected:** Toast titled "G Pro X Wireless battery low" with body "Battery at XX% — charge soon" appears in Windows Action Center.
**Why human:** Requires WinRT toast infrastructure and a running Qt event loop. Cannot be verified in a headless test session.

#### 2. Cooldown Suppression (NOTIF-02 — no-spam)

**Test:** With normal 4-hour cooldown, observe that no second toast fires within the same session after the first alert.
**Expected:** Only one toast per device per 4-hour window.
**Why human:** Requires real-time observation across multiple poll cycles on the target machine.

#### 3. Cooldown Reset on Disconnect (NOTIF-02 — OFFLINE reset)

**Test:** After first alert fires, unplug the dongle (device goes OFFLINE), then replug. Wait for one poll cycle.
**Expected:** A fresh toast fires even though the 4-hour cooldown has not elapsed.
**Why human:** Requires physical hardware interaction with the dongle.

---

### Gaps Summary

No gaps. All 4 ROADMAP success criteria are satisfied by codebase evidence. Human verification items above reflect the inherent impossibility of automated headless WinRT/hardware testing — not missing implementation.

---

_Verified: 2026-06-04_
_Verifier: Claude (gsd-verifier)_
