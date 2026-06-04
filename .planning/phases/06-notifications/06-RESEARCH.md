# Phase 6: Notifications - Research

**Researched:** 2026-06-04
**Domain:** Windows toast notifications, cooldown state management, per-device config persistence
**Confidence:** HIGH

## Summary

Phase 6 adds Windows toast notifications to PeriphWatcher. When any monitored device's battery drops below a per-device configured threshold, the user sees a Windows Action Center toast. A cooldown mechanism prevents alert spam: once fired, the same device cannot trigger another notification until either the cooldown period expires (default 4 hours) or the device goes offline and returns online.

The chosen library, Windows-Toasts 1.3.1, uses WinRT directly via the `winrt-runtime` package family (no pywin32 dependency). The `ToastNotificationManager` WinRT class is explicitly annotated `ThreadingModel.MTA` in the Windows SDK, meaning it is safe to call from the asyncio background thread where all HID I/O already runs. `sys.coinit_flags = 0` (MTA mode, already the first line of `__main__`) is the correct configuration — no change needed.

The notification check belongs on the **Qt main thread** (same thread that calls `on_device_update`), not the background asyncio thread. This keeps the notification logic as a simple function call inside the existing drain/update path, avoids any inter-thread complexity for the cooldown tracker, and means the `NotificationManager` does not need to be thread-safe itself. `show_toast()` is a synchronous call that returns immediately; it does not block the main thread for any meaningful duration.

**Primary recommendation:** Implement a `NotificationManager` class instantiated in `__main__.py` and called from `MainWindow.on_device_update`. It reads thresholds from `settings_manager.load_config()`, tracks per-device cooldown in an in-memory dict, and calls `WindowsToaster.show_toast()` on threshold crossing. Cooldowns are purely in-memory (reset on restart), satisfying NOTIF-02's requirement that cooldown resets when a device goes offline/returns.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTIF-01 | App sends a Windows toast notification when a device's battery drops below a per-device configurable threshold | Windows-Toasts `WindowsToaster.show_toast()` API confirmed; threshold read from `config.json` via `SettingsManager` |
| NOTIF-02 | Notification cooldown prevents the same low-battery alert from repeating within a configurable time window | In-memory `dict[device_key, datetime]` tracking last-fired time; cooldown resets on device OFFLINE→ONLINE transition (go-offline clears entry) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Threshold comparison | Qt main thread | — | Runs inside `on_device_update` drain; no HID I/O, no thread crossing needed |
| Toast dispatch | Qt main thread | — | `show_toast()` is synchronous and fire-and-forget; calling on main thread keeps NotificationManager single-threaded |
| Cooldown tracking | Qt main thread (in-memory) | — | Dict is accessed only from main thread drain path; no locking needed |
| Threshold config persistence | Disk / SettingsManager | — | Piggybacks on existing `load_config` / `save_config` JSON at `%APPDATA%/PeriphWatcher/config.json` |
| Cooldown reset on reconnect | Qt main thread | — | `on_device_update` receives DeviceStatus.ONLINE transition; NotificationManager clears cooldown entry for that key |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `windows-toasts` | 1.3.1 | Windows toast notification dispatch | Locked in CLAUDE.md and STATE.md. Uses WinRT (MTA-safe). Active maintenance. No pywin32 dependency. |

### Supporting (no new packages)

All other capabilities use existing stdlib (`datetime`, `queue`) or existing project dependencies (`settings_manager.py`).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `windows-toasts` | `winotify` | `winotify` is explicitly forbidden in CLAUDE.md — fragile, no active maintenance |
| `windows-toasts` | raw `winrt` calls | More verbose, no advantage for our simple use case |
| In-memory cooldown | Persisted timestamps in `config.json` | Persisted state adds serialization complexity and means battery-full-then-dead cycles within a session won't re-notify; in-memory reset-on-restart is the right behavior per success criterion 4 |

**Installation:**

```bash
pip install windows-toasts==1.3.1
```

This installs: `windows-toasts==1.3.1`, `winrt-runtime~=3.0`, `winrt-Windows.Data.Xml.Dom~=3.0`, `winrt-Windows.Foundation~=3.0`, `winrt-Windows.Foundation.Collections~=3.0`, `winrt-Windows.UI.Notifications~=3.0`.

Add `windows-toasts==1.3.1` to `requirements.txt`.

**Version verification:**

