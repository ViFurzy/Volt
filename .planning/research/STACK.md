# Technology Stack

**Project:** Windows Peripheral Battery Monitor
**Researched:** 2026-06-01
**Scope:** Python Windows 11 app — HID communication, BLE, UI, notifications, packaging

---

## Recommended Stack

### HID Communication

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `hid` (ctypes-hidapi) | 1.0.9 (Feb 2026) | USB HID raw communication | Actively maintained ctypes wrapper; no Cython build required; works on Windows without driver swap; sufficient for HID++ 2.0 raw report read/write |

**Use `hid`, not `hidapi` (cython-hidapi) and not `pywinusb`.**

- `hid` 1.0.9 — pure ctypes, pip-installable, no compiler needed, cross-platform but Windows-native path works fine. Works directly against the LIGHTSPEED USB dongle as a standard HID device.
- `hidapi` (cython-hidapi, 0.15.0) — wraps the same underlying C library but requires a Cython compilation step. Adds build complexity for no functional gain on this project.
- `pywinusb` — **abandoned**. Last commit was ~6 years ago, last PyPI release is 0.4.2 (no activity since ~2018), WinPython removed it from its package set in 2025. Do not use.

**HID++ 2.0 implementation note:** There is no pip-installable HID++ 2.0 library. You implement the protocol manually using raw `hid` report reads/writes, referencing the Solaar project (`pwr-Solaar/Solaar`) as the most complete open-source Python reference for feature IDs (e.g., `0x1000` BATTERY_STATUS, `0x1001` BATTERY_VOLTAGE). Battery feature IDs must be discovered at runtime via the HID++ 2.0 feature index mechanism.

### Bluetooth LE (SteelSeries Aerox 5 Wireless BT path)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `bleak` | 3.0.2 (May 2026) | BLE GATT client | Only serious actively-maintained BLE library for Python; asyncio-native; uses Windows.Devices.Bluetooth WinRT API directly; no driver install needed |

**No meaningful alternative exists.** `PyBluez` is unmaintained and broken on Windows 10+. `bluetooth` (pybluez fork) does not support BLE on Windows. Bleak is the de facto standard confirmed by the Python community and is the only library with active releases tracking Python 3.12+.

**Architecture note:** Bleak is async (asyncio). The SteelSeries Aerox 5 Wireless exposes battery level via the standard BLE Battery Service (UUID `0x180F`, characteristic `0x2A19`). The 2.4GHz dongle path will use HID (same `hid` library as Logitech), not BLE — confirm which interface is actually enumerated before committing to the BT path for SteelSeries.

### UI Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `PySide6` | 6.11.1 (May 2026) | Main window + system tray | Official Qt6 Python bindings from The Qt Company; LGPL licensed (no GPL restriction unlike PyQt6); `QSystemTrayIcon` built-in; renders natively on Windows 11; mature ecosystem |

**Use PySide6, not PyQt6 and not tkinter/customtkinter.**

- PySide6 6.11.1 — LGPL license means no license concern for distribution. Identical API to PyQt6. Has `QSystemTrayIcon` built in — no extra library needed for system tray.
- PyQt6 — GPL license creates distribution complications unless you buy a commercial license. API is nearly identical to PySide6; there is no technical reason to choose PyQt6 over PySide6 for a new project.
- `customtkinter` — Built on tkinter. No native system tray support (requires `pystray` separately). Looks modern but is not Windows-native. Adds complexity for tray without benefit.
- `tkinter` — No system tray support, dated appearance.
- `wxPython` — Native Windows feel but significantly heavier, smaller community, worse documentation, and no strong advantage here.

**Known Windows 11 issue:** `QSystemTrayIcon` icons can be hidden in the taskbar overflow area on Windows 11. This is a Windows 11 behavior (not a Qt bug) — document as expected behavior requiring user to pin the icon. Middle-click activation has a minor Qt bug on Windows 11; use left-click or right-click context menu only.

**PySide6 already covers system tray** — `QSystemTrayIcon` + `QMenu` handle everything needed. No `pystray` required.

