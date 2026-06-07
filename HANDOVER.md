# Volt Project Handover Document

## Overview
**Volt (Power Center)** is a desktop utility built with Python and PySide6 that monitors battery levels of wireless peripherals (Logitech, SteelSeries, Bluetooth devices). It has a headless background service/manager and a premium dark-mode desktop UI.

---

## Architecture Invariants (DO NOT VIOLATE)

| Invariant | Reason |
|-----------|--------|
| `sys.coinit_flags = 0` is the **very first line** of `src/__main__.py`, before all imports | bleak WinRT backend requires COM MTA. Qt/pywin32 initialize STA. If STA is first, `await client.connect()` hangs silently forever. |
| All HID and BLE I/O runs exclusively on the asyncio background thread | Qt requires all UI calls on the main thread. |
| UI ↔ background thread communication via `queue.Queue` only | Only thread-safe mechanism that requires no locks in calling code. |
| HID interface selected by `usage_page=0xFF00` (vendor-specific), never primary | Windows locks `usage_page=0x0001`. Access Denied otherwise. |
| HID++ feature indices discovered at runtime via Root feature 0x0000 | Firmware-assigned. Hardcoding breaks across firmware variants. |

---

## Tech Stack

| Purpose | Library | Version |
|---------|---------|---------|
| HID | `hidapi` (ctypes wrapper) | 0.15.0 |
| Bluetooth LE | `bleak` | 3.0.2 |
| UI + tray | `PySide6` | 6.11.1 |
| Notifications | `Windows-Toasts` | 1.3.1 |
| Startup | `winreg` | stdlib |
| Packaging | `PyInstaller` | 6.17+ |

---

## Color Palette & Style Rules

- Background: `#202028` (pages), `#18181f` (widget), `#1a1a1f` (dialogs)
- Borders: `#2a2a38`
- Highlight / active: `#7B9FFF`
- Warning / CTA: `#E89000`
- Muted text: `#888899` / `#AAAACC`
- Battery good: `#4CAF50`, warning: `#F0BB66`, critical: `#EE6800`, offline/unknown: `#555566`
- Charging: `#4FC3F7`
- All styling via `setStyleSheet()` — no external CSS files.
- Font: `Segoe UI` throughout.

---

## Key Files & Responsibilities

| File | Role |
|------|------|
| `src/__main__.py` | Entry point. Wires `MonitorApp`, `MainWindow`, `TrayManager`, `NotificationManager`. Back-patches consumers after window exists. |
| `src/ui/main_window.py` | App shell. Routing, card registry, queue drain, compact mode toggle. |
| `src/ui/widget_window.py` | **NEW** Compact floating widget (see below). |
| `src/ui/device_card.py` | Dashboard cards. Clickable — emit `history_requested` to route to Device Detail. |
| `src/ui/history_page.py` | Device Detail page: live gauge + time-remaining estimate + threshold toggle + history graph. |
| `src/ui/threshold_dialog.py` | Frameless draggable dialog for setting per-device battery warning %. |
| `src/ui/notification_manager.py` | Dispatches Windows toast notifications when battery drops below per-device threshold. `None` threshold = silent. |
| `src/ui/settings_page.py` | Settings tab. Toggles: startup, close-to-tray, widget always-on-top. |
| `src/ui/settings_manager.py` | `load_config()` / `save_config()`. Source of truth for all persisted state. Also exposes `battery_color()`. |
| `src/ui/tray.py` | System tray icon + context menu. |
| `src/ui/sidebar.py` | Left nav. Registers/unregisters device sub-items. |
| `src/ui/updater.py` | Checks `https://api.github.com/repos/ViFurzy/Volt/releases/latest`, downloads and runs installer. |
| `src/__version__.py` | Single source of truth: `__version__ = "0.4.0"`. |
| `scripts/build.py` | PyInstaller build runner → `dist/Volt/`. |
| `scripts/installer.iss` | Inno Setup spec → `dist/Volt_Setup.exe`. |

---

## What Was Implemented This Session — Compact Widget Mode

### New file: `src/ui/widget_window.py`

A small frameless always-on-top floating window that shows only connected devices.