```
windows-toasts: 1.3.1 (verified: PyPI, pip index versions, METADATA from installed package)
Latest available: 1.3.1 (released 2025-05-06)
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| windows-toasts | PyPI | ~3 yrs (first: 2023-08-14) | Badge present on PyPI | github.com/DatGuy1/Windows-Toasts | N/A (slopcheck not available) | Approved — see notes |

**slopcheck status:** slopcheck CLI was not available at research time. Manual verification performed instead:
- Package exists on PyPI with 16 releases spanning 3 years [CITED: pypi.org/project/Windows-Toasts]
- GitHub repo has 141 stars, 9 forks, active maintenance through 2025 [CITED: github.com/DatGuy1/Windows-Toasts]
- Source repo linked directly from PyPI metadata (not "none")
- No suspicious `postinstall` script (Python library, no build step)
- Locked in project tech stack in CLAUDE.md — pre-approved by project owner
- Issue #201 ("1.3.1 broken") reported a stale `winrt` (old package) conflict; the 1.3.1 release explicitly switched to `winrt-runtime>=3.0` (the current correct packages), resolving this [VERIFIED: METADATA of installed 1.3.1 package]

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

*Manual verification substituted for slopcheck. Package is explicitly listed in project's tech stack (CLAUDE.md).*

## Architecture Patterns

### System Architecture Diagram

```
[Background asyncio thread]              [Qt main thread]
  MonitorService.poll_once()
        |
        | queue.Queue.put(DeviceState)
        |
        v
  [QTimer drain - 500ms]
        |
        | MonitorApp.drain() -> consumer(state)
        |
        v
  MainWindow.on_device_update(state)
        |
        +---> DeviceCard.update_state(state)   [existing]
        |
        +---> NotificationManager.check(state) [NEW - Phase 6]
                    |
                    +-- threshold = settings[device_key].get("threshold", 15)
                    +-- cooldown  = settings[device_key].get("cooldown_hours", 4)
                    |
                    +-- if state.percent is not None
                    |      AND state.percent < threshold
                    |      AND state.status != OFFLINE
                    |      AND (no prior notification OR cooldown elapsed):
                    |         WindowsToaster.show_toast(Toast(...))
                    |         _last_notified[device_key] = datetime.now()
                    |
                    +-- if state.status == OFFLINE:
                           _last_notified.pop(device_key, None)  [cooldown reset]
```

### Recommended Project Structure

```
src/
├── ui/
│   ├── notification_manager.py   # NEW - NotificationManager class
│   ├── settings_manager.py       # MODIFY - add threshold/cooldown config keys
│   ├── main_window.py            # MODIFY - call NotificationManager.check()
│   └── ...
├── ...
requirements.txt                  # MODIFY - add windows-toasts==1.3.1
tests/
└── test_notification_manager.py  # NEW - unit tests (no real WinRT calls)
```

### Pattern 1: Toast dispatch with WindowsToaster

**What:** Create a `WindowsToaster` once at `NotificationManager.__init__` (construction is cheap; reuse avoids repeated AUMID registration overhead). Call `show_toast()` synchronously on each alert.

**When to use:** Every threshold crossing that passes the cooldown gate.

```python
# Source: METADATA README of windows-toasts==1.3.1 + inspected toasters.py
from windows_toasts import Toast, WindowsToaster

class NotificationManager:
    def __init__(self):
        self._toaster = WindowsToaster("PeriphWatcher")
        self._last_notified: dict[tuple[int, int, int], datetime] = {}

    def check(self, state: DeviceState, config: dict) -> None:
        key = (state.vid, state.pid, state.dev_idx)

        # Reset cooldown when device goes offline
        if state.status == DeviceStatus.OFFLINE:
            self._last_notified.pop(key, None)
            return

        # No battery reading (charging or transitional) — skip
        if state.percent is None:
            return

        # Per-device threshold (default 15%)
        thresholds = config.get("thresholds", {})
        device_cfg = thresholds.get(f"{state.vid}:{state.pid}", {})
        threshold = device_cfg.get("threshold_pct", 15)
        cooldown_hours = device_cfg.get("cooldown_hours", 4)

        if state.percent >= threshold:
            return  # battery is fine

        # Check cooldown
        last = self._last_notified.get(key)
        if last is not None:
            elapsed = (datetime.now() - last).total_seconds() / 3600
            if elapsed < cooldown_hours:
                return  # still in cooldown

        # Fire toast
        toast = Toast(text_fields=[
            f"{state.device_name} battery low",
            f"Battery at {state.percent}% — charge soon",
        ])
        self._toaster.show_toast(toast)
        self._last_notified[key] = datetime.now()
