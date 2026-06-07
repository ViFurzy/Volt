
# Research Summary: Windows Peripheral Battery Monitor

**Synthesized:** 2026-06-01
**Sources:** STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md

---

## Executive Summary

This is a Windows 11 system-tray utility that reads battery levels from wireless gaming peripherals (Logitech G Pro X Wireless via HID++ 2.0 LIGHTSPEED dongle, SteelSeries Aerox 5 Wireless via proprietary HID or BLE) without requiring manufacturer software. The stack is well-defined: hid for raw HID, bleak for BLE, PySide6 for UI and tray, Windows-Toasts for notifications, winreg for startup, and PyInstaller for packaging. No pip-installable HID++ 2.0 library exists -- the protocol must be implemented manually using Solaar as the primary reference.

The dominant architecture risk is threading: bleak requires MTA, Qt requires all UI calls on the main thread, and the two cannot share a loop without qasync. The recommended pattern is a single persistent asyncio loop on a daemon background thread communicating to the Qt main thread via queue.Queue. The sys.coinit_flags=0 line must be the very first statement in __main__ before any import touching COM.

The dominant protocol risk is HID interface selection: Windows locks the primary mouse/keyboard HID interface. The vendor-specific usage page (0xFF00) must be targeted for all reads/writes or every HID call fails with Access Denied. For Logitech devices, three incompatible battery feature variants (0x1000, 0x1001, 0x1004) must be probed in priority order at runtime. Both risks must be resolved in Phases 1-2 before any UI work begins.

---

## 1. Recommended Stack

| Library | Version | Rationale |
|---------|---------|-----------|
| hid (ctypes-hidapi) | 1.0.9 | Pure ctypes, no compiler, pip-installable, works without driver swap |
| bleak | 3.0.2 | Only maintained BLE library for Python on Windows; asyncio-native; WinRT backend |
| PySide6 | 6.11.1 | LGPL license; QSystemTrayIcon built in; native Win11 rendering |
| Windows-Toasts | 1.3.1 | WinRT-native toasts; appear in Action Center; supports buttons/progress bars |
| winreg | stdlib | Per-user startup via HKCU Run; no admin required; no extra dependency |
| PyInstaller | 6.17+ | Best-tested for PySide6; --onefile single exe; largest community knowledge base |

Do NOT use: pywinusb (abandoned 2018), hidapi cython (build friction), PyQt6 (GPL), PyBluez (broken on Windows), winotify (PowerShell subprocess), tkinter/pystray (no native tray), Nuitka (C toolchain overhead unjustified).

---

## 2. Table Stakes Features (v1 must-have)

1. **Battery percentage display** -- integer %, per device
2. **System tray icon per device** -- color-coded green/yellow/red; encodes level visually
3. **Tooltip on hover** -- device name + battery % for each device
4. **Low battery toast notification** -- fires once when crossing threshold (default 15%); 4-hour snooze prevents spam
5. **Charging status indicator** -- show charging badge if HID data exposes it; unknown otherwise
6. **Device name display** -- from HID product string or hardcoded VID/PID map; never Device 1
7. **Minimize / close to tray** -- X button hides window; tray context menu has Quit
8. **Auto-start with Windows** -- opt-in via Registry HKCU Run key; toggle in settings
9. **Multiple device support** -- mouse and headset simultaneously; each gets own row/icon

---

## 3. Differentiators (worth adding to stand out)

| Feature | Value | Effort |
|---------|-------|--------|
| Numeric % rendered in tray icon | Fastest glance-check; Win11 does this for laptop battery | Medium -- needs custom icon renderer |
| Configurable alert threshold | Default 15% wrong for many users; power users want 5%, cautious want 25% | Low |
| Last-polled timestamp in tooltip | Confirms reading is fresh, not stale | Low |
| Main window device cards | Name, %, charging badge, last-seen per device | Medium |
| Device offline / disconnected state | Grey icon + offline badge vs stale % -- critical for trust | Medium |
| Dark/light taskbar adaptive icon | Tray icon legible on both Windows themes | Low |
| Notification snooze / cooldown | Suppresses repeat alerts 4h after first fire | Low |

