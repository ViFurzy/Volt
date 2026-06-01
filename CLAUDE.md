# PeriphWatcher — Project Guide

## What This Is

Windows 11 Python app monitoring battery levels of wireless gaming peripherals (Logitech G Pro X Wireless via LIGHTSPEED USB dongle, SteelSeries Aerox 5 Wireless via 2.4GHz dongle) without manufacturer software. Full UI window + system tray + Windows toast notifications.

## Architecture Invariants

These constraints hold across every phase. Violations are bugs, not tradeoffs.

| Invariant | Why |
|-----------|-----|
| `sys.coinit_flags = 0` is the **very first line** in `__main__`, before **all imports** | bleak's WinRT backend requires COM MTA mode. Qt and pywin32 initialize STA. If STA is initialized first, `await client.connect()` hangs forever with no error. |
| All HID and BLE I/O runs exclusively on the asyncio background thread | Qt requires all UI calls on the main thread. Mixing threads causes data races and crash-on-exit. |
| UI communicates with the background thread only via `queue.Queue` | The only thread-safe cross-thread mechanism that requires no locks in calling code. |
| HID interface selected by `usage_page=0xFF00` (vendor-specific), never by primary interface | Windows locks `usage_page=0x0001` mouse/keyboard interfaces. All HID calls fail with Access Denied if you open the wrong interface. |
| HID++ feature indices discovered at runtime via Root feature 0x0000, never hardcoded | Feature indices are firmware-assigned. Hardcoding breaks across firmware variants. |

## Tech Stack

| Purpose | Library | Version |
|---------|---------|---------|
| HID device communication | `hid` (hidapi wrapper) | 1.0.9 |
| Bluetooth LE | `bleak` | 3.0.2 |
| UI framework + system tray | `PySide6` | 6.11.1 |
| Windows toast notifications | `Windows-Toasts` | 1.3.1 |
| Windows startup (winreg) | stdlib | — |
| Packaging | `PyInstaller` | 6.17+ |

**Do NOT use:** `pywinusb` (abandoned), `PyBluez` (abandoned), `winotify` (fragile), `PyQt6` (licensing).

## GSD Workflow

This project is managed with GSD (Get Shit Done). Planning artifacts live in `.planning/`.

**Key files:**
- `.planning/ROADMAP.md` — 7-phase execution plan
- `.planning/REQUIREMENTS.md` — v1 requirements with REQ-IDs
- `.planning/STATE.md` — current project state
- `.planning/research/` — domain research (stack, features, architecture, pitfalls)

**Phase commands:**
- `/gsd:plan-phase N` — plan a phase before execution
- `/gsd:execute-phase N` — execute a planned phase
- `/gsd:discuss-phase N` — discuss approach before planning
- `/gsd:progress` — see current status

**Current state:** Project initialized. Ready for Phase 1.

## Phase 1 Entry Criteria

Before writing any HID++ protocol code:
1. Confirm `sys.coinit_flags = 0` position is correct
2. Confirm `usage_page=0xFF00` opens without Access Denied on the LIGHTSPEED dongle
3. Confirm asyncio background thread + `queue.Queue` + Qt main thread pattern works

Phase 1 is a PoC — it does NOT need to read battery. It must prove HID access works and the threading model is sound.