### Windows Toast Notifications

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `Windows-Toasts` | 1.3.1 (May 2025) | Native Windows 10/11 toast notifications | Uses WinRT bindings directly (`winrt-Windows.UI.Notifications`); produces real Windows notification center entries; supports notification actions; actively maintained |

**Use `Windows-Toasts`, not `winotify` and not plyer.**

- `Windows-Toasts` 1.3.1 — Native WinRT path, notifications appear in Action Center, supports Windows 11 features (progress bars, buttons). Requires Python 3.9+.
- `winotify` — Uses PowerShell as a subprocess. Fragile (PowerShell execution policy can block it), slow, no notification actions. Avoid.
- `plyer` — Cross-platform abstraction; Windows backend uses an older method and lags behind Windows 11 notification features. Cross-platform abstraction is unnecessary overhead here.

**Dependency note:** `Windows-Toasts` pulls in `winrt-runtime ~= 3.0` and several `winrt-Windows.*` packages. These add ~15 MB to the packaged exe but are the correct native approach.

### Windows Startup / Autorun

**Recommendation: Windows Registry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`)**

Use the built-in `winreg` module (stdlib, no extra dependency). Write a single string value pointing to the packaged exe path.

| Method | Verdict | Reasoning |
|--------|---------|-----------|
| Registry `HKCU\...\Run` | **Use this** | Per-user, no admin rights required, simple `winreg` stdlib implementation, works with single-exe output, survives Windows updates |
| Startup folder shortcut | Acceptable fallback | Simpler but requires creating a `.lnk` file (needs `pywin32` or `winshell`), less clean for a single-exe app |
| Task Scheduler | Overkill | XML-based configuration, requires `win32com` or `schtasks.exe` subprocess, complexity is not justified for a simple at-login launch |

**Implementation:** Read `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, set/delete a value named `PeripheryBatteryMonitor` pointing to `sys.executable`. Expose a toggle in the UI settings.

### Packaging / Distribution

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `PyInstaller` | 6.17+ (actively maintained) | Single-exe Windows distribution | Most battle-tested for Python+Qt; best hook ecosystem for PySide6; `--onefile` flag produces a single exe; largest community for troubleshooting |

**Use PyInstaller, not Nuitka and not cx_Freeze.**

- `PyInstaller` 6.x — Most reliable for PySide6 (maintained hooks for Qt). `--onefile` mode produces a self-extracting exe. Handles HID library DLL inclusion well. 4.7M+ monthly downloads; has the largest community knowledge base.
- `Nuitka` 4.x — Compiles Python to C. Produces faster, smaller binaries. However: requires MSVC or MinGW toolchain, significantly longer build times, PySide6 compilation support exists but is less battle-tested than PyInstaller. Justified for performance-critical apps; not needed for a tray utility.
- `cx_Freeze` — Produces a folder, not a single exe. Less active than PyInstaller. No compelling reason to prefer it here.

**PyInstaller known issues with this stack:**
- Must use `--collect-all PySide6` or the appropriate spec file to include Qt plugins (especially `platforms/qwindows.dll`).
- `winrt-*` packages from Windows-Toasts require explicit `--collect-all winrt` to bundle correctly.
- `hid` ctypes library bundles the hidapi DLL; verify it is included in the `--binaries` spec entry if not auto-detected.

---

## Supporting Libraries Summary

| Library | Version | Purpose |
|---------|---------|---------|
| `hid` | 1.0.9 | HID device raw communication |
| `bleak` | 3.0.2 | Bluetooth LE (SteelSeries BT path) |
| `PySide6` | 6.11.1 | UI window + system tray icon |
| `Windows-Toasts` | 1.3.1 | Windows 10/11 toast notifications |
| `winreg` | stdlib | Registry-based startup management |
| `PyInstaller` | 6.17+ | Single-exe packaging |

No additional dependencies required. Total fresh install footprint: ~200 MB (dominated by PySide6/Qt).

---

## What NOT to Use

