# Roadmap: PeriphWatcher

**Milestone:** v1.0 — Windows peripheral battery monitor without manufacturer software
**Granularity:** Fine
**Coverage:** 12/12 v1 requirements mapped

---

## Phases

- [x] **Phase 1: HID Connectivity PoC** - Prove Windows HID access via vendor-specific usage page; establish threading foundation *(complete 2026-06-01)*
- [x] **Phase 2: HID++ 2.0 Protocol** - Logitech feature discovery, battery probe chain, offline handling; battery data flows to stdout *(complete 2026-06-02)*
- [ ] **Phase 3: MonitorService + DeviceRegistry** - Asyncio background thread, 60s polling loop, hot-plug detection, queue-based updates
- [ ] **Phase 4: Qt UI — Window + Tray** - PySide6 main window, system tray icon, close-to-tray, winreg auto-start, settings persistence
- [ ] **Phase 5: SteelSeries HID Backend** - Proprietary 2.4GHz raw HID driver wired into MonitorService
- [ ] **Phase 6: Notifications** - Windows toast alerts, per-device thresholds, cooldown logic
- [ ] **Phase 7: Packaging + Distribution** - PyInstaller single-exe, hidapi.dll bundling, clean-machine validation

---

## Phase Details

### Phase 1: HID Connectivity PoC

**Goal**: Prove that Windows HID access works via the vendor-specific usage page, and lock in the threading architecture before any protocol work begins
**Depends on**: Nothing
**Requirements**: (none directly mapped — foundational gate for all HID work)
**Success Criteria** (what must be TRUE):

  1. A Python script can enumerate HID devices by VID/PID and open the interface with usage_page=0xFF00 without Access Denied
  2. Raw read/write round-trip to the Logitech LIGHTSPEED dongle succeeds (bytes out, bytes back)
  3. sys.coinit_flags = 0 is confirmed as the first executable line in `__main__` before any import, and this is documented in a code comment explaining why
  4. The asyncio-background-thread + queue.Queue + Qt-main-thread pattern is sketched in a stub that starts, communicates one message, and shuts down cleanly

**Plans**: 2 plans
Plans:

- [x] 01-01-PLAN.md — Project bootstrap, requirements.txt, src/__main__.py (coinit_flags guard), src/hid_poc.py (enumerate + open_path + raw read/write)
- [x] 01-02-PLAN.md — src/threading_stub.py (asyncio background thread + queue.Queue + QTimer drain + clean shutdown)

### Phase 2: HID++ 2.0 Protocol

**Goal**: Read a real battery percentage and charging status from the Logitech G Pro X Wireless via HID++ 2.0; handle all known protocol variants and offline edge cases
**Depends on**: Phase 1
**Requirements**: HID-01, BATT-01, BATT-02
**Success Criteria** (what must be TRUE):

  1. Feature discovery via Root feature 0x0000 succeeds: the driver resolves runtime feature indices for battery features without hardcoding them
  2. Battery probe chain executes in priority order (0x1004 → 0x1000 → 0x1001) and returns the correct integer percentage from whichever variant the device implements
  3. Charging status is read and surfaced when the device reports it (bool or enum, not just battery %)
  4. When the mouse is switched off, HID++ error 5 is caught, battery returns None, and the device state is set to OFFLINE without crashing the polling loop
  5. Receiver device index is discovered from the paired-device list (index 0x01–0x0E); device index 0xFF is never used for device queries

**Plans**: 4 plans
Plans:

- [x] 02-01-PLAN.md — src/hidpp/protocol.py + src/hidpp/__init__.py + pytest bootstrap + hardware raw-byte offset confirmation (Wave 1)
- [x] 02-02-PLAN.md — src/hidpp/receiver.py: find_receiver, open_receiver, discover_device_index (Wave 2, parallel with 02-03)
- [x] 02-03-PLAN.md — src/hidpp/features.py: BatteryResult, get_feature_index, battery_probe_chain 0x1004/0x1000/0x1001 (Wave 2, parallel with 02-02)
- [x] 02-04-PLAN.md — src/query_battery.py: integration script, hardware end-to-end test (Wave 3)

### Phase 3: MonitorService + DeviceRegistry