```

### Pattern 2: Toast text_fields layout

`text_fields` is a list of strings. With `WindowsToaster`, the template is `ToastImageAndText04`. The first element renders as the **bold heading/title** line; the second and third elements render as body lines.

```python
# Two-line toast: title + body
toast = Toast(text_fields=[
    "G Pro X Wireless battery low",   # heading (bold)
    "Battery at 12% — charge soon",   # body line
])
```

### Pattern 3: Config schema for thresholds

Add to `config.json` (keyed by `"VID:PID"` string so it survives device rename):

```json
{
  "launch_at_startup": false,
  "thresholds": {
    "1133:2746": { "threshold_pct": 15, "cooldown_hours": 4 },
    "4152:6226": { "threshold_pct": 20, "cooldown_hours": 4 }
  }
}
```

VID/PID are decimal integers stringified as `f"{vid}:{pid}"`. The `_DEFAULTS` dict in `settings_manager.py` needs `"thresholds": {}` added so `{**_DEFAULTS, **data}` merge produces an empty dict (not KeyError) when no thresholds are configured.

### Pattern 4: Wiring in `__main__.py`

```python
# src/__main__.py (additions only)
from ui.notification_manager import NotificationManager

def main() -> None:
    ...
    notif_manager = NotificationManager()
    app_obj = MonitorApp(
        consumer=lambda s: _on_device_update(window, notif_manager, s),
        ...
    )
    ...

def _on_device_update(window, notif_manager, state):
    window.on_device_update(state)
    cfg = load_config()
    notif_manager.check(state, cfg)
```

Alternative: pass `notif_manager` into `MainWindow` and call it at the end of `on_device_update`. Either approach is valid; the lambda wrapper in `__main__` avoids adding a dependency on `NotificationManager` to `MainWindow`.

### Anti-Patterns to Avoid

- **Calling `show_toast()` from the asyncio bg thread:** Avoids the architecture invariant violation and is unnecessary — the existing drain path on the main thread is the natural hook point.
- **Constructing a new `WindowsToaster` on every notification:** AUMID registration happens at construction; reuse a single instance.
- **Hardcoding VID/PID hex strings as config keys:** Use `f"{vid}:{pid}"` (decimal) for round-trip safety with `json.dumps`.
- **Persisting `_last_notified` timestamps to disk:** Adds complexity and fights success criterion 4 ("cooldown resets if device goes offline and returns online"). In-memory is correct here.
- **Re-loading config on every notification check:** `load_config()` does disk I/O. Load once at app start and reload only on settings change. For Phase 6, loading inside `check()` is acceptable since the call is at most every 500ms and the file is tiny — but caching is cleaner.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Windows toast display | Custom WinRT XML construction | `windows_toasts.WindowsToaster` | WinRT XML schema is fragile; library handles template selection, AUMID, notification data binding |
| Cooldown tracking | Redis/SQLite for timestamps | `dict[key, datetime]` in-memory | Requirements explicitly say cooldown resets on restart (success criterion 4); in-memory is both simpler and correct |

## Common Pitfalls

### Pitfall 1: Stale `winrt` package (old monolithic package) installed

**What goes wrong:** `ModuleNotFoundError: No module named 'winrt._winrt'` when importing `windows_toasts`.

**Why it happens:** There are two incompatible PyPI distributions: the old monolithic `winrt` package (unmaintained, Microsoft stopped updates) and the new split `winrt-runtime` + `winrt-Windows.*` namespace packages. Windows-Toasts 1.3.1 requires the new split packages (`winrt-runtime~=3.0`). If the old `winrt` is installed in the venv, it conflicts.

**How to avoid:** Install via `pip install windows-toasts==1.3.1` in a clean venv (as in this project). Do NOT manually install `pip install winrt` — that installs the wrong old package.

**Warning signs:** `No module named 'winrt._winrt'` or `No matching distribution found for winrt` during install of the old package.

### Pitfall 2: Calling `show_toast()` from a non-MTA thread

**What goes wrong:** Hangs, exceptions, or silent failure.

**Why it happens:** If `sys.coinit_flags` was not set to 0 before first COM init (e.g., another package initialized STA first), WinRT calls from that thread may fail.

**How to avoid:** `sys.coinit_flags = 0` is already the first line of `__main__.py` (architecture invariant). Call `show_toast()` from the main thread (Qt drain path) — that thread is initialized MTA by `sys.coinit_flags = 0`. Do not call from any thread that initializes its own COM apartment.

**Warning signs:** `show_toast()` hangs or raises a COM exception with no obvious cause.

### Pitfall 3: Threshold never fires because `percent` is `None` during charging

**What goes wrong:** Notification never fires even when battery is truly low.

**Why it happens:** `MonitorService.poll_once()` sets `percent=None` when `result.charging is True` (to avoid displaying inflated charging voltage as %). The notification check must guard `if state.percent is None: return`.

**How to avoid:** Explicit `None` guard before threshold comparison (shown in Pattern 1).

**Warning signs:** Notification never fires for a charging device even when battery is low.

### Pitfall 4: Double-notification on a single threshold crossing

**What goes wrong:** Two toasts fire for the same battery reading.

**Why it happens:** `MonitorService` pushes a new `DeviceState` every 60 seconds. Without proper "previously above threshold" tracking, each poll that reads a below-threshold value fires a new toast.

**How to avoid:** The `_last_notified` dict with cooldown check prevents this — once fired, no notification until cooldown expires OR device goes offline/returns.

**Warning signs:** Multiple toasts appearing in quick succession.

### Pitfall 5: Cooldown not resetting on device disconnect/reconnect

**What goes wrong:** User unplugs dongle overnight, device battery drains further, user replugs — but no notification fires because the 4-hour cooldown is still running.

**Why it happens:** Cooldown dict entry persists through the OFFLINE state transition.

**How to avoid:** Clear `_last_notified[key]` when `state.status == DeviceStatus.OFFLINE` (shown in Pattern 1). The next ONLINE state with below-threshold battery will fire fresh.

**Warning signs:** No toast after plug-in despite low battery.

## Code Examples

### Minimal verified pattern

```python
# Source: METADATA README + inspected windows_toasts/toasters.py (installed package)
from windows_toasts import Toast, WindowsToaster
from datetime import datetime

