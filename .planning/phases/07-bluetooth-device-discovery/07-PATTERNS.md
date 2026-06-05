# Phase 7: Bluetooth Device Discovery - Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 9 (5 new, 4 modified)
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/monitor/bt_backend.py` | service | async request-response | `src/steelseries/driver.py` | role-match (async variant) |
| `src/monitor/__init__.py` (no change) | package init | — | `src/monitor/__init__.py` | exact |
| `src/monitor/state.py` | model | CRUD | `src/monitor/state.py` (self) | exact (extend) |
| `src/monitor/service.py` | service | event-driven + CRUD | `src/monitor/service.py` (self) | exact (extend) |
| `src/ui/devices_page.py` | component | request-response | `src/ui/settings_page.py` | role-match |
| `src/ui/main_window.py` | component | request-response | `src/ui/main_window.py` (self) | exact (extend) |
| `src/ui/settings_manager.py` | config/utility | CRUD | `src/ui/settings_manager.py` (self) | exact (extend) |
| `tests/test_bt_backend.py` | test | — | `tests/test_service.py` | exact (same pattern) |
| `tests/test_devices_page.py` | test | — | `tests/test_ui_device_card.py` | exact (same pattern) |

---

## Pattern Assignments

### `src/monitor/bt_backend.py` (service, async request-response)

**Analog:** `src/steelseries/driver.py` — same pattern of a self-contained backend module that exports probe/find functions consumed by `MonitorService`. The BT backend replaces the `hid` calls with WinRT/bleak async calls.

**Module docstring pattern** (`src/steelseries/driver.py` lines 1-13):
```python
"""
<Purpose> — <context>.

Interface selection: <key design decision>.
<Constraint or lifecycle note>.
"""
```

**Imports pattern** (modeled on `src/steelseries/driver.py` lines 15-17 and research patterns):
```python
import asyncio
from bleak import BleakClient
from bleak.exc import BleakCharacteristicNotFoundError, BleakError
from winrt.windows.devices.enumeration import DeviceInformation
from winrt.windows.devices.bluetooth import BluetoothDevice
from hidpp.features import BatteryResult  # reuse existing result type if needed
```

**Public constants block** (`src/steelseries/driver.py` lines 22-33 — follow same naming style):
```python
BATTERY_PKEY = "{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_CHAR_UUID    = "00002a19-0000-1000-8000-00805f9b34fb"
```

**Enumerate function pattern** (`src/steelseries/driver.py` lines 55-77 — find_dongle is the analog):
```python
# find_dongle pattern:
def find_dongle(vid: int = SS_VID, verbose: bool = False) -> list[dict]:
    all_devices = hid.enumerate(vid, 0)
    ...
    return [d for d in all_devices if d["interface_number"] == SS_VENDOR_INTERFACE]
```
For BT backend, this becomes an `async def winrt_enumerate_bt() -> list[dict]` that awaits `DeviceInformation.find_all_async(aqs, props)` and returns a list of dicts with keys `id`, `name`, `battery`, `type`.

**Battery probe function pattern** (`src/steelseries/driver.py` lines 93-134 — ss_battery_probe is the analog):
```python
def ss_battery_probe(device, dev_idx: int) -> "BatteryResult | None":
    ...
    for _ in range(_SS_MAX_RESPONSE_READS):
        resp = device.read(64, timeout_ms=100)
        if not resp:
            break
        if resp[0] == _SS_BATTERY_CMD:
            ...
            return BatteryResult(...)
    return None  # device off or out of range
```
For BT backend, `gatt_battery(ble_address, timeout)` follows the same None-on-failure contract. Return `int | None`, not `BatteryResult`, since GATT only gives a percentage with no voltage.

**Error handling pattern** (`src/steelseries/driver.py` line 119 — `except Exception: pass` is wrong; use specific exceptions):
```python
# From research Pattern 2 — use specific exception hierarchy:
async def gatt_battery(ble_address: str, timeout: float = 5.0) -> int | None:
    try:
        async with BleakClient(ble_address, timeout=timeout) as client:
            data = await client.read_gatt_char(BATTERY_CHAR_UUID)
            return int.from_bytes(data, "little")
    except BleakCharacteristicNotFoundError:
        return None
    except BleakError:
        return None
    except Exception:
        return None
