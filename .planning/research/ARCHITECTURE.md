# Architecture Patterns: Windows Peripheral Battery Monitor

**Domain:** Windows system tray app — multi-protocol HID/BLE battery monitoring
**Researched:** 2026-06-01
**Overall confidence:** HIGH (protocol-level details), MEDIUM (SteelSeries proprietary bytes)

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Main Thread (Tkinter event loop)                           │
│  ┌──────────┐  ┌────────────────┐  ┌─────────────────────┐ │
│  │ TrayIcon │  │  BatteryWindow │  │  UI Update Handler  │ │
│  │ (pystray)│  │  (tkinter)     │  │  (.after() calls)   │ │
│  └────┬─────┘  └───────┬────────┘  └─────────┬───────────┘ │
│       └────────────────┴──────────────────────┘             │
│                         ▲  thread-safe queue.Queue          │
└─────────────────────────│───────────────────────────────────┘
                          │
┌─────────────────────────│───────────────────────────────────┐
│  Background Thread (asyncio event loop, MTA)                │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  MonitorService  (orchestrator)                     │   │
│  │  - owns DeviceRegistry                              │   │
│  │  - schedules polling tasks                          │   │
│  │  - receives hotplug events                          │   │
│  │  - pushes BatteryUpdate to UI queue                 │   │
│  └────┬──────────────────┬──────────────────┬──────────┘   │
│       │                  │                  │              │
│  ┌────▼──────┐  ┌────────▼──────┐  ┌───────▼────────┐    │
│  │HIDppDriver│  │SteelSeriesDriver│ │BLEDriver       │    │
│  │(Logitech  │  │(SS 2.4GHz)    │  │(bleak async)   │    │
│  │ LIGHTSPEED│  │               │  │                │    │
│  │ HID++2.0) │  │               │  │                │    │
│  └────┬──────┘  └────────┬──────┘  └───────┬────────┘    │
│       │                  │                  │              │
│  ┌────▼──────────────────▼──────────────────▼───────────┐  │
│  │  DeviceRegistry  {(vid, pid, dev_idx) -> DeviceState}│  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  HotplugWatcher  (hidden HWND + WM_DEVICECHANGE)    │   │
│  │  Runs own message pump in same background thread    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|---|---|---|
| `TrayIcon` | System tray icon, right-click menu, left-click to show window | MonitorService (reads state), BatteryWindow (show/hide) |
| `BatteryWindow` | Tkinter window showing per-device battery bars | Reads from shared DeviceRegistry snapshots via queue |
| `MonitorService` | Owns polling loop, schedules driver calls, coalesces results | All drivers, DeviceRegistry, UI queue |
| `DeviceRegistry` | Thread-safe dict of `(vid, pid, device_index)` -> `DeviceState` | MonitorService writes, UI reads snapshots |
| `HIDppDriver` | HID++ 2.0 receiver open, feature discovery, battery query | MonitorService calls it, writes to `hid` device handles |
| `SteelSeriesDriver` | Raw HID report send/receive for SS 2.4GHz dongles | MonitorService calls it, writes to `hid` device handles |
| `BLEDriver` | bleak async scan, GATT connect, characteristic read | MonitorService awaits it |
| `HotplugWatcher` | Windows `WM_DEVICECHANGE` hidden-window loop | Calls back into MonitorService to trigger rescan |

---

## Data Flow

```
Hotplug event (USB dongle inserted)
  -> HotplugWatcher (WM_DEVICECHANGE callback)
     -> MonitorService.on_device_change()
        -> re-enumerate hid.enumerate() with known VID/PID table
        -> if new device matches a driver, create/update DeviceRegistry entry
        -> schedule immediate battery poll for new device

Periodic poll tick (asyncio.create_task or loop.call_later)
  -> MonitorService._poll_all()
     -> for each registered device:
          HIDppDriver.get_battery(device_handle, feature_idx, dev_idx)
          OR SteelSeriesDriver.get_battery(device_handle)
          OR await BLEDriver.get_battery(ble_address)
     -> DeviceRegistry.update(key, BatteryLevel, Timestamp)
     -> ui_queue.put(BatteryUpdate(device_id, level, charging))

Tkinter after() loop (main thread, every 500ms)
  -> drain ui_queue (non-blocking get_nowait loop)
  -> update BatteryWindow labels / tray tooltip
```

---

## Threading and Async Model

### The One Rule

