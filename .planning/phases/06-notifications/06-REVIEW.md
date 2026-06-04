---
phase: 06-notifications
reviewed: 2026-06-04T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - src/ui/notification_manager.py
  - tests/test_notification_manager.py
  - src/ui/settings_manager.py
  - src/__main__.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-06-04
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Four files were reviewed: the new `NotificationManager` class, its test suite, the extended `settings_manager.py`, and the rewired `__main__.py`. The notification logic itself is structurally sound — cooldown tracking, threshold clamping, offline reset, and toast dispatch all follow correct patterns. However, two critical defects were found: notifications fire while the device is charging (the `CHARGING` status is not guarded), and `cooldown_hours` is used in a numeric comparison without type coercion, which will crash at runtime if the value is ever stored as a string in `config.json`. Three additional warnings cover a repeated disk-read hot path, a silent registry-write failure with no user feedback path, and a latent startup-path bug in `_get_exe_path`. Two info items cover dead test imports and a `null`-thresholds crash surface.

---

## Critical Issues

### CR-01: Notifications fire while device is CHARGING

**File:** `src/ui/notification_manager.py:23-25`

**Issue:** The early-return guard only checks for `DeviceStatus.OFFLINE`. `DeviceStatus.CHARGING` is a distinct enum value (defined in `state.py` line 27, emitted by `service.py` line 283). A device with 10% battery that is actively charging will still pass through to `show_toast()`, producing a "battery low — charge soon" notification at the exact moment the user is already charging. The bug is invisible during normal single-device testing since `CHARGING` state only appears when a cable is connected.

**Fix:**
```python
# notification_manager.py — replace lines 23-25
if state.status in (DeviceStatus.OFFLINE, DeviceStatus.CHARGING):
    if state.status == DeviceStatus.OFFLINE:
        self._last_notified.pop(key, None)
    return
```

Or more readably:
```python
if state.status == DeviceStatus.OFFLINE:
    self._last_notified.pop(key, None)
    return

if state.status == DeviceStatus.CHARGING:
    return  # no notification while plugged in; do NOT clear cooldown
```

Note: The cooldown entry should be preserved (not popped) for `CHARGING` so that if the device is unplugged at 10% it does not immediately re-fire.

---

### CR-02: `cooldown_hours` used in numeric comparison without type coercion — `TypeError` crash if value is a JSON string

**File:** `src/ui/notification_manager.py:33,41`

**Issue:** `threshold_pct` is guarded with `int(device_cfg.get("threshold_pct", 15))` on line 32 to convert string-encoded JSON values. `cooldown_hours` on line 33 receives no such coercion. The comparison on line 41 is `elapsed < cooldown_hours` where `elapsed` is a `float`. If a user sets `"cooldown_hours": "4"` in `config.json` (a common mistake in hand-edited JSON), this raises `TypeError: '<' not supported between instances of 'float' and 'str'`. This crashes the Qt main-thread drain callback, silently halting all further device state processing for the rest of the session (the `drain()` loop has no exception guard).

**Fix:**
```python
# notification_manager.py line 33
cooldown_hours = float(device_cfg.get("cooldown_hours", 4))
```

---

## Warnings

### WR-01: `load_config()` called on every device update — repeated disk I/O on Qt main thread

**File:** `src/__main__.py:27`

**Issue:** `_on_device_update` calls `load_config()` on every invocation. The `MonitorApp.drain()` loop calls the consumer once per queued `DeviceState`. With two devices and a 500ms drain interval this is 4 disk reads per second minimum. `load_config()` does `CONFIG_DIR.mkdir(parents=True, exist_ok=True)` followed by `CONFIG_FILE.open()` + `json.load()` on every call. This runs on the Qt main thread, blocking the event loop on each syscall. The RESEARCH.md (line 253) explicitly flags this as a "cleaner" alternative that should be addressed.

**Fix:** Load config once at app start and pass the dict directly, or reload only when a settings-change signal is emitted:
```python
# src/__main__.py — load once
cfg = load_config()
app_obj = MonitorApp(
    consumer=lambda s: _on_device_update(window, notif_manager, cfg, s),
    poll_interval=2.0,
)

def _on_device_update(window, notif_manager, cfg, state):
    window.on_device_update(state)
    notif_manager.check(state, cfg)
```

If live config reload is required, add a settings-changed signal and reload only then.

---

### WR-02: `set_startup(True)` silently swallows `OSError` with no user feedback path

**File:** `src/ui/settings_manager.py:115-123`

**Issue:** When `winreg.OpenKey` or `winreg.SetValueEx` raises `OSError` (e.g. permission denied, registry hive locked), the exception is caught and discarded (`pass`). The calling code in `settings_page.py` has no way to distinguish success from silent failure. The UI checkbox will appear checked while the startup key was never written. The comment on line 123 acknowledges this but does not address it. On systems with GPO restrictions on the Run key, this failure mode is not rare.

**Fix:** Either return a `bool` success indicator, or re-raise as a domain-specific exception that the settings page can catch and display:
```python
def set_startup(enabled: bool) -> bool:
    """Returns True on success, False if registry write failed."""
    if enabled:
        try:
            with winreg.OpenKey(...) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
            return True
        except OSError:
            return False
    else:
        ...
        return True
```

---

### WR-03: `_get_exe_path()` dev-mode path ignores computed `project_dir` — startup launch fails if CWD is not project root

**File:** `src/ui/settings_manager.py:99-103`

**Issue:** `_get_exe_path()` computes `src_dir` and `project_dir` on lines 100-101 but neither variable is used in the returned string. The return value `f'"{exe}" -m src'` is a hardcoded relative module reference. At Windows login, `python.exe -m src` resolves `src` relative to the working directory, which is `C:\Windows\System32` or the user profile — not the project directory. The app will fail to start at login silently (the process exits immediately with `ModuleNotFoundError`). The computed `project_dir` is dead code.

**Fix:** Use the absolute project directory as the working directory or pass the full module path:
```python
return f'"{exe}" -m src --wd "{project_dir}"'
# or, more reliably, use the -c flag with an absolute path:
return f'"{exe}" "{os.path.join(project_dir, "src", "__main__.py")}"'
```

The most robust approach for dev mode is:
```python
src_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(src_dir)
# Register with Start In directory via a .bat launcher, or use the abs path form:
return f'"{exe}" "{os.path.join(project_dir, "src", "__main__.py")}"'
```

---

## Info

### IN-01: `pytest` imported but never used in test file

**File:** `tests/test_notification_manager.py:5`

**Issue:** `import pytest` is present but no pytest fixtures, marks, or `pytest.raises` calls appear anywhere in the file. This is dead import.

**Fix:** Remove line 5: `import pytest`.

---

### IN-02: `thresholds` value not validated as `dict` — `AttributeError` if `config.json` contains `"thresholds": null`

**File:** `src/ui/notification_manager.py:30-31`

**Issue:** `thresholds = config.get("thresholds", {})` returns `None` if the config file explicitly contains `"thresholds": null` (the default fallback `{}` only applies when the key is absent entirely, not when it is present with a `null` value). The subsequent `thresholds.get(...)` call on line 31 then raises `AttributeError: 'NoneType' object has no attribute 'get'`. While a hand-crafted `config.json` is needed to trigger this, it is a realistic user error.

**Fix:**
```python
thresholds = config.get("thresholds") or {}
device_cfg = thresholds.get(f"{state.vid}:{state.pid}") or {}
```

---

_Reviewed: 2026-06-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