```

**Input validation guard** (security: type-check WinRT property bag before `int()` conversion):
```python
# Matches architecture invariant: never trust raw external data without guard
battery_raw = d.properties.get(BATTERY_PKEY)
battery_pct = int(battery_raw) if isinstance(battery_raw, (int, float)) else None
```

---

### `src/monitor/state.py` (model, CRUD — extend existing file)

**Analog:** `src/monitor/state.py` (self — targeted addition to existing file)

**Existing dataclass pattern** (lines 29-46 — new `BtDeviceInfo` must follow same style):
```python
@dataclass(frozen=True)
class DeviceState:
    """Full snapshot of one peripheral's current state (D-01, D-02).
    ...
    """
    vid: int
    pid: int
    dev_idx: int
    device_name: str
    percent: int | None
    charging: bool
    status: DeviceStatus
```

**New dataclass to add** — follow same frozen=True, docstring, field order convention:
```python
@dataclass(frozen=True)
class BtDeviceInfo:
    """Snapshot of a discovered Bluetooth device (BT-01).

    bt_id is the WinRT DeviceInformation.id string (stable across reboots).
    ble_address is None for classic Bluetooth (BR/EDR) devices.
    battery is None when no tier resolved a value.
    """
    bt_id: str
    name: str
    battery: int | None
    ble_address: str | None  # None for classic BT; set for BLE
    type: str  # "bt"
```

**Dict registry pattern** (lines 51-63 — `KNOWN_DEVICES` and `DEVICE_PROBES` are the model):
```python
# Existing pattern — new BtDeviceRegistry is a separate dict, not mixed into KNOWN_DEVICES
KNOWN_DEVICES: dict[tuple[int, int], str] = {
    (0x046D, 0x0ABA): "G Pro X Wireless",
    (0x1038, 0x1852): "Aerox 5 Wireless",
}
```
For BT devices: key is `bt_id: str` (WinRT DeviceInformation.id), value is `BtDeviceInfo`.

---

### `src/monitor/service.py` (service, event-driven + CRUD — extend existing file)

**Analog:** `src/monitor/service.py` (self — extend `discover()` and `poll_once()`)

**Thread-safe cross-thread scheduling pattern** (lines 107-113 — `rescan()` is the exact model for `scan_bt_devices()`):
```python
def rescan(self) -> concurrent.futures.Future:
    """Thread-safe entry point for the hot-plug callback (03-03).

    Schedules a new discover() run on the bg asyncio loop and returns the
    Future so the caller can optionally wait or add callbacks.
    """
    return asyncio.run_coroutine_threadsafe(self.discover(), self._loop)
```
For `scan_bt_devices()`: same signature, schedules `bt_backend.winrt_enumerate_bt()` on `self._loop`, puts results on `self._ui_queue`.

**discover() extension point** (lines 135-227 — the BT discover block slots in after the SteelSeries block):
```python
# Pattern: each brand gets its own block inside discover()
# Logitech block: lines 179-203
# SteelSeries block: lines 205-226
# BT block: add after line 226 — same structure:
#   bt_devices = await bt_backend.winrt_enumerate_bt()
#   for device in bt_devices:
#       key = ("bt", device["id"])
#       if key in self._bt_open: continue
#       ...
#       self._ui_queue.put(ScanResultEvent(device))
```

**poll_once() extension point** (lines 228-299 — BT polling follows same None-guard pattern):
```python
# Existing pattern for offline handling (lines 266-271):
if result is None or result.percent == 0:
    offline_state = self._registry.mark_offline(key)
    if offline_state is not None:
        self._ui_queue.put(offline_state)