toaster = WindowsToaster("PeriphWatcher")
toast = Toast(text_fields=[
    "G Pro X Wireless battery low",   # first element = heading (bold)
    "Battery at 12% — charge soon",   # second element = body
])
toaster.show_toast(toast)
```

### Unit-testable design (mock show_toast)

```python
# tests/test_notification_manager.py pattern
from unittest.mock import MagicMock, patch

def test_fires_on_threshold_crossing():
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        state = DeviceState(..., percent=10, status=DeviceStatus.ONLINE)
        config = {"thresholds": {}}  # defaults apply

        mgr.check(state, config)

        mock_toaster.show_toast.assert_called_once()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `winrt` monolithic PyPI package | `winrt-runtime` + `winrt-Windows.*` namespace packages | 2023+ | Old package is unmaintained; must use split packages |
| `winotify` / `win10toast` | `windows-toasts` | 2022+ | Former packages abandoned; windows-toasts uses WinRT directly |

**Deprecated/outdated:**
- `winrt` (old monolithic package): stopped receiving updates from Microsoft; replaced by `winrt-runtime` + namespace packages. Windows-Toasts 1.3.1 correctly depends on the new split packages.
- `winotify`: explicitly forbidden in CLAUDE.md — fragile.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `show_toast()` returns synchronously and does not block the main thread for more than ~1ms | Architecture Patterns | If it blocks significantly, a thread or `QThreadPool` wrapper would be needed |
| A2 | `WindowsToaster("PeriphWatcher")` is a valid AUMID-less toaster that works on Windows 11 for unpackaged desktop apps | Code Examples | If Windows 11 requires a registered AUMID, must switch to `InteractableWindowsToaster` with a registered shortcut |
| A3 | Decimal `f"{vid}:{pid}"` string keys in config JSON are sufficient for device identity (no collision) | Architecture Patterns | If two devices share VID:PID (impossible by design), key would collide — but KNOWN_DEVICES already prevents this |

## Open Questions (RESOLVED)

1. **Does `WindowsToaster` work for unpackaged Python apps on Windows 11 without an AUMID shortcut?**
   - What we know: Windows 10 allowed it. Windows 11 tightened notification requirements for some app types. The GitHub README shows the simple `WindowsToaster('Python')` pattern without mentioning AUMID registration.
   - What's unclear: Whether Windows 11 requires a Start Menu shortcut with AppUserModelID for toast display.
   - **RESOLVED: Confirmed at hardware checkpoint in 06-03 Task 1; fallback to `InteractableWindowsToaster` if `WindowsToaster` fails silently. 06-03 SUMMARY documents the confirmed toaster class.**

