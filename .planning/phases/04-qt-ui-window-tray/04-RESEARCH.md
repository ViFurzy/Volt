# Phase 4: Qt UI — Window + Tray — Research

**Researched:** 2026-06-02
**Domain:** PySide6 6.11.1, QSystemTrayIcon, QMainWindow, winreg, QSS dark theme, JSON settings
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Dark theme from VOLT | POWER CENTER spec. Background `#202535`, elevated surface `#262355`, text `#FFFFFF`. Battery colors: normal (>45%) = teal/neutral, warning (≤45%) = amber, critical (≤8%) = red. Global QApplication stylesheet.
- **D-02:** Text-only battery display. Device card: device name (large), battery % as large text, status dot (ONLINE/OFFLINE/CHARGING), charging indicator. No circular gauge.
- **D-03:** Full sidebar skeleton — Dashboard, Devices, History, Profiles, Settings. Dashboard and Settings active; History and Profiles show "Coming soon" QLabel.
- **D-04:** Sidebar uses icon + label style. Active item: filled/highlighted indicator. Width: Claude's discretion (~64px icons-only or ~160px with labels).
- **D-05:** "Launch at startup" toggle in Settings tab writes/removes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` key `PeriphWatcher` via stdlib `winreg`. No admin rights required.
- **D-06:** Settings file: `%APPDATA%\PeriphWatcher\config.json`. Schema: `{"launch_at_startup": false}`. Create directory if absent.
- **D-07:** Static tray icon (PNG/ICO). Tray context menu: "Show" + separator + "Quit". Double-click restores main window.
- **D-08:** Close (X) hides window — does NOT quit. `closeEvent` calls `hide()` and `event.ignore()`. `QApplication.quit()` only from tray "Quit" item.

### Claude's Discretion

- Exact sidebar width and whether labels appear alongside icons
- Specific icon assets (SVG/PNG) for sidebar and tray (create minimal placeholders)
- Device card grid layout (1-column vs 2-column vs wrapping)
- Window default size and whether size is persisted (not required by SYS-02)
- Config file load/save helper implementation details

### Deferred Ideas (OUT OF SCOPE)

- Circular ring battery gauge
- Dynamic tray icon with battery %
- Settings screen for notification thresholds
- Window geometry persistence
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | Main window lists all monitored devices with name, battery %, and charging status | QMainWindow + QStackedWidget Dashboard page; device card widget consuming DeviceState |
| UI-02 | Closing the main window minimizes to system tray (does not quit) | closeEvent override + event.ignore() + hide(); QApplication.setQuitOnLastWindowClosed(False) |
| UI-03 | System tray icon present; double-click or context menu restores window | QSystemTrayIcon + activated signal ActivationReason.DoubleClick + QMenu "Show"/"Quit" |
| SYS-01 | Register in Windows startup, launch minimized to tray | winreg HKCU\...\Run key, toggle in Settings tab, path quoting |
| SYS-02 | User settings persist to disk and survive restarts | JSON config at %APPDATA%\PeriphWatcher\config.json, pathlib create-if-absent pattern |
</phase_requirements>

---

## Summary

Phase 4 replaces the `mock_consumer` in `run_monitor.py` with a real PySide6 main window that
consumes `DeviceState` snapshots from the existing `MonitorApp.ui_queue` via the already-wired
`QTimer.drain()` mechanism. The MonitorApp API is a stable contract — Phase 4 is purely additive
on the UI side.

The main technical surface areas are: (1) `QSystemTrayIcon` setup and Windows 11 activation
signal behaviour, (2) global QSS dark theme with correct widget coverage, (3) `QStackedWidget`
sidebar navigation with checkable `QPushButton` nav items, (4) `closeEvent` override to
hide-not-quit, (5) `winreg` startup registration, and (6) JSON config persistence with
pathlib directory creation. None of these involve custom protocol work; all are solved problems
with well-documented PySide6 patterns.

One notable Windows 11 gotcha: `QSystemTrayIcon` shows notifications as banners only (they do
not persist in the Action Center), but notifications are out of scope for Phase 4 so this does
not block. The double-click activation path (`ActivationReason.DoubleClick`) works correctly on
Windows 11 for window restoration.

**Primary recommendation:** Wire Phase 4 as a thin UI shell on top of the existing Phase 3
stack — new files for `MainWindow`, `DeviceCard`, `SidebarNav`, `TrayManager`, and a
`SettingsManager` helper; extend `run_monitor.py` (or replace with `__main__.py`) minimally.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Device state polling | Background asyncio thread (MonitorService) | — | Already Phase 3; Phase 4 must not touch this |
| Cross-thread delivery | queue.Queue drained by QTimer | — | Architecture invariant; unchanged |
| Device card rendering | Qt main thread (DeviceCard widget) | — | All Qt widget ops must be on main thread |
| Tray icon lifecycle | Qt main thread (TrayManager) | — | QSystemTrayIcon is a QObject; must stay on main thread |
| Window show/hide | Qt main thread (MainWindow) | — | Qt constraint |
| Startup registration | Main thread at app init / settings toggle | — | winreg is synchronous + instant; no threading needed |
| Settings persistence | Main thread (SettingsManager) | — | JSON read/write is fast; no background I/O required |
| `sys.coinit_flags = 0` | Entry point, line 1, before all imports | — | Architecture invariant; absolutely must not move |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.11.1 | Main window, tray icon, widgets, QSS | Already in project; locked decision |
| Python stdlib `winreg` | — (stdlib) | Startup registry read/write | No third-party dependency; HKCU requires no admin |
| Python stdlib `pathlib` | — (stdlib) | Config file path construction + dir creation | Cleaner than `os.path`; `mkdir(parents=True, exist_ok=True)` |
| Python stdlib `json` | — (stdlib) | Config file serialisation | Simple schema; no need for heavier format |

**Version verification:** `PySide6==6.11.1` is the current release on PyPI as of 2026-05-13 [VERIFIED: PyPI]. It is already pinned in `requirements.txt`.

### Supporting (Test)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-qt | 4.5.0 | QApplication singleton management in pytest; `qapp` fixture | All UI unit tests that need a QApplication |

**pytest-qt version 4.5.0** confirmed current on PyPI (uploaded 2026-07-01) [VERIFIED: PyPI]. Full PySide6 support confirmed. [CITED: pytest-qt.readthedocs.io]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Global QSS string | `qdarktheme`, `QDarkStyle`, `qt-material` | Third-party theme libs add a dependency and override custom brand tokens — not needed; hand-authoring QSS is appropriate for a constrained design spec |
| `pathlib` for AppData path | `QStandardPaths.AppDataLocation` | Both work; `pathlib` + `os.environ["APPDATA"]` is simpler for a non-cross-platform app |
| Checkable `QPushButton` for sidebar | `QListWidget`, `QToolBox` | QPushButton with `:checked` QSS pseudo-state gives full style control; QListWidget theming is harder |

**Installation (new test dependency only):**
```bash
pip install pytest-qt==4.5.0
```

---

## Package Legitimacy Audit

> slopcheck was not available in this environment. All packages are tagged per evidence found
> in official docs and PyPI. The one new package (pytest-qt) is verified below.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| PySide6 | PyPI | ~6 yrs | Very high | github.com/qt-project/pyside-setup | [ASSUMED — slopcheck unavailable] | Approved — official Qt project |
| pytest-qt | PyPI | ~10 yrs | High (established pytest plugin) | github.com/pytest-dev/pytest-qt | [ASSUMED — slopcheck unavailable] | Approved — official pytest-dev org |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable at research time. Both packages have well-established histories
and are published by known organisations (Qt Project, pytest-dev). Planner should add a
`checkpoint:human-verify` before the `pip install pytest-qt` task per protocol.*

---

## Architecture Patterns

### System Architecture Diagram

```
Entry point (run_monitor.py or __main__.py)
  |
  |-- sys.coinit_flags = 0  [line 1, before ALL imports]
  |
  |-- QApplication([])
  |     |-- setStyleSheet(DARK_QSS)          # global brand colors
  |     |-- setQuitOnLastWindowClosed(False) # essential for tray pattern
  |
  |-- MainWindow(QMainWindow)
  |     |-- SidebarNav (QWidget, left)
  |     |     |-- QPushButton[Dashboard] checkable, setChecked(True) on start
  |     |     |-- QPushButton[Devices]   checkable
  |     |     |-- QPushButton[History]   checkable
  |     |     |-- QPushButton[Profiles]  checkable
  |     |     |-- QPushButton[Settings]  checkable
  |     |     '-- QButtonGroup (exclusive)
  |     |
  |     |-- QStackedWidget (right)
  |           |-- page 0: DashboardPage  (QScrollArea > QWidget > QVBoxLayout > DeviceCard*)
  |           |-- page 1: DevicesPage    ("Coming soon" placeholder)  [D-03: History slot]
  |           |-- page 2: HistoryPage    ("Coming soon" QLabel)
  |           |-- page 3: ProfilesPage   ("Coming soon" QLabel)
  |           '-- page 4: SettingsPage   (QCheckBox "Launch at startup")
  |
  |-- TrayManager
  |     |-- QSystemTrayIcon(icon, parent=qapp)
  |     |-- QMenu
  |     |     |-- QAction "Show"  -> mainwindow.show_restore()
  |     |     |-- separator
  |     |     '-- QAction "Quit"  -> qapp.quit()
  |     '-- activated.connect(on_tray_activated)
  |           '-- ActivationReason.DoubleClick -> mainwindow.show_restore()
  |
  |-- MonitorApp(consumer=mainwindow.on_device_update)   [Phase 3 — unchanged]
  |     |-- MonitorService  (asyncio bg thread)
  |     |-- DeviceRegistry
  |     '-- HotPlugWatcher
  |
  |-- QTimer(200ms) -> lambda: None   [SIGINT heartbeat]
  |-- QTimer(500ms) -> app_obj.drain  [queue drain — Phase 3 pattern]
  |
  '-- qapp.exec()
        |
        [DeviceState arrives via queue.Queue]
        |
        mainwindow.on_device_update(state: DeviceState)
          |-- look up card by (vid, pid, dev_idx)
          |-- if not found: create DeviceCard, add to DashboardPage layout
          '-- card.update_state(state)  # update % text, color, status dot
