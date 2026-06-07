# Phase 6: Notifications - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 6 new/modified files
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/ui/notification_manager.py` | service | event-driven | `src/monitor/registry.py` | role-match (state tracker + in-memory dict) |
| `src/ui/settings_manager.py` | config | CRUD | self (existing file) | exact (add key to `_DEFAULTS`) |
| `src/ui/main_window.py` | controller | request-response | self (existing file) | exact (extend `on_device_update`) |
| `src/__main__.py` | config/wiring | request-response | self (existing file) | exact (add import + instantiation) |
| `tests/test_notification_manager.py` | test | event-driven | `tests/test_registry.py` + `tests/test_ui_settings.py` | role-match |
| `requirements.txt` | config | — | self (existing file) | exact (append one line) |

## Pattern Assignments

### `src/ui/notification_manager.py` (service, event-driven)

**Analog:** `src/monitor/registry.py` (in-memory dict keyed by device tuple) and the pattern sketch in RESEARCH.md Pattern 1.

**Imports pattern** — follow `registry.py` lines 1-14 for stdlib-only imports, no Qt:
```python
"""Notification dispatch and cooldown tracking for PeriphWatcher.

No Qt imports — pure stdlib so tests run headlessly.
Instantiated in __main__.py; check() called from main-thread drain path.
"""
from __future__ import annotations

from datetime import datetime

from windows_toasts import Toast, WindowsToaster

from monitor.state import DeviceState, DeviceStatus
```

**Core pattern** — in-memory dict keyed by `(vid, pid, dev_idx)` (same key shape as `DeviceRegistry._devices` in `registry.py` lines 24-26):
```python
class NotificationManager:
    def __init__(self) -> None:
        self._toaster = WindowsToaster("PeriphWatcher")
        self._last_notified: dict[tuple[int, int, int], datetime] = {}

    def check(self, state: DeviceState, config: dict) -> None:
        key = (state.vid, state.pid, state.dev_idx)

        if state.status == DeviceStatus.OFFLINE:
            self._last_notified.pop(key, None)
            return

        if state.percent is None:
            return

        thresholds = config.get("thresholds", {})
        device_cfg = thresholds.get(f"{state.vid}:{state.pid}", {})
        threshold = max(1, min(99, int(device_cfg.get("threshold_pct", 15))))
        cooldown_hours = device_cfg.get("cooldown_hours", 4)

        if state.percent >= threshold:
            return

        last = self._last_notified.get(key)
        if last is not None:
            elapsed = (datetime.now() - last).total_seconds() / 3600
            if elapsed < cooldown_hours:
                return

        toast = Toast(text_fields=[
            f"{state.device_name} battery low",
            f"Battery at {state.percent}% — charge soon",
        ])
        self._toaster.show_toast(toast)
        self._last_notified[key] = datetime.now()
```

**Error handling pattern** — clamp threshold silently (security pattern from RESEARCH.md §Security Domain); never raise on bad config, same philosophy as `settings_manager.py` lines 47-52 which returns defaults on `json.JSONDecodeError`/`OSError`.

---

### `src/ui/settings_manager.py` (config, CRUD) — MODIFY

**Analog:** self (`src/ui/settings_manager.py` lines 23-52)

**Change required:** Add `"thresholds": {}` to `_DEFAULTS` (line 23) so the `{**_DEFAULTS, **data}` merge (line 50) provides an empty dict rather than a `KeyError` when no thresholds are configured.

**Existing `_DEFAULTS` pattern** (line 23):
```python
_DEFAULTS: dict = {"launch_at_startup": False}
```

**After modification:**
```python
_DEFAULTS: dict = {"launch_at_startup": False, "thresholds": {}}
```

**Existing merge pattern** (lines 47-52) — no change needed, works as-is:
```python
    try:
        with CONFIG_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)
```

---

### `src/ui/main_window.py` (controller, request-response) — MODIFY

**Analog:** self (`src/ui/main_window.py` lines 116-135)

**Existing `on_device_update` pattern** (lines 116-135) — the hook point for Phase 6:
```python
    def on_device_update(self, state: DeviceState) -> None:
        key = (state.vid, state.pid, state.dev_idx)
        if key not in self._cards:
            card = DeviceCard(state)
            self._cards[key] = card
            stretch_idx = self.dashboard_layout.count() - 1
            self.dashboard_layout.insertWidget(stretch_idx, card)
        else:
            self._cards[key].update_state(state)
```

**Change required:** Per RESEARCH.md Pattern 4 (alternative B), the simplest approach is to call `NotificationManager.check()` at the end of `on_device_update`. This avoids a lambda wrapper in `__main__.py`. Add to `__init__` a `notif_manager` parameter, or wire via `__main__` lambda. RESEARCH.md recommends the lambda wrapper in `__main__` to avoid adding a `NotificationManager` dependency to `MainWindow`. Either is valid — the planner picks one.

---

### `src/__main__.py` (wiring, request-response) — MODIFY

**Analog:** self (`src/__main__.py` lines 1-55)

**Existing wiring pattern** (lines 38-44) — the consumer lambda is the injection point:
```python
    app_obj = MonitorApp(consumer=window.on_device_update, poll_interval=2.0)
    app_obj.start()
    hotplug = app_obj.build_hotplug()
    timer = app_obj.make_timer()  # noqa: F841 — kept alive intentionally