| Library | Reason |
|---------|--------|
| `pywinusb` | Abandoned ~2018, last commit 6 years ago, removed from WinPython |
| `hidapi` (cython-hidapi) | Requires Cython build; same functionality as `hid` with more friction |
| `PyQt6` | GPL license; identical API to PySide6 but legally riskier for distribution |
| `PyBluez` / `bluetooth` | Unmaintained, broken on Windows 10+, no BLE support on Windows |
| `winotify` | PowerShell subprocess; unreliable, no notification actions |
| `plyer` | Cross-platform abstraction with outdated Windows backend |
| `tkinter` / `customtkinter` | No native tray support; requires separate `pystray` library |
| `Nuitka` | Over-engineered for a tray utility; C toolchain build complexity not justified |
| `cx_Freeze` | Folder-based output, less active, no advantage over PyInstaller here |
| Task Scheduler for startup | Unnecessary complexity (`win32com` + XML) vs. simple registry key |

---

## Installation

```bash
# Core runtime dependencies
pip install hid bleak PySide6 Windows-Toasts

# Packaging (dev-time only)
pip install pyinstaller
```

```bash
# Build single-exe (adjust entry point as needed)
pyinstaller --onefile --noconsole --name PeripheryBatteryMonitor \
  --collect-all PySide6 \
  --collect-all winrt \
  main.py
```

---

## Confidence Levels

| Area | Confidence | Basis |
|------|------------|-------|
| HID library (`hid`) | HIGH | PyPI version confirmed (1.0.9, Feb 2026); pywinusb abandonment confirmed via Snyk + OpenHub |
| Bleak BLE | HIGH | PyPI version confirmed (3.0.2, May 2026); no competing Windows BLE library exists |
| PySide6 for UI + tray | HIGH | PyPI version confirmed (6.11.1, May 2026); QSystemTrayIcon official docs confirmed |
| Windows-Toasts | HIGH | PyPI version confirmed (1.3.1, May 2025); WinRT dependency chain verified |
| Registry for startup | MEDIUM | Standard approach per Microsoft docs; winreg is stdlib but edge cases exist (UAC, relocated exe) |
| PyInstaller packaging | HIGH | Version 6.x confirmed active; community guidance for PySide6 packing is well-documented |
| HID++ 2.0 protocol impl | MEDIUM | No pip library exists; Solaar is primary reference; feature IDs confirmed from multiple sources but device-specific variants require testing |
| SteelSeries BLE battery UUID | MEDIUM | Standard BLE Battery Service (0x180F) is the expected path; device-specific confirmation requires hardware testing |

---

## Sources

- [hid on PyPI](https://pypi.org/project/hid/)
- [hidapi (cython) on PyPI](https://pypi.org/project/hidapi/)
- [pywinusb maintenance status — Snyk Advisor](https://snyk.io/advisor/python/pywinusb)
- [bleak on PyPI](https://pypi.org/project/bleak/)
- [bleak GitHub](https://github.com/hbldh/bleak)
- [PySide6 on PyPI](https://pypi.org/project/PySide6/)
- [PySide6 QSystemTrayIcon docs](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html)
- [PySide6 system tray tutorial](https://www.pythonguis.com/tutorials/pyside6-system-tray-mac-menu-bar-applications/)
- [Windows-Toasts on PyPI](https://pypi.org/project/Windows-Toasts/)
- [Windows-Toasts GitHub](https://github.com/DatGuy1/Windows-Toasts)
- [PyInstaller on PyPI](https://pypi.org/project/PyInstaller/)
- [Nuitka on PyPI](https://pypi.org/project/Nuitka/)
- [2026 PyInstaller vs Nuitka vs cx_Freeze comparison](https://ahmedsyntax.com/2026-comparison-pyinstaller-vs-cx-freeze-vs-nui/)
- [Solaar HID++ implementation reference](https://pwr-solaar.github.io/Solaar/implementation/)
- [SteelSeries Rival 650 battery monitor example](https://github.com/ugurcandede/SteelSeries-Rival-650-Battery-Monitor)
- [QSystemTrayIcon Windows 11 issues](https://www.pythonguis.com/faq/system-tray-examples-not-showing-up-on-windows-10/)