```

### Recommended Project Structure

```
src/
├── monitor/               # Phase 3 — unchanged
│   ├── app.py
│   ├── hotplug.py
│   ├── registry.py
│   ├── service.py
│   └── state.py
├── ui/                    # Phase 4 — new package
│   ├── __init__.py
│   ├── main_window.py     # MainWindow(QMainWindow) + on_device_update()
│   ├── sidebar.py         # SidebarNav widget + QButtonGroup
│   ├── device_card.py     # DeviceCard widget, update_state()
│   ├── tray.py            # TrayManager — QSystemTrayIcon lifecycle
│   ├── settings_page.py   # SettingsPage — startup toggle
│   ├── settings_manager.py # JSON config load/save + winreg read/write
│   └── styles.py          # DARK_QSS constant (or dark_theme.qss file)
├── assets/
│   └── tray_icon.png      # 16x16 (or 32x32 scaled down) placeholder icon
├── __main__.py            # Entry point — extend or replace run_monitor.py
└── run_monitor.py         # Phase 3 entry point — keep for reference; __main__.py supersedes
tests/
├── conftest.py            # existing + add qapp_cls fixture for pytest-qt
├── test_ui_main_window.py # MainWindow instantiation, on_device_update, closeEvent
├── test_ui_device_card.py # DeviceCard.update_state, threshold color logic
├── test_ui_settings.py    # SettingsManager load/save, winreg toggle (mocked)
└── test_ui_tray.py        # TrayManager construction (no show — headless safe)
```

---

### Pattern 1: QSystemTrayIcon Setup

**What:** Create icon, attach context menu, connect `activated` signal, call `show()`.
**When to use:** Application startup, after `QApplication` is created.

**Critical ordering rule:** Icon must be set AND context menu must be attached BEFORE calling
`tray.setVisible(True)` / `tray.show()`. On Windows 11, new icons may be automatically hidden
in the overflow area — this is a Windows OS behaviour, not a Qt bug. [CITED: pythonguis.com/faq]

```python
# Source: pythonguis.com/tutorials/pyside6-system-tray-mac-menu-bar-applications/
#         + doc.qt.io/qt-6/qsystemtrayicon.html [CITED]

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