Tkinter is not thread-safe. All `tk.*` calls must happen on the main thread. The asyncio event loop must NOT run on the main thread because `asyncio.run()` blocks and cannot coexist with `root.mainloop()`.

### Recommended Pattern

```
Main thread:     tkinter mainloop + pystray (via pystray daemon thread)
Background thread: asyncio event loop (daemon=True)
Communication:   queue.Queue (thread-safe, no asyncio primitives needed)
```

```python
import sys
# MUST be set before importing pywin32, pythoncom, or anything that triggers COM init
sys.coinit_flags = 0  # Forces MTA; 0x2 would be STA (bad for bleak)

import threading, asyncio, queue

ui_queue = queue.Queue()

def start_background_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

bg_loop = asyncio.new_event_loop()
bg_thread = threading.Thread(target=start_background_loop, args=(bg_loop,), daemon=True)
bg_thread.start()

# To schedule async work from main thread:
asyncio.run_coroutine_threadsafe(some_coro(), bg_loop)

# To push results to UI from background:
ui_queue.put(update_object)

# In tkinter, drain queue:
def poll_queue():
    try:
        while True:
            update = ui_queue.get_nowait()
            apply_update(update)
    except queue.Empty:
        pass
    root.after(500, poll_queue)
```

### Why Not asyncio.run() Once at Top Level

bleak's documentation warns against calling `asyncio.run()` more than once. The recommended pattern is to create one event loop, keep it alive for the process lifetime, and schedule work into it. `run_forever()` with `run_coroutine_threadsafe` achieves this.

### pystray Threading

pystray's `icon.run()` blocks the calling thread. Run it in its own daemon thread OR call `icon.run_detached()` (if available in your pystray version) to avoid blocking the tkinter mainloop thread. The standard safe pattern: dedicate a third daemon thread to pystray, and communicate back to tkinter via `root.after()`.

---

## HID++ 2.0 Architecture (Logitech LIGHTSPEED)

### Protocol Overview

HID++ 2.0 is feature-based. Every device exposes a feature table. You discover feature indices at runtime, then send commands using those indices.

**Message format (short: 7 bytes, long: 20 bytes):**

```
Byte 0: report_id   — 0x10 (short) or 0x11 (long)
Byte 1: device_idx  — 0xFF for wired, 0x01-0x0F for wireless via receiver
Byte 2: feature_idx — runtime-discovered index for a given feature ID
Byte 3: func_swid  — upper nibble = function number (0-15), lower = SW ID (1-15)
Bytes 4-6 (or 4-19): parameters
```

### Feature Discovery Sequence

1. Open the receiver HID device by VID/PID (e.g., VID=0x046D, PID=0xC547 for Nano receiver).
2. Send a "GetFeature" request to **root feature 0x0000** asking for feature ID `0x1000` (BATTERY_LEVEL_STATUS). This returns the runtime index (e.g., `0x04`) that battery lives at on that device.
3. Cache this index in DeviceRegistry per device. Feature indices are stable for a session but can differ between device models.

```python
# Pseudocode: discover feature index for 0x1000
msg = build_msg(report_id=0x10, device_idx=dev_idx,
                feature_idx=0x00,       # root feature always at 0
                func_swid=0x01,         # GetFeature function
                params=[0x10, 0x00, 0x00])  # feature ID 0x1000
device.write(msg)
response = device.read(timeout_ms=1000)
battery_feature_idx = response[4]  # returned feature index
```

### Battery Query (feature 0x1000)

After discovering the index:

```python
msg = build_msg(report_id=0x10, device_idx=dev_idx,
                feature_idx=battery_feature_idx,
                func_swid=0x01,   # GetBatteryLevelStatus function 0
                params=[0x00, 0x00, 0x00])
device.write(msg)
response = device.read(timeout_ms=1000)
battery_percent = response[4]   # 0-100
battery_status  = response[6]   # 0=discharging, 1=recharging, 3=full
```

Feature 0x1001 (BATTERY_VOLTAGE) is used by newer devices (MX Master 3, G Pro X Superlight 2). Returns voltage in mV in bytes 4-5.

### Unsolicited Notifications

HID++ 2.0 supports event delivery from device (unsolicited reports arrive on the read channel with the feature_idx matching a known feature). For battery, devices send a notification when level drops a threshold. Solaar processes these in its main read loop. For a polling-first approach, you can treat all incoming messages uniformly — a read that matches a pending request is a response; others are notifications that update the cache.

