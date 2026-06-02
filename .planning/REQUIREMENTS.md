# Requirements: PeriphWatcher

**Defined:** 2026-06-01
**Core Value:** Always know the battery level of every wireless peripheral at a glance, without installing bloatware.

## v1 Requirements

### HID Communication

- [ ] **HID-01**: App reads battery level from Logitech G Pro X Wireless via HID++ 2.0 over LIGHTSPEED USB dongle
- [ ] **HID-02**: App reads battery level from SteelSeries Aerox 5 Wireless via 2.4GHz dongle (proprietary HID protocol)
- [x] **HID-03**: App auto-discovers known devices when their USB dongle is plugged in (built-in VID/PID registry, no user config required)
- [x] **HID-04**: App detects when a dongle is unplugged and marks affected device as offline

### Battery Display

- [ ] **BATT-01**: App displays current battery percentage for each monitored device
- [ ] **BATT-02**: App shows a charging indicator when a device is actively charging (if reported by device)

### UI

- [ ] **UI-01**: Main window lists all monitored devices with their name, battery %, and charging status
- [ ] **UI-02**: Closing the main window minimizes the app to the system tray (does not quit)
- [ ] **UI-03**: System tray icon is present when app is running; double-clicking or using the context menu restores the main window

### Notifications

- [ ] **NOTIF-01**: App sends a Windows toast notification when a device's battery drops below a per-device configurable threshold
- [ ] **NOTIF-02**: Notification cooldown prevents the same low-battery alert from repeating within a configurable time window

### System Integration

- [ ] **SYS-01**: App registers in Windows startup so it launches automatically at login, starting minimized to tray
- [ ] **SYS-02**: User settings (per-device thresholds, cooldown period) persist to disk and survive restarts

## v2 Requirements

### Bluetooth

- **BT-01**: Read battery from Bluetooth-connected devices via Windows BLE GATT Battery Service
- **BT-02**: BLE device auto-discovery for paired Bluetooth peripherals

### UI Enhancements

- **UIV2-01**: Color-coded battery level indicators (green / yellow / red)
- **UIV2-02**: Numeric battery % rendered into the system tray icon image
- **UIV2-03**: System tray icon tooltip listing all devices and their levels
- **UIV2-04**: Settings screen in the UI to configure thresholds and cooldown (instead of config file only)

### Notifications

- **NOTIFV2-01**: Critical battery second alert at a lower threshold per device

## Out of Scope

| Feature | Reason |
|---------|--------|
| Logitech G HUB integration | The whole point is to avoid manufacturer software |
| SteelSeries GG integration | Same reason |
| macOS / Linux support | Windows 11 only; HID/BLE APIs are platform-specific |
| Device control (DPI, lighting, etc.) | Read-only battery monitor — controlling devices adds significant complexity |
| Cable-connected devices | Wireless only; wired devices don't have battery |
| Battery life prediction / time remaining | HID++ doesn't reliably expose this; would require inference |
| Cloud sync or telemetry | Fully local app, no internet required |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| HID-01 | Phase 2 | Pending |
| HID-02 | Phase 5 | Pending |
| HID-03 | Phase 3 | Complete |
| HID-04 | Phase 3 | Complete |
| BATT-01 | Phase 2 | Pending |
| BATT-02 | Phase 2 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| NOTIF-01 | Phase 6 | Pending |
| NOTIF-02 | Phase 6 | Pending |
| SYS-01 | Phase 4 | Pending |
| SYS-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-01*
*Last updated: 2026-06-01 after roadmap creation — corrected NOTIF-01/02 to Phase 6, SYS-02 to Phase 4*