# Required BEFORE creating tray or any window:
qapp.setQuitOnLastWindowClosed(False)

tray = QSystemTrayIcon(parent=qapp)
tray.setIcon(QIcon("assets/tray_icon.png"))
tray.setToolTip("PeriphWatcher")

menu = QMenu()
show_action = QAction("Show")
show_action.triggered.connect(window.show_restore)
menu.addAction(show_action)
menu.addSeparator()
quit_action = QAction("Quit")
quit_action.triggered.connect(qapp.quit)
menu.addAction(quit_action)

tray.setContextMenu(menu)
tray.activated.connect(on_tray_activated)
tray.show()   # call AFTER icon + context menu are set


def on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
    if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
        window.show_restore()
```

**ActivationReason enum values** [CITED: doc.qt.io/qt-6/qsystemtrayicon.html]:
- `Unknown` (0), `Context` (1), `DoubleClick` (2), `Trigger` (3, left single-click), `MiddleClick` (4)

**Windows 11 note:** Middle-click emits `Trigger` instead of `MiddleClick` on Windows 11 — known
platform bug reported on Qt Forum. Not relevant for Phase 4 (only DoubleClick used). [CITED: forum.qt.io/topic/155726]

---

### Pattern 2: closeEvent Hide-Not-Quit

**What:** Override `closeEvent` to hide the window instead of closing it.
**When to use:** `QMainWindow` subclass.

```python
# Source: doc.qt.io/qtforpython-6/PySide6/QtGui/QCloseEvent.html [CITED]

from PySide6.QtGui import QCloseEvent

class MainWindow(QMainWindow):
    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()   # suppress default close behaviour
        self.hide()      # hide — do NOT call event.accept()

    def show_restore(self) -> None:
        self.show()
        self.raise_()          # bring to front of window stack
        self.activateWindow()  # give keyboard focus
```

`QApplication.setQuitOnLastWindowClosed(False)` is the other half — without it the app
terminates when the window is hidden. Set this immediately after `QApplication([])`. [CITED: pythonguis.com]

---

### Pattern 3: QSS Global Dark Theme

**What:** Apply a custom QSS stylesheet to `QApplication` to style all widgets.
**When to use:** After `QApplication` is created, before `MainWindow` is shown.

**Critical pitfall — QWidget subclass backgrounds:** If you create a custom class that
inherits `QWidget` directly (not a concrete subclass like `QFrame`), Qt will NOT apply the
background-color rule from the stylesheet unless you override `paintEvent`. This is because
`QWidget.paintEvent` does not call the style drawing primitive by default. [CITED: wiki.qt.io]

```python
# Source: wiki.qt.io/How_to_Change_the_Background_Color_of_QWidget [CITED]