```

**Change required** — add import + instantiation + rewire consumer (RESEARCH.md Pattern 4):
```python
from ui.notification_manager import NotificationManager

def main() -> None:
    ...
    notif_manager = NotificationManager()
    app_obj = MonitorApp(
        consumer=lambda s: _on_device_update(window, notif_manager, s),
        poll_interval=2.0,
    )
    ...

def _on_device_update(
    window: MainWindow,
    notif_manager: NotificationManager,
    state: DeviceState,
) -> None:
    window.on_device_update(state)
    cfg = load_config()
    notif_manager.check(state, cfg)
```

The import of `load_config` is already available via `ui.settings_manager`; add it to the existing import block.

---

### `tests/test_notification_manager.py` (test, event-driven)

**Analog:** `tests/test_registry.py` (factory helper + focused assertion tests) and `tests/test_ui_settings.py` (mocker/patch pattern via pytest-mock).

**Imports pattern** — combining both analogs (test_registry.py lines 1-4, test_ui_settings.py lines 1-13):
```python
"""Unit tests for NotificationManager — no real WinRT calls."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from monitor.state import DeviceState, DeviceStatus
from ui.notification_manager import NotificationManager
```

**Factory helper pattern** — copy from `test_registry.py` lines 87-96:
```python
def _make_state(percent=10, status=DeviceStatus.ONLINE, charging=False):
    return DeviceState(
        vid=0x046D,
        pid=0x0ABA,
        dev_idx=0xFF,
        device_name="G Pro X Wireless",
        percent=percent,
        charging=charging,
        status=status,
    )
```

**Mock WindowsToaster pattern** — from RESEARCH.md Code Examples + `test_ui_settings.py` mocker style (lines 115-133):
```python
def test_fires_on_threshold_crossing():
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        mgr.check(_make_state(percent=10), {"thresholds": {}})

        mock_toaster.show_toast.assert_called_once()
```

**Cooldown time-travel pattern** — inject past timestamp directly into `_last_notified`:
```python
def test_fires_after_cooldown():
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        key = (0x046D, 0x0ABA, 0xFF)
        # Plant an expired timestamp (5 hours ago, cooldown default is 4h)
        mgr._last_notified[key] = datetime.now() - timedelta(hours=5)

        mgr.check(_make_state(percent=10), {"thresholds": {}})

        mock_toaster.show_toast.assert_called_once()
```

**No-fire suppression pattern** (used for cooldown, above-threshold, None-percent tests):
```python
        mock_toaster.show_toast.assert_not_called()
```

---

## Shared Patterns

### In-memory dict keyed by `(vid, pid, dev_idx)`
**Source:** `src/monitor/registry.py` lines 24-26 (`_devices` dict) and `src/ui/main_window.py` line 90 (`_cards` dict)
**Apply to:** `NotificationManager._last_notified`
```python
# Both existing patterns use the same three-tuple key:
self._devices: dict[tuple[int, int, int], DeviceState] = {}   # registry.py
self._cards:   dict[tuple[int, int, int], object]     = {}    # main_window.py
# NotificationManager follows the same convention:
self._last_notified: dict[tuple[int, int, int], datetime] = {}
```

### Config load/merge pattern
**Source:** `src/ui/settings_manager.py` lines 37-52
**Apply to:** `NotificationManager.check()` config access, `_DEFAULTS` extension
```python
# _DEFAULTS merge ensures missing keys are filled without KeyError:
return {**_DEFAULTS, **data}
# NotificationManager uses .get() with defaults for nested keys:
thresholds = config.get("thresholds", {})
device_cfg = thresholds.get(f"{state.vid}:{state.pid}", {})
```

### Null-guard before numeric comparison
**Source:** `src/ui/settings_manager.py` lines 75-76 (`battery_color`) and RESEARCH.md Pitfall 3
**Apply to:** `NotificationManager.check()` before threshold comparison
```python
if percent is None:
    return "#888888"  # settings_manager.py pattern — early return on None
# NotificationManager mirrors this:
if state.percent is None:
    return
```

### pytest-mock `mocker.patch` / `unittest.mock.patch` test pattern
**Source:** `tests/test_ui_settings.py` lines 115-133
**Apply to:** `tests/test_notification_manager.py` — patching `WindowsToaster`
```python
# test_ui_settings.py style (mocker fixture from pytest-mock):
mock_open = mocker.patch("ui.settings_manager.winreg.OpenKey")
# test_notification_manager.py equivalent (unittest.mock.patch context manager):
with patch("ui.notification_manager.WindowsToaster") as MockToaster:
```

### Module docstring convention (no Qt imports)
**Source:** `src/ui/settings_manager.py` lines 1-9
**Apply to:** `src/ui/notification_manager.py`
```python
"""Settings persistence ... for PeriphWatcher.
...
No Qt imports here — pure stdlib so tests run headlessly.
"""
```

## No Analog Found

All files have close analogs. No entries.

## Metadata

**Analog search scope:** `src/ui/`, `src/monitor/`, `tests/`, `src/__main__.py`
**Files scanned:** 9 source files, 3 test files
**Pattern extraction date:** 2026-06-04