Defer to v2: per-device poll interval, startup notification summary, battery history.

---

## 4. Architecture in Brief

### Component Map

    Main Thread (Qt event loop)
      TrayIcon (QSystemTrayIcon)   <---+
      BatteryWindow (QWidget)          |  queue.Queue (thread-safe)
      UI update drain (QTimer 500ms)  <-+

    Background Thread (asyncio loop, daemon=True)
      MonitorService
        HIDppDriver       -- Logitech LIGHTSPEED, HID++ 2.0, feature discovery
        SteelSeriesDriver -- SS 2.4GHz, proprietary raw HID output reports
        BLEDriver         -- bleak async, GATT Battery Service 0x180F/0x2A19
        DeviceRegistry    -- thread-safe dict (vid,pid,dev_idx) -> DeviceState
        HotplugWatcher    -- hidden HWND + WM_DEVICECHANGE, triggers rescan

### Threading Model

- sys.coinit_flags = 0 -- first line of __main__, before ALL imports
- Main thread: Qt event loop only; zero HID/BLE calls ever
- Background thread: asyncio.new_event_loop() + loop.run_forever(); all I/O here
- Cross-thread: queue.Queue.put() from background; QTimer drain on main thread
- Schedule async work from main: asyncio.run_coroutine_threadsafe(coro, bg_loop)
- Never call asyncio.run() more than once; never hold persistent BLE connections

### Polling Intervals

| Protocol | Interval | Notes |
|----------|----------|-------|
| HID++ 2.0 | 60s | Battery changes slowly; shorter adds USB traffic |
| SteelSeries HID | 60s | No notification mechanism available |
| BLE | 120s | Connect-read-disconnect cycle adds 1-2s overhead per poll |

---

## 5. Critical Pitfalls (ordered by severity)

**P1 -- Opening the wrong HID interface (Access Denied)**
Enumerate all interfaces for a VID/PID; filter to usage_page=0xFF00 (vendor-specific). Never open usage_page=0x0001 with usage=0x02 (mouse) or usage=0x06 (keyboard) -- Windows locks these. Must be resolved before any protocol work.

**P2 -- HID++ battery feature variant mismatch (0x1000 vs 0x1001 vs 0x1004)**
Three incompatible battery features with incompatible response structures. Probe order: 0x1004 first, fall back to 0x1000, then 0x1001. Feature indices are runtime-discovered via Root feature 0x0000 -- never hardcoded. For 0x1004, check capability bitmask for HAS_SOC flag before reading state_of_charge.

**P3 -- bleak WinRT STA/MTA threading conflict**
sys.coinit_flags = 0 before importing PyQt6/pywin32/pythoncom. If COM is already STA when bleak starts, await client.connect() hangs forever with no error. Architecture decision -- must be settled before writing any BLE code.

**P4 -- Offline device returns HID++ error 5, crashes polling thread**
Receiver stays visible when wireless device is off; replies with error 5. Treat error 5 as device offline, return None for battery level, do not raise. Catch OSError/ValueError around all HID calls. Implement ONLINE/OFFLINE/UNKNOWN state machine.

**P5 -- HID++ receiver device index: 0xFF = dongle, not the mouse**
Device index 0xFF targets the USB receiver itself. Wireless peripherals use indices 0x01-0x0E. Must discover correct index by querying receiver paired device list -- never assume 0x01.

**Supporting pitfalls:**
- DBT_DEVNODES_CHANGED fires 5-6x per plug event -- use RegisterDeviceNotification with HID GUID + 500ms debounce
- asyncio.run() multiple times fragments bleak event loop -- one persistent loop, run_coroutine_threadsafe only
- SteelSeries uses hid.write() not hid.send_feature_report() -- source command bytes from rivalcfg/HeadsetControl
- PyInstaller --onefile will not auto-include hidapi.dll -- add manually in spec binaries=
- HID++ 0x1000 returns 0% while charging -- substitute charging status string, never display 0% on charge

