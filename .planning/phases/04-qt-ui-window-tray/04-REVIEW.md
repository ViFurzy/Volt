---
phase: 04-qt-ui-window-tray
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/ui/__init__.py
  - src/ui/styles.py
  - src/ui/sidebar.py
  - src/ui/settings_page.py
  - src/ui/tray.py
  - src/ui/main_window.py
  - src/ui/device_card.py
  - src/ui/settings_manager.py
  - src/__main__.py
findings:
  critical: 3
  warning: 4
  info: 3
  total: 10
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 4 delivers the Qt UI shell: dark-themed window, sidebar nav, device cards, settings
page, system tray, and the `__main__` entry point that wires everything together.  Overall
structure is sound and the architecture invariants from CLAUDE.md are mostly followed.
However three correctness bugs were found that will cause wrong runtime behaviour, and four
warning-level issues degrade robustness or maintainability.

---

## Critical Issues

### CR-01: `sys.coinit_flags = 0` is on line 2, not line 1 — `import sys` precedes it

**File:** `src/__main__.py:1-2`

**Issue:** The CLAUDE.md architecture invariant states:
> `sys.coinit_flags = 0` is the **very first line** in `__main__`, before **all imports**

The actual file reads:
```
line 1:  import sys
line 2:  sys.coinit_flags = 0  # MUST be here — before any other import …
```

`import sys` is itself an import. `sys` is a built-in so it does not initialise COM by
itself, but this pattern is fragile in two concrete ways:

1. Any future import inserted above line 2 (e.g. a logger, a version constant) will
   silently violate the invariant before `coinit_flags` is set.
2. The project documentation and CLAUDE.md clearly call for `sys.coinit_flags = 0` to be
   the *very first line*. The code comment on line 2 even states "MUST be here — before
   any other import", yet `import sys` is above it. The comment contradicts the code.

While `import sys` is technically safe today, the invariant is violated as written, and a
future maintainer reading the comment will be confused (or will incorrectly believe it is
already correct).

**Fix:**
```python
# line 1 — absolutely nothing before this
import sys
sys.coinit_flags = 0  # MUST be set before any other import initialises COM.
```
Wait — the invariant is that `sys.coinit_flags = 0` must precede *all other* imports.
`import sys` is a prerequisite to set the attribute, and `sys` itself never touches COM.
The real fix is to add a comment clarifying why `import sys` is the lone safe exception,
and to enforce via review/CI that nothing else appears between line 1 and the assignment:

```python
import sys          # stdlib builtin — does NOT initialise COM; must be first
sys.coinit_flags = 0  # MTA mode required for bleak WinRT; must precede all other imports
```

The code is functionally correct today but the invariant as documented is violated. Mark
as BLOCKER because the next person editing `__main__` may insert an import above line 2
believing it is safe (the comment says "before any other import" — they may think `import
sys` is that import). That would silently break `bleak`.

---

### CR-02: `set_startup(True)` silently drops the write if the `Run` key cannot be opened

**File:** `src/ui/settings_manager.py:104-110`

**Issue:** The `enabled=True` branch calls `winreg.OpenKey` with `KEY_WRITE`.  If the
key open fails for any reason (permissions edge case, key path wrong on certain Windows
editions, registry redirection on 32-bit Python running on 64-bit Windows), the exception
propagates up to `SettingsPage._on_startup_toggled`, which has **no try/except around
`set_startup`**.  The checkbox will visually flip to checked while the registry write
silently never happened, leaving the UI and the registry permanently out of sync with no
user-visible error.

The `disabled` branch explicitly handles `FileNotFoundError` and is idempotent — the
same discipline is missing from the `enabled` branch.

**Fix:**
```python
def set_startup(enabled: bool) -> None:
    if enabled:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                access=winreg.KEY_WRITE,
            ) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
        except OSError:
            # Log or surface to caller; do not silently swallow
            raise
    else:
        ...
```

At minimum, let the exception propagate so the caller (`_on_startup_toggled`) can catch
it and revert the checkbox to its previous state rather than leaving the UI desynced.