### Receiver Addressing

A single USB HID handle to the receiver talks to up to 6 paired devices. `device_idx` 1-6 selects which wireless device receives the command. When a device is turned off, writes succeed (receiver accepts the byte) but no response arrives — so reads must time out. Use a short timeout (50-100 ms) and treat timeout as "device offline."

---

## SteelSeries 2.4GHz HID Architecture

### Protocol Characteristics

SteelSeries uses proprietary HID output/input reports — no published spec. Protocol reverse-engineered by community inspection of USB traffic with USBPcap/Wireshark.

**Observed pattern for Arctis headsets (generalizes to mice like Rival 650):**

```
Send HID output report: [0x00, 0xb0, 0x00, ...]
Read HID input report:  [0x00, 0xb0, battery_byte, charging_byte, ...]
```

`battery_byte` is 0-100 (percent). `charging_byte` is 0 (discharging) or 1 (charging). The leading `0x00` is the report ID for HID++ usage page; actual byte 1 (`0xb0`) is the command.

**This means:**
- Opening the device: `hid.device().open(vid, pid)` — works without kernel driver detach on Windows.
- Write: `device.write([0x00, 0xb0] + [0x00] * 62)` (64-byte padded).
- Read: `device.read(64, timeout_ms=2000)` — check response[1] == 0xb0.

Because the protocol is undocumented, each supported device model needs its own tested byte sequence in the device database. Factor the driver as `SteelSeriesDriver(query_bytes, response_battery_offset, response_charging_offset)`.

### Security Note (Mice and Keyboards)