**`_DeviceRow(QFrame)`** — one row per online device:
- Device name (bold, white)
- `⚡` charging indicator (`#4FC3F7`), hidden when not charging
- Battery % (right-aligned, color-coded via `battery_color()`)
- Thin `QProgressBar` (4px height) below the text, colored to match battery level

**`WidgetWindow(QWidget)`** — the container:
- `Qt.FramelessWindowHint | Qt.Tool`, optionally `Qt.WindowStaysOnTopHint`
- Header: `VOLT` label + `[⊡]` expand (calls `exit_callback`) + `[✕]` hide-to-tray
- Draggable; position saved to config (`widget_position: {x, y}`) on drag-release and `hideEvent`
- **Only online devices are shown.** Offline devices are hidden (row set invisible or not created). "No devices monitored" label shows when all rows are hidden.
- `update_device(key, name, percent, charging, offline)` — if `offline=True`, hides/skips the row; if online, creates or updates and shows it
- `remove_device(key)` — removes row from layout
- `set_always_on_top(bool)` — re-applies `setWindowFlags` live (re-shows window if it was visible)
- `_apply_opacity()` — reads `widget_opacity` from config (default `0.95`) for semi-transparent background

### Changes to `src/ui/main_window.py`

- Imports `WidgetWindow`
- Creates `self._widget = WidgetWindow(exit_callback=self.exit_widget_mode)` at end of `__init__`
- Title bar: new `[⊡]` button (before `[—]`) → `enter_widget_mode()`
- `enter_widget_mode()`: `self.hide()` → `self._widget.show()`
- `exit_widget_mode()`: `self._widget.hide()` → `self.show()` / `raise_()` / `activateWindow()`
- `show_restore()`: checks `self._widget.isVisible()` first — exits widget mode if active (so tray double-click works correctly in both modes)
- `on_device_update()`: calls `self._widget.update_device(key, ...)` after every card update
- `on_bt_device_update()`: same for BT devices
- `remove_card()`: calls `self._widget.remove_device(card_key)` in the removal loop

### Changes to `src/ui/tray.py`

- Added `"Compact mode"` action between `"Show the app"` and the separator → `window.enter_widget_mode()`

### Changes to `src/ui/settings_page.py`

- Added `SliderRow` widget class (label + `QSlider` + value label)
- Added `"Compact mode widget always on top"` `ToggleSwitch`
- Reads/writes `widget_always_on_top` config key (default `True`)
- `_on_widget_top_toggled()`: saves config + calls `self._window._widget.set_always_on_top(checked)` live
- `showEvent()`: re-syncs this toggle alongside existing ones

---

## Config Keys (full list of known keys)

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `monitored_devices` | list | `[]` | Devices being tracked |
| `close_behavior` | `"tray"` / `null` | `null` | What X button does |
| `launch_at_startup` | bool | `false` | Winreg startup entry |
| `thresholds` | dict keyed by device_id | `{}` | Per-device `threshold_pct` (int or null = disabled) and `cooldown_hours` |
| `history` | dict keyed by device_id | `{}` | List of `{timestamp, percent}` entries, max 200 per device |
| `widget_always_on_top` | bool | `true` | Whether compact widget floats above other windows |
| `widget_position` | `{x, y}` | absent | Last screen position of compact widget |
| `widget_opacity` | float | `0.95` | Background opacity of compact widget container |

---

## GitHub Remote

```
https://github.com/ViFurzy/Volt.git
```
Branch: `master`. Nothing has been pushed yet — all changes are local commits only.

---

## Test Suite

- **221 tests, all passing.** Run with: `.venv-1\Scripts\pytest.exe tests/`
- Tests are headless — no Qt display required. `NotificationManager` has no Qt imports by design.
- When adding new UI features, ensure service/config logic is independently testable without a running QApplication.

---

## Next Steps (Phase 8 — Packaging)

1. Push `master` to `https://github.com/ViFurzy/Volt.git`
2. Run `python scripts/build.py` to produce `dist/Volt/`
3. Compile `scripts/installer.iss` with Inno Setup 6 → `dist/Volt_Setup.exe`
4. Create a GitHub Release tagged `v0.4.0` with `Volt_Setup.exe` as the release asset
5. The auto-updater in `src/ui/updater.py` is already wired to `ViFurzy/Volt` — it will pick up the release automatically once published