```
For BT: `battery = await bt_backend.resolve_battery(device_info)` — `None` result means show "battery unknown", not OFFLINE (device may be on but just not exposing battery).

**Open handle dict pattern** (lines 63-67 — follow same comment convention for new BT dict):
```python
# Open HID device handles keyed by (vid, pid, dev_idx).
# Accessed exclusively on the bg asyncio thread.
self._open: dict[tuple[int, int, int], object] = {}
```
Add:
```python
# Discovered BT devices keyed by bt_id str.
# Accessed exclusively on the bg asyncio thread.
self._bt_devices: dict[str, BtDeviceInfo] = {}
```

---

### `src/ui/devices_page.py` (component, request-response — new file)

**Analog:** `src/ui/settings_page.py` — closest existing QWidget subclass page with a layout, heading, interactive controls, and config persistence.

**Imports pattern** (`src/ui/settings_page.py` lines 1-16):
```python
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)
from ui.settings_manager import is_startup_enabled, load_config, save_config, set_startup
```
For DevicesPage, replace settings imports with:
```python
import asyncio
import concurrent.futures
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from ui.settings_manager import load_config, save_config
```

**QWidget subclass constructor pattern** (`src/ui/settings_page.py` lines 19-59):
```python
class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(heading)
        ...
        layout.addStretch()
```

**Thread-safe slot-to-coroutine pattern** (`src/monitor/hotplug.py` lines 172-179 and RESEARCH Pattern — `DevicesPage._on_scan_clicked` must use this):
```python
# From hotplug.py — cross-thread scheduling:
self._service._loop.call_soon_threadsafe(self._debouncer.schedule)

# From RESEARCH Pattern — for DevicesPage scan button:
def _on_scan_clicked(self) -> None:
    future = asyncio.run_coroutine_threadsafe(
        self._service.scan_bt_devices(), self._loop
    )
    future.add_done_callback(self._on_scan_done)
```
Note: `self._loop` and `self._service` are injected at construction time; DevicesPage must NOT own or start the asyncio loop.

**Signal blocker pattern** (`src/ui/settings_page.py` lines 44-46 — use for any checkbox state init):
```python
self._startup_cb.blockSignals(True)
self._startup_cb.setChecked(is_startup_enabled())
self._startup_cb.blockSignals(False)
self._startup_cb.toggled.connect(self._on_startup_toggled)
```

**paintEvent override** (`src/ui/settings_page.py` lines 77-81 — required for QSS background on QWidget subclass):
```python
def paintEvent(self, event) -> None:
    opt = QStyleOption()
    opt.initFrom(self)
    p = QPainter(self)
    self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
```
Copy this verbatim into DevicesPage — Qt requires it for background-color QSS on non-QFrame QWidget subclasses.

**Config read pattern for populating list on init** (`src/ui/settings_page.py` lines 52-56):
```python
cfg = load_config()
self._tray_close_cb.setChecked(cfg.get("close_behavior") == "tray")
```
For DevicesPage: `monitored = load_config().get("monitored_devices", [])` to populate the monitored list widget on construction.

---

### `src/ui/main_window.py` (component, request-response — extend existing file)

**Analog:** `src/ui/main_window.py` (self — swap placeholder + add `on_scan_result`)

**Placeholder swap pattern** (lines 63-65 — this is exactly what gets replaced for Devices):
```python
# Pages 1-3 — Placeholders
for name in ("Devices", "History", "Profiles"):
    self._stack.addWidget(_PlaceholderPage(name))  # indices 1, 2, 3
```
Becomes:
```python
self._devices_page = DevicesPage(service=..., loop=...)
self._stack.addWidget(self._devices_page)  # index 1
for name in ("History", "Profiles"):
    self._stack.addWidget(_PlaceholderPage(name))  # indices 2, 3