from PySide6.QtWidgets import QStyleOption, QStyle
from PySide6.QtGui import QPainter

class StyledWidget(QWidget):
    """Required boilerplate for any QWidget subclass that relies on QSS background-color."""
    def paintEvent(self, event) -> None:
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
```

**Selector specificity:** When `QWidget { background-color: X }` is in the global stylesheet,
it does NOT automatically cascade to child widgets of a custom `QWidget` subclass. Use
`QWidget#myObjectName, QWidget#myObjectName * { ... }` or the `*` combinator to force
inheritance. [CITED: forum.qt.io/topic/111137]

**Minimal dark QSS skeleton** (expand as needed):

```python
DARK_QSS = """
QWidget {
    background-color: #202535;
    color: #FFFFFF;
}
QMainWindow {
    background-color: #202535;
}
QPushButton {
    background-color: transparent;
    color: #FFFFFF;
    border: none;
    padding: 8px 12px;
    text-align: left;
}
QPushButton:checked {
    background-color: #262355;
    border-left: 3px solid #4FC3F7;
}
QPushButton:hover {
    background-color: #2a2d45;
}
QScrollBar:vertical {
    background-color: #202535;
    width: 8px;
}
QScrollBar::handle:vertical {
    background-color: #3a3d55;
    border-radius: 4px;
}
QLabel {
    background-color: transparent;
    color: #FFFFFF;
}
QCheckBox {
    color: #FFFFFF;
    spacing: 8px;
}
QMenu {
    background-color: #262355;
    color: #FFFFFF;
    border: 1px solid #3a3d55;
}
QMenu::item:selected {
    background-color: #2a2d45;
}
"""
```

---

### Pattern 4: Sidebar Navigation with QStackedWidget

**What:** Exclusive checkable QPushButtons controlling QStackedWidget page index.
**When to use:** Any multi-page layout with persistent navigation.

```python
# Source: doc.qt.io/qtforpython-6/PySide6/QtWidgets/QButtonGroup.html [CITED]
#         + doc.qt.io/qtforpython-6/PySide6/QtWidgets/QStackedWidget.html [CITED]

from PySide6.QtWidgets import QButtonGroup, QPushButton, QStackedWidget

class SidebarNav(QWidget):
    def __init__(self, stack: QStackedWidget, parent=None):
        super().__init__(parent)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        nav_items = [
            ("Dashboard", 0),
            ("Devices",   1),
            ("History",   2),
            ("Profiles",  3),
            ("Settings",  4),
        ]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        for label, idx in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            self._group.addButton(btn, idx)
            layout.addWidget(btn)

        layout.addStretch()

        # Wire button clicks to page changes
        self._group.idClicked.connect(stack.setCurrentIndex)

        # Start on Dashboard
        self._group.button(0).setChecked(True)
```

**Key:** `QButtonGroup.idClicked` emits the integer id assigned via `addButton(btn, idx)`,
which maps directly to `QStackedWidget.setCurrentIndex(idx)`. [CITED: Qt docs]

---

### Pattern 5: winreg Startup Registration

**What:** Write/remove `HKCU\...\Run` key to register/deregister startup launch.
**When to use:** When user toggles "Launch at startup" in Settings.

```python
# Source: docs.python.org/3/library/winreg.html [CITED]

import winreg
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "PeriphWatcher"


def _get_exe_path() -> str:
    """Return quoted exe path — quoting required when path contains spaces."""
    path = sys.executable  # dev: python.exe; packaged: PeriphWatcher.exe
    # Wrap in quotes so Windows handles paths with spaces correctly
    return f'"{path}"'


def set_startup(enabled: bool) -> None:
    if enabled:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            access=winreg.KEY_WRITE,
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
    else:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                access=winreg.KEY_WRITE,
            ) as key:
                winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass  # key did not exist — idempotent


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY
        ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
```

**Path quoting:** The REG_SZ value for a Run entry with spaces in the path MUST be wrapped
in double quotes (e.g. `"C:\Program Files\PeriphWatcher\PeriphWatcher.exe"`). Without
quoting, Windows treats the first space as an argument separator and fails to launch.
[ASSUMED — path quoting requirement is well-documented Windows behavior but was not
confirmed via an official winreg/run-key specific doc in this research session]

**HKCU vs HKLM:** HKCU (current user) requires no admin rights — correct for this use case.
`HKLM\...\Run` would require elevation. [CITED: CONTEXT.md D-05 + winreg docs]

---

### Pattern 6: JSON Config Persistence

**What:** Load settings from `%APPDATA%\PeriphWatcher\config.json`, create if absent.
**When to use:** App startup and on every settings toggle.

```python
# Source: docs.python.org/3/library/pathlib.html [CITED]

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ["APPDATA"]) / "PeriphWatcher"
CONFIG_FILE = CONFIG_DIR / "config.json"

_DEFAULTS = {"launch_at_startup": False}


def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    try:
        with CONFIG_FILE.open() as f:
            data = json.load(f)
        # Merge with defaults so Phase 6 additions don't break Phase 4 reads
        return {**_DEFAULTS, **data}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w") as f:
        json.dump(config, f, indent=2)
```