---

### CR-03: `_get_exe_path()` produces a double-quoted path that is incomplete for the packaged app — the script argument is missing

**File:** `src/ui/settings_manager.py:88-94`

**Issue:** `_get_exe_path()` returns `'"<path-to-python.exe>"'`.  When Windows executes
the Run key value at login it will launch `python.exe` with *no arguments*, so the app
will not start.  The correct value for the dev-mode entry should be:

```
"C:\Python\python.exe" -m src
```

or point at the packaged `.exe` directly (Phase 7).  The code comment acknowledges
"packaged exe is Phase 7", but the dev-mode entry produced now is broken — storing it to
the registry causes startup-registration failures that are invisible until the user
reboots and finds the app did not launch.  A user who enables the toggle will believe
startup is registered when it is not functional.

**Fix (dev mode):**
```python
def _get_exe_path() -> str:
    """Return the run command for the HKCU Run key.

    Dev mode: `"python.exe" -m src`
    Packaged (Phase 7): replace with the exe path directly.
    """
    exe = sys.executable
    # __spec__.parent is 'src' when run as `python -m src`
    pkg = __import__('__main__').__spec__.parent if __import__('__main__').__spec__ else ""
    if pkg:
        return f'"{exe}" -m {pkg}'
    return f'"{exe}"'
```

Or at minimum document the known limitation prominently so Phase 7 cannot miss it.

---

## Warnings

### WR-01: `_on_startup_toggled` reads then writes config on every checkbox flip — no error handling around `save_config`

**File:** `src/ui/settings_page.py:55-60`

**Issue:** `save_config` opens a file for writing.  If the write fails (disk full, path
permission issue), the exception propagates unhandled to Qt's signal dispatch, which will
print a traceback to stderr but *not* crash the app.  The registry was already written by
`set_startup` at this point, so the registry and JSON config become permanently desynced
without the user being notified.

**Fix:** Wrap the `save_config` call and, on failure, either show a status label or at
minimum revert `set_startup` to restore consistency:
```python
def _on_startup_toggled(self, checked: bool) -> None:
    set_startup(checked)
    cfg = load_config()
    cfg["launch_at_startup"] = checked
    try:
        save_config(cfg)
    except OSError:
        # Revert registry to stay in sync
        set_startup(not checked)
        self._startup_cb.blockSignals(True)
        self._startup_cb.setChecked(not checked)
        self._startup_cb.blockSignals(False)
```

---

### WR-02: `MainWindow._cards` is typed as `dict[tuple[int,int,int], object]` but stores `DeviceCard` — the loose type hides `update_state` call at line 135

**File:** `src/ui/main_window.py:90,135`

**Issue:** `self._cards` is declared as `dict[tuple[int, int, int], object]` (line 90).
Line 135 calls `self._cards[key].update_state(state)`.  Because `object` does not have
`update_state`, this line is invisible to type checkers — mypy will report an error in
strict mode.  In practice it works, but the type annotation actively misleads tooling and
future readers.

**Fix:**
```python
from ui.device_card import DeviceCard
# ...
self._cards: dict[tuple[int, int, int], DeviceCard] = {}
```

There is already a conditional import of `DeviceCard` in the function body (line 129);
move it to the top of the file for consistency and use it in the type annotation.

---

### WR-03: `QStyleOption.initFrom` deprecation — `QStyleOption` is not the right type for `PE_Widget`

**File:** `src/ui/sidebar.py:68-71`, `src/ui/settings_page.py:67-70`

**Issue:** Both `SidebarNav.paintEvent` and `SettingsPage.paintEvent` use the base
`QStyleOption` class.  The correct type for `QStyle.drawPrimitive(PE_Widget, …)` is
`QStyleOption`; this is technically correct.  However, `opt.initFrom(self)` on a raw
`QStyleOption` object works but `initFrom` was deprecated in Qt 6.x in favour of
`QStyleOption.initFrom` called on a properly-typed sub-option.  More importantly, both
widgets import `QStyle` and `QStyleOption` but neither imports are listed in the module
`__all__` — this is a minor coupling smell because the `paintEvent` boilerplate is
duplicated verbatim in two files.