```

**on_device_update create-or-update pattern** (lines 165-184 — `on_scan_result` follows same structure):
```python
def on_device_update(self, state: DeviceState) -> None:
    key = (state.vid, state.pid, state.dev_idx)
    if key not in self._cards:
        card = DeviceCard(state)
        self._cards[key] = card
        stretch_idx = self.dashboard_layout.count() - 1
        self.dashboard_layout.insertWidget(stretch_idx, card)
        self._sidebar.register_device(key, state.device_name)
        self._count_label.setText(f"All Devices ({len(self._cards)})")
    else:
        self._cards[key].update_state(state)
```

---

### `src/ui/settings_manager.py` (config/utility — extend existing file)

**Analog:** `src/ui/settings_manager.py` (self — add `monitored_devices` to `_DEFAULTS`)

**_DEFAULTS extension pattern** (line 23 — single dict literal, add one key):
```python
# Existing:
_DEFAULTS: dict = {"launch_at_startup": False, "thresholds": {}, "close_behavior": None}

# Extended (add cooldown_hours if not already present, then monitored_devices):
_DEFAULTS: dict = {
    "launch_at_startup": False,
    "thresholds": {},
    "close_behavior": None,
    "cooldown_hours": 4,
    "monitored_devices": [],  # list[dict] with keys: id, name, type, ble_address
}
```

**Backward-compatible merge pattern** (lines 48-51 — the `{**_DEFAULTS, **data}` merge is already backward-compatible; no additional code needed):
```python
return {**_DEFAULTS, **data}
```
Adding `monitored_devices: []` to `_DEFAULTS` is sufficient — existing configs without the key will get `[]` automatically on `load_config()`.

**save_config call-site pattern** (`src/ui/settings_page.py` lines 63-65 — use same pattern in DevicesPage):
```python
cfg = load_config()
cfg["launch_at_startup"] = checked
save_config(cfg)
```
For DevicesPage add/remove device:
```python
cfg = load_config()
cfg["monitored_devices"].append({"id": bt_id, "name": name, "type": "bt", "ble_address": ble_address})
save_config(cfg)
```

---

### `tests/test_bt_backend.py` (test — new file)

**Analog:** `tests/test_service.py` — same pattern of asyncio unit tests with patched external I/O, organized in classes.

**Test file header pattern** (`tests/test_service.py` lines 1-20):
```python
"""Unit tests for monitor.service.MonitorService.

All tests exercise discover() and poll_once() directly via asyncio.run() —
no real hardware, no real threads. find_receiver, open_receiver, find_dongle,
and DEVICE_PROBES are patched at the monitor.service module namespace.
"""
import asyncio
import queue
import pytest
from hidpp.receiver import DEVICE_IDX
from monitor.registry import DeviceRegistry
from monitor.service import MonitorService
```
For test_bt_backend.py:
```python
"""Unit tests for monitor.bt_backend.

All async functions tested via asyncio.run() with mocked WinRT and bleak.
No hardware required. WinRT DeviceInformation and BleakClient patched at
the bt_backend module namespace.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
```

**asyncio.run() test pattern** (`tests/test_service.py` lines 83-89 — call async functions directly):
```python
asyncio.run(service.discover())
state = registry.get(GPRO_KEY)
assert state.device_name == "G Pro X Wireless"
```
For bt_backend tests:
```python
result = asyncio.run(bt_backend.gatt_battery("AA:BB:CC:DD:EE:FF"))
assert result is None
```

**mocker.patch pattern** (`tests/test_service.py` lines 79-81 — patch at module namespace, not source):
```python
mocker.patch("monitor.service.find_receiver", return_value=[GPRO_INTERFACE])
mocker.patch("monitor.service.find_dongle", return_value=[])
mocker.patch("monitor.service.open_receiver", return_value=mock_handle)
```
For bt_backend:
```python
mocker.patch("monitor.bt_backend.BleakClient", ...)
mocker.patch("monitor.bt_backend.DeviceInformation.find_all_async", ...)
```

**Class-based test grouping** (`tests/test_service.py` lines 71-200):
```python
class TestDiscover:
    def test_registers_online_state_for_known_device(self, mocker): ...
    def test_puts_state_on_queue(self, mocker): ...

class TestPollOnce:
    def test_online_battery_result_upserts_and_queues(self, mocker): ...
```
For test_bt_backend.py:
```python
class TestWinrtEnumerate:
    def test_returns_list_of_dicts(self, mocker): ...
    def test_battery_property_none_when_absent(self, mocker): ...

class TestGattBattery:
    def test_success_returns_int(self, mocker): ...
    def test_no_service_returns_none(self, mocker): ...
    def test_bleak_error_returns_none(self, mocker): ...

class TestResolveBattery:
    def test_winrt_path_short_circuits(self, mocker): ...
    def test_fallthrough_to_gatt(self, mocker): ...
```

---

### `tests/test_devices_page.py` (test — new file)

**Analog:** `tests/test_ui_device_card.py` — same pytest-qt headless widget testing pattern.

**Test file header pattern** (`tests/test_ui_device_card.py` lines 1-7):
```python
"""Unit tests for DeviceCard widget.