**Goal**: Battery data flows automatically from background polling to a UI-consumable queue; hot-plug events trigger device discovery and teardown without user action
**Depends on**: Phase 2
**Requirements**: HID-03, HID-04
**Success Criteria** (what must be TRUE):

  1. MonitorService runs on a daemon asyncio background thread and polls connected devices on a 60-second interval without blocking the main thread
  2. Plugging in the Logitech LIGHTSPEED dongle triggers device discovery via WM_DEVICECHANGE within 1 second (with 500ms debounce against duplicate events)
  3. Unplugging the dongle marks the affected device as OFFLINE in DeviceRegistry and pushes an update to the queue within the debounce window
  4. DeviceRegistry is a thread-safe store keyed by (vid, pid, dev_idx); all reads and writes from background thread and main thread are safe
  5. Queue.put() from background thread and QTimer drain on main thread function end-to-end: a mock consumer on the main thread receives DeviceState updates

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 03-01-PLAN.md — src/monitor/state.py + registry.py: DeviceState, DeviceStatus, KNOWN_DEVICES, thread-safe DeviceRegistry (Wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — src/monitor/service.py: MonitorService asyncio 60s poll loop, discover/poll_once, find_receiver verbose flag (Wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03-PLAN.md — src/monitor/hotplug.py: HotPlugWatcher hidden QWidget, RegisterDeviceNotification, WM_DEVICECHANGE + 500ms debounce (Wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 03-04-PLAN.md — src/monitor/app.py + run_monitor.py: wire service+registry+hotplug, QTimer drain → mock consumer, hardware checkpoint (Wave 4)

**UI hint**: yes

### Phase 4: Qt UI — Window + Tray

**Goal**: Users can see all monitored devices in a real application window, minimize to tray, restore from tray, and have the app start automatically at Windows login with settings that survive restarts
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, SYS-01, SYS-02
**Success Criteria** (what must be TRUE):

  1. Main window displays a device card for each entry in DeviceRegistry showing device name, battery percentage, and charging status; cards update live as queue messages arrive
  2. Closing the main window hides it (does not quit the process); the system tray icon remains visible and the background thread keeps polling
  3. Double-clicking the tray icon or using the "Show" context menu item restores the main window
  4. A "Launch at startup" toggle in the UI writes or removes the app path in HKCU\Software\Microsoft\Windows\CurrentVersion\Run without requiring admin rights
  5. Per-device notification thresholds and cooldown settings are saved to a JSON config file on disk and loaded correctly on next app launch

**Plans**: TBD
**UI hint**: yes

### Phase 5: SteelSeries HID Backend

**Goal**: Battery level is read from the SteelSeries Aerox 5 Wireless via its 2.4GHz dongle using raw proprietary HID and appears in the UI alongside the Logitech device
**Depends on**: Phase 4
**Requirements**: HID-02
**Success Criteria** (what must be TRUE):

  1. The SteelSeries driver opens the correct HID interface for the Aerox 5 dongle (vendor usage page, not mouse primary interface) without Access Denied
  2. A raw HID output report sends the battery query command and the response is parsed into an integer battery percentage
  3. The SteelSeries device appears as a live device card in the main window with the same data shape (name, %, charging status) as Logitech devices
  4. Dongle unplug marks the SteelSeries device OFFLINE via the same HID-04 code path used by the Logitech backend (no duplicate offline logic)

**Plans**: TBD

### Phase 6: Notifications

**Goal**: Users receive a Windows toast notification when any device drops below its configured battery threshold, without being spammed by repeated alerts
**Depends on**: Phase 5
**Requirements**: NOTIF-01, NOTIF-02
**Success Criteria** (what must be TRUE):

  1. A Windows toast notification (visible in Action Center) fires when a device's battery percentage crosses below its per-device threshold for the first time
  2. The threshold is read from the persisted settings (SYS-02) and defaults to 15% for devices with no explicit setting
  3. After a notification fires for a device, no further notification is sent for that device until the cooldown period has elapsed (default 4 hours)
  4. The cooldown resets if the device goes offline and returns online (preventing a single low-battery state from blocking alerts across sessions)

**Plans**: TBD

### Phase 7: Packaging + Distribution

**Goal**: PeriphWatcher ships as a single Windows executable that runs on a machine with no Python installed and passes a clean-machine smoke test
**Depends on**: Phase 6
**Requirements**: (consolidates all prior phases into distributable form)
**Success Criteria** (what must be TRUE):

  1. PyInstaller builds a single --onefile .exe with no DLL-not-found errors on launch; hidapi.dll is bundled via the spec `binaries=` list
  2. PySide6 and winrt WinRT DLLs are collected completely via `--collect-all PySide6` and `--collect-all winrt`; the app starts and shows the tray icon
  3. The .exe runs on a clean Windows 11 VM with no Python or Logitech software installed and successfully reads battery from the LIGHTSPEED dongle
  4. sys.coinit_flags = 0 remains the first executable statement after PyInstaller entry-point wrapping (verified by inspecting the boot-time import order)

**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. HID Connectivity PoC | 2/2 | ✓ Complete | 2026-06-01 |
| 2. HID++ 2.0 Protocol | 4/4 | ✓ Complete | 2026-06-02 |
| 3. MonitorService + DeviceRegistry | 3/4 | In Progress|  |
| 4. Qt UI — Window + Tray | 0/? | Not started | - |
| 5. SteelSeries HID Backend | 0/? | Not started | - |
| 6. Notifications | 0/? | Not started | - |
| 7. Packaging + Distribution | 0/? | Not started | - |

---

## Architecture Invariants

These constraints must hold across every phase. Violations are bugs, not trade-offs.

| Invariant | Enforced in | Reason |
|-----------|-------------|--------|
| `sys.coinit_flags = 0` is the first line of `__main__`, before all imports | Phase 1 PoC; Phase 7 packaging validation | bleak WinRT backend requires MTA; STA initialized by Qt/pywin32 will cause `await client.connect()` to hang forever with no error |
| All HID and BLE I/O runs exclusively on the asyncio background thread | Phase 2 onward | Qt requires all UI calls on main thread; mixing threads causes data races and crash-on-exit |
| UI communicates with background thread only via `queue.Queue` | Phase 3 onward | Only thread-safe cross-thread mechanism that requires no locks in calling code |
| HID interface selected by `usage_page=0xFF00` (vendor-specific), never by primary interface | Phase 1 PoC | Windows locks usage_page=0x0001 mouse/keyboard interfaces; all HID calls fail with Access Denied |
| HID++ feature indices are discovered at runtime via Root feature 0x0000 | Phase 2 | Feature indices are firmware-assigned; hardcoding breaks on any firmware variant |

---
*Created: 2026-06-01*
*Last updated: 2026-06-02 — Phase 3 planned: 4 plans in 4 waves*