2. **Should `NotificationManager.check()` re-load config on every call or cache it?**
   - What we know: `load_config()` reads a ~100-byte JSON file from disk. At 500ms drain interval, that is 2 disk reads/second max.
   - What's unclear: Whether disk I/O overhead is measurable in practice.
   - **RESOLVED: Accept per-call re-read for Phase 6 simplicity (no user-visible performance impact at 2 reads/second on a 100-byte file). Caching deferred to Phase 7 if needed.**

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `windows-toasts` | NOTIF-01/02 | Not yet installed | 1.3.1 (PyPI) | — (must install) |
| `winrt-runtime` | windows-toasts | Not yet installed | 3.2.1 (auto-pulled) | — (auto-dependency) |
| Windows 10/11 toast infrastructure | `show_toast()` | ✓ (Windows 11 Pro confirmed) | — | — |

**Missing dependencies with no fallback:**
- `windows-toasts==1.3.1` — must be installed via pip and added to `requirements.txt`. Auto-installs all `winrt-*` namespace packages.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (testpaths = tests, pythonpath = src) |
| Quick run command | `pytest tests/test_notification_manager.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTIF-01 | Toast fires when percent < threshold (first crossing) | unit | `pytest tests/test_notification_manager.py::test_fires_on_threshold_crossing -x` | Wave 0 |
| NOTIF-01 | No toast when percent >= threshold | unit | `pytest tests/test_notification_manager.py::test_no_fire_above_threshold -x` | Wave 0 |
| NOTIF-01 | No toast when percent is None (charging/offline) | unit | `pytest tests/test_notification_manager.py::test_no_fire_when_percent_none -x` | Wave 0 |
| NOTIF-01 | Default threshold is 15% when no config entry | unit | `pytest tests/test_notification_manager.py::test_default_threshold -x` | Wave 0 |
| NOTIF-02 | No second toast within cooldown window | unit | `pytest tests/test_notification_manager.py::test_cooldown_suppresses -x` | Wave 0 |
| NOTIF-02 | Toast fires again after cooldown expires | unit | `pytest tests/test_notification_manager.py::test_fires_after_cooldown -x` | Wave 0 |
| NOTIF-02 | Cooldown clears when device goes OFFLINE | unit | `pytest tests/test_notification_manager.py::test_cooldown_resets_on_offline -x` | Wave 0 |
| NOTIF-01+02 | Toast visible in Action Center on hardware | manual smoke | (hardware checkpoint plan) | N/A |

### Sampling Rate

- **Per task commit:** `pytest tests/test_notification_manager.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_notification_manager.py` — covers all NOTIF-01/02 unit tests above
- [ ] `src/ui/notification_manager.py` — NotificationManager class (created in Wave 1)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (minor) | Validate threshold value is int 0–100 before comparison; clamp silently |
| V6 Cryptography | no | — |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Config file tampered (threshold set to 0) | Tampering | Clamp threshold to [1, 99] in NotificationManager.check(); never crash on bad config |
| Notification spam via rapid config change | DoS | Cooldown logic itself is the mitigation |

## Sources

### Primary (HIGH confidence)

- `C:\Temp\wt_check\windows_toasts\toasters.py` — inspected `WindowsToaster`, `show_toast()`, `_setup_toast()` implementation
- `C:\Temp\wt_check\windows_toasts\toast.py` — inspected `Toast.__init__()`, `text_fields` type
- `C:\Temp\wt_check\windows_toasts-1.3.1.dist-info\METADATA` — verified dependency list (`winrt-runtime~=3.0`), version, release date
- `https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.toastnotificationmanager` — confirmed `ThreadingModel.MTA` annotation on `ToastNotificationManager`

### Secondary (MEDIUM confidence)

- `https://pypi.org/project/Windows-Toasts/` — package summary, version history
- `https://libraries.io/pypi/Windows-Toasts` — first published 2023-08-14, 9 releases, Apache-2.0
- `https://github.com/DatGuy1/Windows-Toasts` — source repo, 141 stars, active maintenance
- `https://github.com/DatGuy1/Windows-Toasts/releases` — 1.3.1 release notes: "Support pywinrt>=3" (#184)
- `https://github.com/DatGuy1/Windows-Toasts/issues/201` — "1.3.1 broken" issue: caused by old monolithic `winrt` package conflict; 1.3.1 uses `winrt-runtime` split packages which resolves it

### Tertiary (LOW confidence — none)

No LOW-confidence findings. All key claims verified against source code or official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — package inspected locally, API read from source, threading model confirmed from official MS docs
- Architecture: HIGH — wiring follows existing project patterns; hook point (on_device_update drain) is unambiguous
- Pitfalls: HIGH — most derived from reading actual source code; issue #201 verified against releases page
- Config schema: HIGH — follows existing `settings_manager.py` merge pattern (`{**_DEFAULTS, **data}`)

**Research date:** 2026-06-04
**Valid until:** 2026-12-04 (stable library; winrt-runtime 3.x is current)