`mkdir(parents=True, exist_ok=True)` — `parents=True` creates intermediate directories;
`exist_ok=True` is a no-op if the dir already exists. [CITED: Python docs]

---

### Pattern 7: DeviceCard — Battery Threshold Colour Logic

**What:** Map battery percentage to display colour per D-01 thresholds.
**When to use:** `DeviceCard.update_state()` to set percent label colour.

```python
# Source: CONTEXT.md D-01 thresholds [CITED]

def battery_color(percent: int | None) -> str:
    """Return QSS color string for given battery percentage."""
    if percent is None:
        return "#888888"   # grey for offline
    if percent <= 8:
        return "#E50000"   # critical red
    if percent <= 45:
        return "#E5A300"   # warning amber (approximate; verify against design spec)
    return "#4FC3F7"       # normal teal/neutral
```

**Design spec note:** The design spec lists `#E5090D` as warning amber but the spec
commentary notes exact hex values are hard to read from the image. `#E5A300` (golden amber)
is a safer interpretation for readability against the dark background. Planner should flag
this for visual verification. [ASSUMED — amber hex interpretation]

---

### Anti-Patterns to Avoid

- **`event.accept()` in closeEvent:** Accepts the close event, which destroys the window. Must use `event.ignore()` + `self.hide()`.
- **Forgetting `setQuitOnLastWindowClosed(False)`:** App exits the moment the user first closes the window. Set this immediately after `QApplication` is created.
- **Setting tray icon after `show()`:** On Windows, the icon may not appear or may render incorrectly. Set icon and context menu first, then call `show()`.
- **Not quoting paths with spaces in winreg Run value:** Windows will fail to launch the exe if the path contains spaces and is not quoted. Always wrap the path string in outer quotes.
- **Custom `QWidget` subclass without `paintEvent` override:** Background-color from QSS will silently not render. Every custom QWidget subclass needs the `QStyleOption` + `drawPrimitive` paintEvent boilerplate.
- **Hardcoding `sys.executable` as the startup path during development:** During development `sys.executable` is the Python interpreter, not the app exe. This is acceptable for Phase 4 (packaged exe is Phase 7), but should be documented as a known limitation.
- **Keeping `mock_consumer` alongside the real consumer:** The new `on_device_update` method replaces `mock_consumer` in the entry point. Leaving both connected doubles all card updates.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| QApplication singleton in pytest | Per-test QApplication creation | pytest-qt `qapp` fixture | QApplication cannot be destroyed and recreated within a session; pytest-qt manages this |
| Dark theme base | Custom palette QPalette manipulation | Global QSS string on QApplication | QPalette dark mode works but QSS gives finer token-level control needed for brand colours |
| Settings key-value store | Custom INI/binary format | stdlib `json` | Schema is trivial (1 bool); json is readable and extensible |
| Startup registration | Third-party startup-manager lib | stdlib `winreg` | No admin required, well-documented, no added dependency |

**Key insight:** Phase 4 is a pure UI shell over an already-correct data plumbing layer. All the
complex async/threading/HID work is done. The new code is almost entirely declarative (widget
constructors, layouts, stylesheet strings, simple file I/O).

---

## Common Pitfalls

### Pitfall 1: QWidget Subclass Background Not Rendering

**What goes wrong:** A custom widget that inherits `QWidget` directly has `background-color`
set in the global QSS but renders transparent at runtime.
**Why it happens:** `QWidget.paintEvent` does not invoke the style drawing primitive. The
stylesheet rule exists but nothing calls the code to paint it.
**How to avoid:** Add the `paintEvent` override with `QStyleOption` + `style().drawPrimitive`
to every custom `QWidget` subclass that needs a background. [CITED: wiki.qt.io]
**Warning signs:** Widget shows OS default appearance (white/grey) despite dark QSS being set.

### Pitfall 2: App Exits When Window is Hidden

**What goes wrong:** App terminates silently when user closes the main window, despite the
`closeEvent` override calling `hide()`.
**Why it happens:** `QApplication.setQuitOnLastWindowClosed` defaults to `True`. When the
window hides, Qt counts 0 visible windows and calls `quit()`.
**How to avoid:** Call `qapp.setQuitOnLastWindowClosed(False)` immediately after creating
`QApplication`. [CITED: pythonguis.com]
**Warning signs:** Process exits; tray icon disappears; Ctrl+C is the only way to confirm
the app is gone.

### Pitfall 3: Tray Icon Not Visible on Windows 11

**What goes wrong:** The tray icon is not visible in the taskbar notification area.
**Why it happens:** Windows 11 automatically hides new tray icons in the overflow area
behind the `^` arrow. This is an OS-level default — not a bug in the code.
**How to avoid:** The app is still running; the user must pin the icon via Windows Settings
> Taskbar > Other system tray icons. Document this in the app. For development, use the
overflow area to verify the icon is present. [CITED: pythonguis.com/faq]
**Warning signs:** Tray icon absent from visible tray area — check overflow `^` first.