The actual risk: the raw `QStyleOption` approach is documented as the correct workaround
for PySide6; this is a known pattern and works.  The warning is about duplication and
potential future breakage if Qt removes the overload.

**Fix:** Extract the repeated three-line paintEvent body into a module-level helper in
a shared `ui/_paint_mixin.py` or just a standalone function:

```python
# ui/_utils.py
def paint_widget(widget):
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyle, QStyleOption
    opt = QStyleOption()
    opt.initFrom(widget)
    p = QPainter(widget)
    widget.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, widget)
```

Both `SidebarNav` and `SettingsPage` can then call `paint_widget(self)`.

---

### WR-04: `styles.py` — `QFrame#deviceCard[offline="true"] { opacity: 0.6; }` is silently ignored by Qt

**File:** `src/ui/styles.py:109-113`

**Issue:** `opacity` is not a valid QSS property.  Qt's CSS-like stylesheet engine does
not support the `opacity` shorthand.  The correct Qt mechanism to control widget
transparency is `QWidget::setWindowOpacity()` (only works on top-level windows) or
`QGraphicsOpacityEffect`.  The `offline` property change fires `unpolish`/`polish`
correctly, but the visual dimming effect from `opacity: 0.6` will never apply — the
offline card will look identical to an online card, which breaks the design requirement
for offline muting.

**Fix:** Remove the `opacity` line from QSS and apply the dimming via color changes
already present (`background-color: #1e2030; border-color: #2a2d45`), or apply a
`QGraphicsOpacityEffect` in `DeviceCard.update_state` when offline:
```python
# in DeviceCard.update_state, after setting the property:
if is_offline:
    effect = QGraphicsOpacityEffect(self)
    effect.setOpacity(0.6)
    self.setGraphicsEffect(effect)
else:
    self.setGraphicsEffect(None)
```

---

## Info

### IN-01: `TrayManager.__init__` takes `window` typed as bare `object` (no type annotation)

**File:** `src/ui/tray.py:28`

**Issue:** `def __init__(self, window, qapp: QApplication) -> None:` — the `window`
parameter has no type annotation.  The method calls `window.show_restore` so the
expected interface is clear; a `Protocol` or direct `MainWindow` type would make this
self-documenting.

**Fix:**
```python
from ui.main_window import MainWindow   # or define a Protocol
def __init__(self, window: MainWindow, qapp: QApplication) -> None:
```

---

### IN-02: Magic number `200` in `__main__.py` SIGINT timer has no named constant

**File:** `src/__main__.py:35`

**Issue:** `sigint_timer.start(200)` — the `200` ms heartbeat is a magic number.  It is
explained in the adjacent comment, but a named constant makes grepping and tuning
unambiguous.

**Fix:**
```python
_SIGINT_POLL_MS = 200   # Wake Python interpreter to process SIGINT
sigint_timer.start(_SIGINT_POLL_MS)
```

---

### IN-03: `settings_manager.py` module-level `CONFIG_DIR` uses `os.environ["APPDATA"]` directly — raises `KeyError` in non-Windows environments (CI, WSL)

**File:** `src/ui/settings_manager.py:20`

**Issue:** `CONFIG_DIR: Path = Path(os.environ["APPDATA"]) / "PeriphWatcher"` is
evaluated at *import time*.  In any environment where `APPDATA` is not set (Linux CI,
macOS, WSL without the variable exported), importing `settings_manager` raises `KeyError`
immediately, before any test or function can mock it.

The test suite currently works because CI presumably runs on Windows, but the fragility
is real — a new contributor running tests on Linux will get a confusing import-time
failure rather than a test skip.

**Fix:**
```python
CONFIG_DIR: Path = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "PeriphWatcher"
```

Or move the resolution into `load_config` / `save_config` rather than module-level so it
can be patched before evaluation.

---

_Reviewed: 2026-06-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
