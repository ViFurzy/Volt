# PeriphWatcher

## What This Is

A Windows background application that monitors battery levels of wireless gaming peripherals in one place — without requiring any manufacturer software (no G HUB, no SteelSeries GG). It auto-discovers known devices when their USB dongles are connected, shows battery status in a full app window and a system tray icon, and fires Windows toast notifications when a device's battery drops below a user-configured threshold.

## Core Value

Always know the battery level of every wireless peripheral at a glance, without installing bloatware.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Auto-discover known devices (Logitech LIGHTSPEED, SteelSeries) on dongle plug-in via built-in VID/PID registry
- [ ] Read battery level from Logitech G Pro X Wireless via HID++ 2.0 over LIGHTSPEED USB dongle
- [ ] Read battery level from SteelSeries Aerox 5 Wireless via 2.4GHz dongle and/or Windows BLE Battery Service
- [ ] Display all monitored devices and their battery levels in a main application window
- [ ] Minimize to Windows system tray; restore window from tray
- [ ] Send Windows toast notification when a device's battery drops below its configured threshold
- [ ] Per-device configurable notification thresholds (each device has its own low-battery percentage)
- [ ] Launch automatically at Windows startup, starting minimized to tray
- [ ] Extensible device registry — new device types can be added via config or UI with VID/PID and protocol

### Out of Scope

- Logitech G HUB integration — the whole point is to avoid manufacturer software
- SteelSeries GG integration — same reason
- macOS / Linux support — Windows 11 only for now
- Controlling device settings (DPI, lighting, etc.) — read-only battery monitor
- Devices connected via cable — wireless only

## Context

- User is a Windows 11 gamer with multiple wireless peripherals
- Target devices at launch: Logitech G Pro X Wireless (LIGHTSPEED USB receiver), SteelSeries Aerox 5 Wireless (2.4GHz dongle or Bluetooth)
- Logitech LIGHTSPEED uses HID++ 2.0 protocol (partially reverse-engineered, community libraries available)
- SteelSeries 2.4GHz uses proprietary HID protocol; Bluetooth variant can use standard Windows BLE Battery Service
- Windows exposes Bluetooth Battery Service for BLE-connected devices that implement it
- The app should handle devices being connected/disconnected at runtime (USB hot-plug events)

## Constraints

- **Tech Stack**: Python — preferred by the user; good ecosystem for HID (hidapi) and BLE (bleak)
- **Platform**: Windows 11 only — can use Windows-specific APIs freely
- **No external services**: Fully local, no cloud, no internet
- **No manufacturer software**: Must communicate with devices directly over HID/BT without any vendor SDK

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python as language | User preference; strong HID/BLE library ecosystem | — Pending |
| HID++ 2.0 for Logitech | Industry-standard reverse-engineered protocol; works without G HUB | — Pending |
| Windows BLE Battery Service for BT devices | Standard protocol, no reverse engineering needed | — Pending |
| Built-in VID/PID device registry | Ships with known devices; extensible for future additions | — Pending |
| Per-device notification thresholds | Different devices may have different usage patterns | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-01 after initialization*