### Pitfall 4: Startup Path Not Quoted

**What goes wrong:** App registered in Run key but Windows fails to launch it at login with
"Windows cannot find..." error, despite the path being correct.
**Why it happens:** The registry value `C:\Users\Name\App Data\PeriphWatcher.exe` has a space.
Windows tokenises the path at the first space and tries to run `C:\Users\Name\App` with
arguments `Data\PeriphWatcher.exe`.
**How to avoid:** Always store the REG_SZ value as `"C:\path with spaces\app.exe"` with outer
double-quote characters included in the string value. [ASSUMED — well-known Windows behavior]
**Warning signs:** Works for paths without spaces; fails silently for paths with spaces.

### Pitfall 5: QButtonGroup idClicked Not Emitting

**What goes wrong:** Clicking sidebar buttons does not change the QStackedWidget page.
**Why it happens:** `idClicked` only emits when a button's id was set via `addButton(btn, id)`.
If buttons were added with `addButton(btn)` (no id), the id defaults to -1 for all of them,
so `idClicked` fires but with -1 and `setCurrentIndex(-1)` is a no-op.
**How to avoid:** Always use `group.addButton(btn, idx)` with an explicit integer id that
matches the stack page index. [CITED: Qt docs]
**Warning signs:** Signal fires (can verify with a print slot) but page does not change.

### Pitfall 6: DeviceCard Not Created on First Update

**What goes wrong:** The first `DeviceState` message arrives but no card appears.
**Why it happens:** The lookup `by (vid, pid, dev_idx)` finds nothing in an empty dict on first
call. If the "not found → create card" branch is missing, updates are silently dropped.
**How to avoid:** `on_device_update` must have two branches: (1) key present → update
existing card, (2) key absent → create new card, register in dict, add to layout, then update.
**Warning signs:** Console shows queue drain working (no errors) but UI shows empty dashboard.

### Pitfall 7: sys.coinit_flags Displaced by UI Reorganization

**What goes wrong:** Moving entry-point code to a new `__main__.py` places the COM init flag
after an import, causing `await client.connect()` hangs in Phase 5+ when BLE is added.
**Why it happens:** Any import that touches pywin32 or Qt will initialise COM as STA before
the flag is read.
**How to avoid:** `sys.coinit_flags = 0` MUST be the very first statement in whatever file
is the true entry point — with a comment explaining why. Copy the comment from `run_monitor.py`
verbatim. [CITED: CLAUDE.md Architecture Invariants]
**Warning signs:** No immediate symptom in Phase 4 (no BLE); the bug is latent until Phase 5.

---

## Code Examples

### Complete TrayManager Skeleton

```python
# Source: doc.qt.io/qt-6/qsystemtrayicon.html + pythonguis.com/tutorials/... [CITED]

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayManager:
    def __init__(self, window, qapp: QApplication) -> None:
        self._tray = QSystemTrayIcon(parent=qapp)
        self._tray.setIcon(QIcon("assets/tray_icon.png"))
        self._tray.setToolTip("PeriphWatcher")

        menu = QMenu()
        show_act = QAction("Show")
        show_act.triggered.connect(window.show_restore)
        menu.addAction(show_act)
        menu.addSeparator()
        quit_act = QAction("Quit")
        quit_act.triggered.connect(qapp.quit)
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._window = window

    def show(self) -> None:
        self._tray.show()   # call after all setup is complete

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._window.show_restore()
```

### Entry Point Pattern

```python
# src/__main__.py  — MUST be the actual entry point file
import sys
sys.coinit_flags = 0  # MUST be first — before ALL imports. MTA mode required for bleak WinRT.

import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from monitor.app import MonitorApp
from ui.main_window import MainWindow
from ui.tray import TrayManager


def main() -> None:
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)   # required before any window is shown
    qapp.setStyleSheet(DARK_QSS)            # imported from ui.styles

    window = MainWindow()
    tray = TrayManager(window, qapp)
    tray.show()

    signal.signal(signal.SIGINT, lambda *_: qapp.quit())
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)

    app_obj = MonitorApp(consumer=window.on_device_update)
    app_obj.start()
    hotplug = app_obj.build_hotplug()
    timer = app_obj.make_timer()  # noqa: F841

    window.show()
    qapp.exec()

    app_obj.stop()
    hotplug.unregister()


if __name__ == "__main__":
    main()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `QSystemTrayIcon` notifications for Windows toasts | Use `Windows-Toasts` library (Phase 6) | Qt 6 / Windows 11 | Qt tray notifications don't persist in Action Center on Windows 11 — irrelevant for Phase 4 |
| `QApplication.setPalette()` for theming | QSS stylesheet on `QApplication` | Always available | QSS gives per-widget-type control; palette is coarser |
| Manual `signal.signal` SIGINT only | SIGINT + 200ms heartbeat QTimer | Phase 3 confirmed | Qt event loop on Windows swallows SIGINT without a timer tick |

**Deprecated/outdated:**
- `pywinusb`: abandoned — project uses `hid` (hidapi) instead (locked)
- `PyBluez`: abandoned — project uses `bleak` instead (locked, Phase 5+)
- `PySide2` / `PyQt5`: superseded by PySide6 — not applicable here

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Amber warning colour `#E5A300` is appropriate for the design spec | Pattern 7 (DeviceCard) | Visual design mismatch — easily corrected by checking against design image at implementation time |
| A2 | Startup path quoting (outer double-quotes in REG_SZ value) is required for paths with spaces | Pattern 5 (winreg) | Dev-mode path (`C:\Users\...\.venv\...`) may not have spaces, so this is latent until Phase 7 packaging |
| A3 | `sys.executable` is acceptable as startup path in Phase 4 dev mode | Pattern 5 (winreg) | Registering python.exe instead of the packaged exe — correct to flag as dev-mode limitation, not a bug |
| A4 | pytest-qt 4.5.0 is installable in the project's venv (requirements.txt not yet confirmed) | Standard Stack | If the project venv uses a different Python version or has conflicts, install may fail — verify in Wave 0 |