Strategy (from RESEARCH Validation Architecture):
  - NEVER call widget.show() in headless tests — Qt show() requires a display.
  - Instantiate DeviceCard and call methods directly.
  - pytest-qt's qapp fixture provides the QApplication singleton.
"""
```

**qapp fixture pattern** (`tests/test_ui_device_card.py` lines 33-38 — use `qapp` as first arg for all widget tests):
```python
def test_is_qframe_subclass(self, qapp):
    from ui.device_card import DeviceCard
    state = _make_state(80, DeviceStatus.ONLINE)
    card = DeviceCard(state)
    assert isinstance(card, QFrame)
```
For DevicesPage tests:
```python
def test_constructs(self, qapp):
    from ui.devices_page import DevicesPage
    page = DevicesPage(service=MagicMock(), loop=MagicMock())
    assert page is not None
```

**isHidden() over isVisible() pattern** (`tests/test_ui_device_card.py` lines 199-206 — headless tests must use isHidden):
```python
# isVisible() requires the parent chain to be shown — use isHidden() instead
assert not card._charging_indicator.isHidden()
assert card._charging_indicator.isHidden()
```

**Inline import pattern** (`tests/test_ui_device_card.py` lines 40, 47 — import inside test functions):
```python
def test_is_qframe_subclass(self, qapp):
    from ui.device_card import DeviceCard   # inside test body
    ...
```

---

## Shared Patterns

### Architecture Invariant: All async I/O on Background Thread

**Source:** `src/monitor/service.py` docstring lines 1-14 and `src/monitor/hotplug.py` lines 172-179
**Apply to:** `src/monitor/bt_backend.py`, `src/ui/devices_page.py`

```python
# Cross-thread scheduling — Qt slot to asyncio bg thread:
# From hotplug.py line 179:
self._service._loop.call_soon_threadsafe(self._debouncer.schedule)

# From rescan() in service.py lines 107-113:
return asyncio.run_coroutine_threadsafe(self.discover(), self._loop)

# NEVER call asyncio.run() from a Qt slot — use run_coroutine_threadsafe
```

### Queue-Based UI Update

**Source:** `src/monitor/app.py` lines 65-77 and `src/monitor/service.py` lines 196-203
**Apply to:** `src/monitor/service.py` (BT scan results), `src/ui/main_window.py` (consume scan results)

```python
# Producer (bg thread): service.py line 203:
self._ui_queue.put(state)

# Consumer (Qt main thread via QTimer): app.py lines 65-77:
def drain(self) -> None:
    try:
        while True:
            state: DeviceState = self.ui_queue.get_nowait()
            self._consumer(state)
    except queue.Empty:
        pass
```
BT scan results should flow through the same `_ui_queue` with a new event type (e.g., `BtScanResultEvent`) so `MonitorApp.drain()` can route them.

### Config Read-Modify-Write

**Source:** `src/ui/settings_page.py` lines 61-65 and `src/ui/settings_manager.py` lines 37-59
**Apply to:** `src/ui/devices_page.py` (add/remove monitored devices), `src/ui/settings_manager.py` (new default key)

```python
# Pattern from settings_page.py:
def _on_startup_toggled(self, checked: bool) -> None:
    set_startup(checked)
    cfg = load_config()
    cfg["launch_at_startup"] = checked
    save_config(cfg)
```

### Backward-Compatible Config Extension

**Source:** `src/ui/settings_manager.py` lines 37-51
**Apply to:** `src/ui/settings_manager.py` (add `monitored_devices` key)

```python
# _DEFAULTS merge already handles new keys backward-compatibly:
return {**_DEFAULTS, **data}
# Adding a new key to _DEFAULTS with a safe default is the full extension.
# No migration code needed.
```

### None-Guard on External Data

**Source:** `src/steelseries/driver.py` lines 122-125 and architecture pattern
**Apply to:** `src/monitor/bt_backend.py` (WinRT property bag, GATT byte decode)

```python
# SteelSeries guard pattern:
pct = max(0, min(100, pct))  # clamp to valid range

# BT backend must guard WinRT property:
battery_raw = d.properties.get(BATTERY_PKEY)
battery_pct = int(battery_raw) if isinstance(battery_raw, (int, float)) else None

# And guard GATT bytes (always check length):
data = await client.read_gatt_char(BATTERY_CHAR_UUID)
return int.from_bytes(data[:1], "little") if data else None
```

### Test: asyncio.run() for Async Functions Under Test

**Source:** `tests/test_service.py` lines 83, 104
**Apply to:** `tests/test_bt_backend.py`

```python
# All async functions tested synchronously:
asyncio.run(service.discover())
```

### Test: Patch at Module Namespace

**Source:** `tests/test_service.py` lines 79-81
**Apply to:** `tests/test_bt_backend.py`, `tests/test_devices_page.py`

```python
mocker.patch("monitor.service.find_receiver", return_value=[GPRO_INTERFACE])
# Not: mocker.patch("hidpp.receiver.find_receiver", ...)
# Always patch at the importing module's namespace.
```

---

## No Analog Found

All files have reasonable analogs. The following capabilities are new to the codebase and rely on RESEARCH.md patterns rather than existing code:

| Capability | File | Reason |
|------------|------|--------|
| WinRT `DeviceInformation.find_all_async()` | `src/monitor/bt_backend.py` | No WinRT enumeration in codebase yet; use RESEARCH Pattern 1 |
| BLE GATT read via BleakClient | `src/monitor/bt_backend.py` | No bleak usage in codebase yet; use RESEARCH Pattern 2 |
| Three-tier resolve chain | `src/monitor/bt_backend.py` | New composition; use RESEARCH Pattern 4 |
| QListWidget device list | `src/ui/devices_page.py` | No list widget in codebase; use standard PySide6 `QListWidget` |

---

## Metadata

**Analog search scope:** `src/` (all Python files), `tests/` (all Python files)
**Files scanned:** 28 source + test files
**Pattern extraction date:** 2026-06-05

**Critical architecture constraints for planner to enforce:**
1. `sys.coinit_flags = 0` is already at line 1 of `__main__.py` — do NOT move or add `allow_sta()`.
2. `BleakClient` coroutines MUST run on the asyncio bg thread via `run_coroutine_threadsafe` — never from a Qt slot via `asyncio.run()`.
3. All `bt_backend.py` functions are `async def` — they are called from `MonitorService` coroutines on the bg loop, never directly from Qt.
4. `DevicesPage` receives `service` and `loop` as constructor arguments — it does not own or start the event loop.
5. The `_ui_queue` bridge is the only cross-thread data path; any new BT event type must go through it.