---

## 6. Build Order

**Phase 1 -- HID Connectivity PoC**
Enumerate VID/PID, select usage_page=0xFF00 interface, raw read/write, prove Windows HID access works. No protocol, no UI. Resolves P1.

**Phase 2 -- HID++ 2.0 Protocol (Logitech)**
Feature discovery via Root 0x0000, receiver device index resolution, battery feature probe (0x1004->0x1000->0x1001), battery query, offline error handling. stdout only. Resolves P2, P4, P5.

**Phase 3 -- MonitorService + DeviceRegistry**
Asyncio background thread, 60s polling loop, thread-safe DeviceRegistry, queue-based UI skeleton, HotplugWatcher (WM_DEVICECHANGE, debounced). Mock UI updates only.

**Phase 4 -- Qt UI: Tray + Window**
QSystemTrayIcon with color-coded icon, right-click menu, BatteryWindow device cards, tooltip, QTimer queue drain. Close-to-tray behavior. winreg auto-start toggle. Wire to real MonitorService queue.

**Phase 5 -- SteelSeries HID Backend**
Proprietary 2.4GHz raw report driver. Source command bytes from rivalcfg/HeadsetControl. Filter vendor usage page. Wire into MonitorService. Budget discovery time for byte sequences.

**Phase 6 -- BLE Backend (bleak)**
BleakScanner + BleakClient, GATT Battery Service 0x180F/0x2A19, connect-read-disconnect polling. Validate sys.coinit_flags=0 is first in __main__. Wire into MonitorService. Most threading complexity -- do last.

**Phase 7 -- Notifications + Polish**
Windows-Toasts low battery alert, crossing-event trigger, 4-hour snooze, configurable threshold. Adaptive tray icons. Numeric % rendered into icon.

**Phase 8 -- Packaging**
PyInstaller spec: --collect-all PySide6, --collect-all winrt, binaries=[(hidapi.dll, .)]. Test on clean machine without Python installed.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Stack choices | HIGH | All versions confirmed on PyPI; alternatives abandonment confirmed via Snyk/OpenHub |
| HID++ 2.0 protocol | MEDIUM-HIGH | Linux kernel source + libratbag + Solaar; byte layouts confirmed from LKML patches |
| SteelSeries protocol | MEDIUM | Community reverse-engineering only; command bytes may vary by firmware version |
| BLE battery UUID | MEDIUM | Standard GATT path expected; device-specific confirmation requires hardware |
| Threading model | HIGH | bleak official docs explicit on MTA; pattern confirmed in troubleshooting guide |
| Packaging | HIGH | PyInstaller + PySide6 packaging well-documented in community |

**Gaps requiring hardware validation:**
- Which Aerox 5 interface is actually enumerated in practice (2.4GHz HID vs BLE) -- determines Phase 6 priority
- Exact SteelSeries Aerox 5 command bytes and battery response offsets
- G Pro X Wireless firmware version and which battery feature (0x1000 vs 0x1004) it implements
- Whether 0x1004 state_of_charge field is populated on the specific device firmware in use

---

## Research Flags for Roadmapper

- **Phases 1-2:** Well-documented patterns. HID++ 2.0 fully covered by Solaar + libratbag. No pre-phase research needed.
- **Phase 5 (SteelSeries):** Needs hardware testing to confirm byte sequences. Budget discovery time. Reference rivalcfg and HeadsetControl projects.
- **Phase 6 (BLE):** Standard GATT path documented. Risk is device-specific behavior. Confirm BT interface is actually used (Aerox 5 may default to 2.4GHz dongle mode in practice).
- **Phases 7-8:** Low research risk. Windows-Toasts and PyInstaller packaging are well-documented.