**If this table is empty:** N/A — there are 4 assumptions above.

---

## Open Questions

1. **Amber hex value for warning state**
   - What we know: Design spec says "warning amber ≤45%" with approximate hex `#E5090D` (but spec note says hex is hard to read from image)
   - What's unclear: Exact amber hex — `#E5A300` (golden amber) vs `#E5090D` (which looks red) vs `#E5B800`
   - Recommendation: Use `#E5A300` as a placeholder; planner adds a manual visual-check task

2. **`run_monitor.py` vs `__main__.py` as entry point**
   - What we know: `run_monitor.py` exists and works; `src/__main__.py` exists as a stub
   - What's unclear: Whether Phase 4 replaces `__main__.py` (cleaner) or extends `run_monitor.py` (keeps git history)
   - Recommendation: Replace `__main__.py` with the full Phase 4 entry point; keep `run_monitor.py` as a dev convenience but document it is superseded

3. **Icon asset format: 16x16 ICO vs PNG**
   - What we know: Windows system tray expects 16x16; Qt accepts both ICO and PNG; Qt scales automatically
   - What's unclear: Whether a 32x32 or 64x64 PNG with Qt auto-scaling looks acceptable vs a proper ICO with multiple resolutions
   - Recommendation: Create a 32x32 PNG placeholder; Qt will scale to 16x16 for the tray

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All | ✓ | 3.12.13 | — |
| PySide6 | All UI code | ✓ (in requirements.txt) | 6.11.1 | — |
| pytest-qt | UI tests | ✗ (not yet installed) | — | Add to requirements.txt in Wave 0 |
| winreg (stdlib) | SYS-01 | ✓ (Windows 11) | stdlib | — |
| pathlib (stdlib) | SYS-02 | ✓ | stdlib | — |

**Missing dependencies with no fallback:** none

**Missing dependencies with fallback:**
- `pytest-qt` not yet in `requirements.txt` — planner adds it in Wave 0 setup task

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pytest.ini` (exists) |
| Quick run command | `pytest tests/test_ui_*.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Device card renders name/percent/status from DeviceState | unit | `pytest tests/test_ui_device_card.py -x` | ❌ Wave 0 |
| UI-01 | on_device_update creates card on first state, updates on subsequent | unit | `pytest tests/test_ui_main_window.py -x` | ❌ Wave 0 |
| UI-02 | closeEvent calls hide() and ignores event | unit | `pytest tests/test_ui_main_window.py::test_close_hides -x` | ❌ Wave 0 |
| UI-03 | TrayManager construction succeeds without show() (headless) | unit | `pytest tests/test_ui_tray.py -x` | ❌ Wave 0 |
| UI-03 | DoubleClick activation calls show_restore | unit | `pytest tests/test_ui_tray.py::test_double_click_activates -x` | ❌ Wave 0 |
| SYS-01 | set_startup(True) writes REG_SZ to Run key (winreg mocked) | unit | `pytest tests/test_ui_settings.py::test_set_startup_enabled -x` | ❌ Wave 0 |
| SYS-01 | set_startup(False) deletes Run key value (winreg mocked) | unit | `pytest tests/test_ui_settings.py::test_set_startup_disabled -x` | ❌ Wave 0 |
| SYS-02 | load_config() returns defaults when file absent | unit | `pytest tests/test_ui_settings.py::test_load_config_defaults -x` | ❌ Wave 0 |
| SYS-02 | save_config() / load_config() round-trip preserves values | unit | `pytest tests/test_ui_settings.py::test_config_roundtrip -x` | ❌ Wave 0 |
| SYS-02 | battery_color() returns correct hex for critical/warning/normal/None | unit | `pytest tests/test_ui_device_card.py::test_battery_color -x` | ❌ Wave 0 |