Some SteelSeries HID interfaces for keyboards and mice are protected on Windows at the WinUSB/HID driver level (Microsoft's "exclusive access" policy). The HID device handle for the primary keyboard/mouse usage page cannot be opened from user space — only vendor-usage HID collections on the same physical device (which share a different `usage_page`) are accessible. When enumerating, filter for `usage_page=0xFF00` (vendor-defined) rather than standard usage pages.

---

## Bluetooth LE Battery Service Architecture (bleak)

### GATT Battery Profile

The Bluetooth SIG standardizes:
- Service UUID: `0x180F` (Battery Service)
- Characteristic UUID: `0x2A19` (Battery Level) — returns 1 byte, 0-100

All compliant BLE devices expose this. Non-compliant devices (many gaming headsets with BLE) may use vendor-specific characteristics.

### Device Discovery Pattern

```python
from bleak import BleakScanner, BleakClient

# Scan once, filter by service UUID to avoid connecting to unrelated devices
devices = await BleakScanner.discover(
    service_uuids=["0000180f-0000-1000-8000-00805f9b34fb"]
)
# Or: scan passively and match by device name/address from a known list
```

For known devices (bonded, appear in Windows Bluetooth registry), use the device's Bluetooth address directly — no scan needed:

```python
async with BleakClient(known_address) as client:
    raw = await client.read_gatt_char("00002a19-0000-1000-8000-00805f9b34fb")
    level = int.from_bytes(raw, "little")  # 0-100
```

### Windows MTA Requirement

bleak on Windows uses WinRT async APIs internally. These require the calling thread to be MTA. Set `sys.coinit_flags = 0` at process start before any import that touches COM (pywin32, pythoncom). If the app uses a UI that has already initialized STA (common with tkinter + pywin32), call:

```python
from bleak.backends.winrt.util import uninitialize_sta
uninitialize_sta()
```

If the UI framework is properly integrated with asyncio (rare with tkinter), call `allow_sta()` instead.

**The simplest safe pattern:** run bleak entirely in the daemon background thread with its own `asyncio.new_event_loop()`, and set `coinit_flags = 0` before any other import.

### Reconnection Strategy

BLE connections are not persistent — devices advertise intermittently. Read pattern:
1. On app start, scan for known device addresses (cached from pairing).
2. Attempt `BleakClient.connect()`. If device is off, it raises `BleakError`.
3. On success, read battery, disconnect, cache result.
4. Re-attempt on next poll cycle.

Do not hold a permanent BLE connection for battery reads — it drains device battery and is not needed for periodic reads.

---

## Device Registry Pattern

```python
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import time, threading

DeviceKey = Tuple[int, int, int]  # (vid, pid, device_index)

@dataclass
class DeviceState:
    display_name: str
    protocol: str           # "hidpp2", "steelseries", "ble"
    battery_percent: Optional[int] = None
    charging: bool = False
    online: bool = False
    last_seen: float = field(default_factory=time.time)

class DeviceRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._devices: Dict[DeviceKey, DeviceState] = {}

    def upsert(self, key: DeviceKey, state: DeviceState) -> None:
        with self._lock:
            self._devices[key] = state

    def snapshot(self) -> Dict[DeviceKey, DeviceState]:
        with self._lock:
            return dict(self._devices)
```

The registry is populated from a static `KNOWN_DEVICES` table keyed by `(vid, pid)`:

```python
KNOWN_DEVICES = {
    (0x046D, 0xC547): {"name": "Logitech Nano Receiver", "protocol": "hidpp2",
                        "devices": {1: "G Pro X Superlight"}},
    (0x1038, 0x12AD): {"name": "SteelSeries Arctis 7 Dongle", "protocol": "steelseries",
                        "query": [0x00, 0xb0], "batt_offset": 2},
}
```

On startup and on hotplug events, call `hid.enumerate()` and cross-reference against `KNOWN_DEVICES` to populate the registry.

---

## USB Hotplug Detection

Windows sends `WM_DEVICECHANGE` with `DBT_DEVICEARRIVAL` / `DBT_DEVICEREMOVECOMPLETE` to any window that has registered for `GUID_DEVINTERFACE_HID` (`{4D1E55B2-F16F-11CF-88CB-001111000030}`).

Pattern: create a hidden HWND in a dedicated thread (or reuse the background thread), register for device notifications, pump the Windows message loop.

```python
import win32gui, win32con, win32gui_struct

GUID_DEVINTERFACE_HID = "{4D1E55B2-F16F-11CF-88CB-001111000030}"

def _device_change_wnd_proc(hwnd, msg, wparam, lparam):
    if msg == win32con.WM_DEVICECHANGE:
        if wparam in (0x8000, 0x8004):  # DBT_DEVICEARRIVAL, DBT_DEVICEREMOVECOMPLETE
            monitor_service.schedule_rescan()
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def run_hotplug_watcher():
    wc = win32gui.WNDCLASS()
    wc.lpszClassName = "BatteryCheckerHotplug"
    wc.lpfnWndProc = _device_change_wnd_proc
    win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(wc.lpszClassName, "", 0, 0, 0, 0, 0, 0, 0, None, None)
    flt = win32gui_struct.PackDEV_BROADCAST_DEVICEINTERFACE(GUID_DEVINTERFACE_HID)
    win32gui.RegisterDeviceNotification(hwnd, flt, win32con.DEVICE_NOTIFY_WINDOW_HANDLE)
    win32gui.PumpMessages()  # blocks; run in daemon thread
```

`schedule_rescan()` uses `asyncio.run_coroutine_threadsafe(rescan_coro(), bg_loop)` to trigger re-enumeration on the background asyncio loop without blocking the message pump.

---

## Polling Strategy

| Protocol | Mechanism | Recommended Interval | Notes |
|---|---|---|---|
| HID++ 2.0 | Polling (read/write) | 60 seconds | Battery changes slowly; shorter = more USB traffic |
| HID++ 2.0 notifications | Unsolicited reads from device | Continuous read loop | Device pushes update on level drop; use as supplement |
| SteelSeries HID | Polling only | 60 seconds | No notification mechanism |
| BLE Battery Service | Polling (read_gatt_char) | 120 seconds | Connect, read, disconnect cycle adds ~1-2s overhead |
| BLE GATT notify | subscribe_to_characteristic | Continuous | Not all devices support it on 0x2A19 |

For the first version, implement polling-only for all protocols. Add HID++ notification handling later when the polling skeleton is proven.

**Stagger polls:** Don't poll all devices simultaneously. Use `asyncio.gather` with `asyncio.sleep` offsets to spread USB traffic.

---

## Component Build Order

Build in this sequence to get something working end-to-end at each step:

1. **DeviceRegistry + KNOWN_DEVICES table** — pure Python, no I/O, testable in isolation.
2. **HIDppDriver (read-only)** — open first known Logitech receiver, do feature discovery, read battery. No UI, just print to stdout. This validates the protocol layer.
3. **SteelSeriesDriver** — same approach for SS dongle with raw HID bytes.
4. **MonitorService (polling loop)** — `asyncio` background thread, drive both drivers on a 60s tick, print to stdout.
5. **HotplugWatcher** — add dongle connect/disconnect detection, verify rescan works.
6. **UI skeleton** — tkinter window + pystray tray icon, reading from `queue.Queue`. No real data yet (inject mock updates).
7. **Wire MonitorService to UI** — replace mock with real queue pushes from MonitorService.
8. **BLEDriver** — add bleak support last; it has the most threading complexity.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: asyncio.run() in a Loop
**What:** Calling `asyncio.run()` per poll tick or per device read.
**Why bad:** bleak's docs are explicit — calling `asyncio.run()` more than once causes unpredictable crashes on Windows (WinRT objects are not recreated cleanly).
**Instead:** `asyncio.new_event_loop()` once, keep it alive with `run_forever()`, submit work with `run_coroutine_threadsafe`.

### Anti-Pattern 2: pywin32 imported before coinit_flags
**What:** `import pywin32` (or any transitive import of `pythoncom`) before setting `sys.coinit_flags = 0`.
**Why bad:** pythoncom initializes the thread apartment to STA by default. bleak then hangs waiting for WinRT callbacks that never arrive in STA without a message loop.
**Instead:** `sys.coinit_flags = 0` must be the very first statement in `__main__`, before all other imports.

### Anti-Pattern 3: Holding persistent BLE connection
**What:** Connecting to a BLE device once at startup and holding the connection indefinitely.
**Why bad:** Gaming peripherals implement BLE battery service as a peripheral role — a held connection keeps the device's Bluetooth radio active, draining battery faster.
**Instead:** Connect, read, disconnect per polling cycle. Cache the address.

### Anti-Pattern 4: Polling HID++ without timeout on reads
**What:** `device.read(64)` with no timeout or a large timeout when device is off.
**Why bad:** If the wireless device is off, the receiver accepts the write but never responds. The read blocks the entire polling loop.
**Instead:** Always use `device.read(64, timeout_ms=100)` and treat empty/timeout response as offline.

### Anti-Pattern 5: Calling tkinter from the background thread
**What:** Any `widget.config()`, `label["text"] = x`, or `root.update()` from the asyncio background thread.
**Why bad:** Tkinter is built on Tcl/Tk which has a single-threaded interpreter. Cross-thread calls cause intermittent segfaults or silent corruption.
**Instead:** All UI mutations go through `ui_queue.put()` and are applied exclusively in the main thread's `after()` drain loop.

---

## Scalability Considerations

| Concern | 1-3 devices (MVP) | 10+ devices |
|---|---|---|
| Polling concurrency | Sequential per driver | `asyncio.gather` all driver calls in parallel |
| BLE connections | Sequential scan+connect | Pool of concurrent BleakClient tasks with semaphore |
| HID handles | Open/close per poll or keep open | Keep open (no driver contention on Windows HID) |
| UI update rate | 500ms queue drain | Same; throttle per-device update to avoid flicker |

---

## Sources

- Solaar HID++ 2.0 implementation reference: https://pwr-solaar.github.io/Solaar/implementation/
- Logitech HID++ 2.0 draft specification: https://lekensteyn.nl/files/logitech/logitech_hidpp_2.0_specification_draft_2012-06-04.pdf
- libratbag HID++ 2.0 driver deep wiki: https://deepwiki.com/libratbag/libratbag/3.2-logitech-hid++-2.0-driver
- bleak documentation (usage, Windows backend, troubleshooting): https://bleak.readthedocs.io/en/latest/
- bleak Windows threading (MTA/STA): https://bleak.readthedocs.io/en/latest/troubleshooting.html
- BLE battery service GATT read example: https://getwavecake.com/blog/reading-your-phones-battery-level-over-bluetooth-ble-with-python-bleak/
- SteelSeries HID battery monitor (Rival 650): https://github.com/ugurcandede/SteelSeries-Rival-650-Battery-Monitor
- SteelSeries Arctis HID reverse engineering: https://gist.github.com/flozz/df45b59d6d3594c4b843e00c5df16dd0
- pywin32 WM_DEVICECHANGE demo: https://github.com/kovidgoyal/pywin32/blob/master/win32/Demos/win32gui_devicenotify.py
- GUID_DEVINTERFACE_HID Windows docs: https://learn.microsoft.com/en-us/windows-hardware/drivers/install/guid-devinterface-hid
- asyncio + tkinter threading pattern: https://github.com/fluentpython/asyncio-tkinter