**Notes on test strategy:**
- `QSystemTrayIcon.show()` cannot be tested headlessly without a display server — TrayManager tests must not call `tray.show()`. Construction and signal wiring are testable.
- `MainWindow.show()` is also problematic headlessly — tests should instantiate the window object and call methods without calling `show()`. pytest-qt's `qapp` fixture provides the necessary QApplication.
- winreg calls in settings tests should be mocked with `mocker.patch("winreg.OpenKey")` to avoid real registry writes in CI.

### Sampling Rate

- **Per task commit:** `pytest tests/test_ui_*.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ui_main_window.py` — covers UI-01, UI-02
- [ ] `tests/test_ui_device_card.py` — covers UI-01, battery_color thresholds
- [ ] `tests/test_ui_tray.py` — covers UI-03
- [ ] `tests/test_ui_settings.py` — covers SYS-01, SYS-02
- [ ] `pytest-qt==4.5.0` add to `requirements.txt`
- [ ] `src/ui/__init__.py` — empty init for new package

---

## Security Domain

> `security_enforcement` key absent from config.json — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | no user authentication in this app |
| V3 Session Management | no | desktop app, no sessions |
| V4 Access Control | no | single-user desktop app |
| V5 Input Validation | yes (minimal) | settings file is written by this app and read back — `json.JSONDecodeError` caught in `load_config` |
| V6 Cryptography | no | no sensitive data stored |
| V7 Error Handling | yes | winreg `FileNotFoundError` caught in `is_startup_enabled` + `set_startup(False)` |

### Known Threat Patterns for Desktop Python / Registry

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Registry Run key pointing to wrong path (path traversal / typo) | Tampering | Quote path; use `sys.executable` directly (not user-supplied input) |
| Malformed config.json causing crash on load | Denial of Service | Catch `json.JSONDecodeError`, fall back to defaults |
| Config file written by another process with unexpected schema | Tampering | Merge with `_DEFAULTS` dict on load (forward-compatible) |

---

## Sources

### Primary (HIGH confidence)

- [doc.qt.io/qt-6/qsystemtrayicon.html](https://doc.qt.io/qt-6/qsystemtrayicon.html) — ActivationReason enum, setContextMenu, show/hide, platform notes
- [doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html) — Python bindings
- [docs.python.org/3/library/winreg.html](https://docs.python.org/3/library/winreg.html) — OpenKey, SetValueEx, DeleteValue, QueryValueEx patterns
- [docs.python.org/3/library/pathlib.html](https://docs.python.org/3/library/pathlib.html) — mkdir(parents=True, exist_ok=True)
- [wiki.qt.io/How_to_Change_the_Background_Color_of_QWidget](https://wiki.qt.io/How_to_Change_the_Background_Color_of_QWidget) — paintEvent override for QWidget subclasses
- [pytest-qt.readthedocs.io/en/latest/qapplication.html](https://pytest-qt.readthedocs.io/en/latest/qapplication.html) — QApplication singleton, qapp fixture, session scope
- [pypi.org/pypi/PySide6/json](https://pypi.org/project/PySide6/) — version 6.11.1 confirmed current (2026-05-13)
- [pypi.org/pypi/pytest-qt/json](https://pypi.org/project/pytest-qt/) — version 4.5.0 confirmed current (2025-07-01)

### Secondary (MEDIUM confidence)

- [pythonguis.com/tutorials/pyside6-system-tray-mac-menu-bar-applications/](https://www.pythonguis.com/tutorials/pyside6-system-tray-mac-menu-bar-applications/) — Complete tray setup pattern with setQuitOnLastWindowClosed(False)
- [pythonguis.com/faq/system-tray-examples-not-showing-up-on-windows-10/](https://www.pythonguis.com/faq/system-tray-examples-not-showing-up-on-windows-10/) — Windows 11 tray icon hidden in overflow pitfall
- [forum.qt.io/topic/111137/stylesheet-inheritance-and-container-widgets](https://forum.qt.io/topic/111137/stylesheet-inheritance-and-container-widgets) — QWidget stylesheet cascade / `*` combinator fix
- [forum.qt.io/topic/155726/qsystemtrayicon-cannot-respond-to-middle-click-on-win11](https://forum.qt.io/topic/155726/qsystemtrayicon-cannot-respond-to-middle-click-on-win11) — Windows 11 MiddleClick/Trigger mismatch

### Tertiary (LOW confidence)

- Project design system memory (`memory/design_system.md`) — approximate color hex values (amber warning noted as uncertain in the document itself)

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — PySide6 6.11.1 is current on PyPI; pytest-qt 4.5.0 confirmed; all other deps are stdlib
- Architecture: HIGH — patterns confirmed from official Qt docs and pythonguis.com tutorials
- Pitfalls: HIGH — QWidget paintEvent issue confirmed from Qt wiki; tray icon visibility confirmed from pythonguis FAQ; remaining pitfalls from official docs
- Winreg path quoting: MEDIUM — well-known Windows behavior; indirect evidence from registry docs and Windows CMD reference

**Research date:** 2026-06-02
**Valid until:** 2026-07-02 (PySide6 point releases are infrequent; patterns are stable)
