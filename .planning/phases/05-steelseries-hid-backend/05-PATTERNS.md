# Phase 5: SteelSeries HID Backend - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 6 (4 production files + 2 test files)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/steelseries/__init__.py` | package marker | — | `src/hidpp/__init__.py` (implicit) | exact (empty file) |
| `src/steelseries/driver.py` | service (HID backend) | request-response | `src/hidpp/receiver.py` + `src/hidpp/features.py` | exact (same role, same HID data flow) |
| `src/monitor/state.py` | model / registry | CRUD | itself (add DEVICE_PROBES alongside KNOWN_DEVICES) | self-modification |
| `src/monitor/service.py` | service (polling engine) | request-response | itself (modify poll_once dispatch + smoothing guard) | self-modification |
| `tests/test_steelseries_driver.py` | test | — | `tests/test_receiver.py` + `tests/test_features.py` | exact (same test patterns) |
| `tests/test_service.py` (update) | test | — | itself (add new test methods to existing classes) | self-modification |

---

## Pattern Assignments

### `src/steelseries/__init__.py` (package marker)

**Analog:** Implicit — every `src/` subpackage has an empty `__init__.py`.

This file is empty. Create it with no content to make `steelseries` a package importable as `from steelseries.driver import ...`.

---

### `src/steelseries/driver.py` (service, request-response)

**Primary analog:** `src/hidpp/receiver.py`
**Secondary analog:** `src/hidpp/features.py`

#### Imports pattern — `src/hidpp/receiver.py` lines 1–13 and `src/hidpp/features.py` lines 1–11

```python
# receiver.py: only hid + docstring, no other imports
import hid

# features.py: dataclass + protocol layer
from dataclasses import dataclass
from hidpp.protocol import send_and_recv, HIDppError
```

For `driver.py`, the pattern is:
```python
import hid
from hidpp.features import BatteryResult
```
No other imports needed. `BatteryResult` is defined in `hidpp/features.py` and is the shared return type contract (D-03).

#### Constants pattern — `src/hidpp/receiver.py` lines 18–28

```python
LOGITECH_VID = 0x046D
VENDOR_USAGE_PAGE = 0xFF43   # → SteelSeries equivalent: SS_VID, SS_AEROX5_PID, SS_VENDOR_INTERFACE
DEVICE_IDX = 0xFF
```

SteelSeries constants follow the same naming style. Key difference: SteelSeries filters by `interface_number`, not `usage_page`:

```python
SS_VID = 0x1038
SS_AEROX5_PID = 0x1852
SS_VENDOR_INTERFACE = 3     # interface_number, NOT usage_page
SS_DEVICE_IDX = 0x00        # placeholder for (vid, pid, dev_idx) key; unused in command
```

#### find_dongle() pattern — mirrors `src/hidpp/receiver.py` lines 35–68 (`find_receiver`)

```python
def find_receiver(vid: int = LOGITECH_VID, verbose: bool = True) -> list[dict]:
    if verbose:
        print(f"=== All Logitech (0x{vid:04X}) HID interfaces ===")
    all_devices = hid.enumerate(vid, 0)

    if not all_devices:
        if verbose:
            print("  (no devices found for this VID)")
        return []

    for info in all_devices:
        if verbose:
            path = info["path"]
            path_str = path.decode("utf-8", errors="replace") if isinstance(path, bytes) else repr(path)
            print(
                f"  PID=0x{info['product_id']:04X}  "
                f"usage_page=0x{info['usage_page']:04X}  "
                f"usage=0x{info['usage']:04X}  "
                f"path={path_str}  "
                ...
            )

    vendor_interfaces = [d for d in all_devices if d["usage_page"] == VENDOR_USAGE_PAGE]
    return vendor_interfaces
```

`find_dongle()` is a near-copy with two differences:
1. Filter criterion: `d["interface_number"] == SS_VENDOR_INTERFACE` instead of `d["usage_page"] == VENDOR_USAGE_PAGE`.
2. `verbose=False` as default (RESEARCH.md recommendation; `find_receiver` uses `verbose=True`).

#### open_dongle() pattern — exact copy of `src/hidpp/receiver.py` lines 71–81 (`open_receiver`)

```python
def open_receiver(info: dict):
    device = hid.device()
    device.open_path(info["path"])
    return device
```

`open_dongle()` is a character-for-character copy, renaming only the function.

#### ss_battery_probe() pattern — mirrors `src/hidpp/features.py` lines 40–60 (`battery_probe_chain`)

```python
def battery_probe_chain(device, device_idx: int) -> "BatteryResult | None":
    cmd = [0x11, device_idx, 0x06, 0x0D] + [0x00] * 16
    try:
        result = send_and_recv(device, cmd, min_len=7)
    except (HIDppError, OSError):
        return None
    if result is None:
        return None
    voltage_mv = (result[4] << 8) | result[5]
    charging = result[6] == 0x03
    return BatteryResult(
        percent=voltage_to_percent(voltage_mv),
        voltage_mv=voltage_mv,
        charging=charging,
        feature_used="0x06/0x0D",
    )
```

`ss_battery_probe()` mirrors the signature `(device, dev_idx) -> BatteryResult | None` and the `BatteryResult(...)` construction pattern. Key differences:
- No try/except around the HID calls (warmup reads and write do not raise on SteelSeries; failures manifest as empty `resp`).
- Three warmup `device.read(64, timeout_ms=100)` calls before `device.write(...)`.
- Response filtered by `resp[0] == 0xD2` (skip `0x61` async notification packets).
- `voltage_mv=0` (SteelSeries doesn't report voltage).
- `feature_used="0xD2"` (string constant naming the command byte, same convention as `"0x06/0x0D"`).

---

### `src/monitor/state.py` (model, add DEVICE_PROBES)

**Analog:** Itself — existing `KNOWN_DEVICES` dict defines the pattern; `DEVICE_PROBES` is placed immediately after.

#### Existing KNOWN_DEVICES pattern — `src/monitor/state.py` lines 49–51

```python
KNOWN_DEVICES: dict[tuple[int, int], str] = {
    (0x046D, 0x0ABA): "G Pro X Wireless",
}
```

#### New DEVICE_PROBES — placed directly after KNOWN_DEVICES (line 52 onward)

Pattern to add:
```python
# Lazy imports to avoid circular import: state ← service ← state.
# Import at module level is safe because features/driver don't import monitor.
from hidpp.features import battery_probe_chain
from steelseries.driver import ss_battery_probe

KNOWN_DEVICES: dict[tuple[int, int], str] = {
    (0x046D, 0x0ABA): "G Pro X Wireless",
    (0x1038, 0x1852): "Aerox 5 Wireless",       # Phase 5
}

# Probe function registry: (vid, pid) → (device, dev_idx) → BatteryResult | None
DEVICE_PROBES: dict[tuple[int, int], callable] = {
    (0x046D, 0x0ABA): battery_probe_chain,
    (0x1038, 0x1852): ss_battery_probe,          # Phase 5
}
```

Note: `DEVICE_PROBES` type annotation uses `callable` (lowercase), matching the project's existing style (no `typing.Callable` imports in `state.py`).

---

### `src/monitor/service.py` (service, modify poll_once + smoothing guard)

**Analog:** Itself — two targeted surgical changes to `poll_once()`.

#### Change 1: Import update — lines 22–28 (current)

```python
# CURRENT (lines 22-27):
from hidpp.receiver import (
    DEVICE_IDX,
    find_receiver,
    open_receiver,
)
from hidpp.features import battery_probe_chain, voltage_to_percent
```

Phase 5 adds import of `DEVICE_PROBES` from `monitor.state`, and removes the direct `battery_probe_chain` import (it will be accessed via `DEVICE_PROBES`):

```python
# AFTER Phase 5:
from hidpp.receiver import (
    DEVICE_IDX,
    find_receiver,
    open_receiver,
)
from hidpp.features import voltage_to_percent
from monitor.state import KNOWN_DEVICES, DEVICE_PROBES, DeviceState, DeviceStatus
```

`battery_probe_chain` is removed from the import as it is now registered in `DEVICE_PROBES`. The `monitor.state` import line is already present (line 31); it needs `DEVICE_PROBES` added to it.

#### Change 2: poll_once() dispatch — lines 208–240 (current)

Current hardcoded call at line 210:
```python
result = battery_probe_chain(handle, dev_idx)
```

Replace with dispatch via registry:
```python
probe_fn = DEVICE_PROBES.get((vid, pid))
if probe_fn is None:
    continue
result = probe_fn(handle, dev_idx)
```

#### Change 3: Voltage smoothing guard — lines 220–222 (current)

Current (no guard):
```python
hist = self._voltage_history.setdefault(key, deque(maxlen=_VOLTAGE_WINDOW))
hist.append(result.voltage_mv)
smoothed_percent = voltage_to_percent(round(sum(hist) / len(hist)))
```

After Phase 5 (add `voltage_mv == 0` guard, D-03):
```python
if result.voltage_mv != 0:
    hist = self._voltage_history.setdefault(key, deque(maxlen=_VOLTAGE_WINDOW))
    hist.append(result.voltage_mv)
    smoothed_percent = voltage_to_percent(round(sum(hist) / len(hist)))
else:
    # SteelSeries reports voltage_mv=0; use percent directly, no smoothing
    smoothed_percent = result.percent
```

This guard is the entire extent of the smoothing change — no new data structures.

#### Handle management for SteelSeries (open-per-poll constraint)

Because the SteelSeries dongle responds to a battery command exactly once per device open, `poll_once()` must open a fresh handle for SteelSeries entries before calling `ss_battery_probe`, then close it after. The planner must choose between two strategies:

**Strategy A (recommended in RESEARCH.md):** `discover()` adds SteelSeries to `self._open` with a handle. At the start of each `poll_once()` iteration for a SteelSeries device, close the old handle, open a fresh one via `open_dongle(info)`, call `ss_battery_probe`, then store the new handle (or close it and remove from `_open` to rely on next `discover()`). This requires `discover()` to also store the `info` dict alongside or instead of the handle for SteelSeries devices so `poll_once()` can re-open.

**Strategy B:** `discover()` does not add SteelSeries to `self._open`. Instead, `poll_once()` enumerates SteelSeries dongles directly (calls `find_dongle()`) on each cycle. The planner will decide; both strategies are valid. Strategy A better reuses the existing `_open` bookkeeping and the unplug detection in `discover()`.

The pattern for differentiating SteelSeries from Logitech inside `poll_once()` is `(vid, pid) in DEVICE_PROBES` with a per-device open/close block — same `(vid, pid)` check already used in `discover()` at lines 149 and 169.

---

### `tests/test_steelseries_driver.py` (new test file)

**Primary analog:** `tests/test_receiver.py` (structure, mocking, `patch("hid.enumerate")` pattern)
**Secondary analog:** `tests/test_features.py` (probe function return type assertions)

#### Test file header pattern — `tests/test_receiver.py` lines 1–4

```python
"""Unit tests for hidpp.receiver."""

from unittest.mock import MagicMock, patch
from hidpp.receiver import find_receiver, open_receiver, discover_device_index, DEVICE_IDX
```

`test_steelseries_driver.py` follows the same structure:
```python
"""Unit tests for steelseries.driver."""

from unittest.mock import MagicMock, patch
from steelseries.driver import find_dongle, open_dongle, ss_battery_probe, SS_VENDOR_INTERFACE
```

#### find_dongle filter test pattern — `tests/test_receiver.py` lines 7–19

```python
def test_find_receiver_filters_ff43_only():
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            {"usage_page": 0xFF00, "product_id": 0xC547, "path": b"/dev/hid0",
             "usage": 0x01, "manufacturer_string": "", "product_string": ""},
            {"usage_page": 0xFF43, "product_id": 0x0ABA, "path": b"/dev/hid1",
             "usage": 0x01, "manufacturer_string": "", "product_string": ""},
        ]
        result = find_receiver()
    assert len(result) == 1
    assert result[0]["usage_page"] == 0xFF43
```

Equivalent for `find_dongle` — filter criterion is `interface_number == 3`, not `usage_page`:
```python
def test_find_dongle_filters_interface_3():
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [
            {"interface_number": 0, "product_id": 0x1852, "path": b"/dev/hid0",
             "usage_page": 0x0001, "vendor_id": 0x1038},
            {"interface_number": 3, "product_id": 0x1852, "path": b"/dev/hid1",
             "usage_page": 0xFFC0, "vendor_id": 0x1038},
        ]
        result = find_dongle()
    assert len(result) == 1
    assert result[0]["interface_number"] == 3
```

#### open_dongle test pattern — `tests/test_receiver.py` lines 34–40

```python
def test_open_receiver_calls_open_path():
    with patch("hid.device") as mock_dev_class:
        mock_dev = MagicMock()
        mock_dev_class.return_value = mock_dev
        open_receiver({"path": b"/dev/hidraw0"})
    mock_dev.open_path.assert_called_once_with(b"/dev/hidraw0")
```

Exact same pattern for `open_dongle`.

#### ss_battery_probe test pattern — `tests/test_features.py` lines 40–81 (mock_hid fixture)

```python
def test_timeout_returns_none(mock_hid):
    mock_hid.read.return_value = []
    result = battery_probe_chain(mock_hid, 0xFF)
    assert result is None
```

SteelSeries equivalent uses same `mock_hid` fixture from `conftest.py`. The `conftest.py` fixture (`tests/conftest.py` lines 4–9) is:
```python
@pytest.fixture
def mock_hid(mocker):
    device = mocker.MagicMock()
    device.write.return_value = None
    return device
```

For `ss_battery_probe`, warmup reads must return empty lists, and the response packet is `[0xD2, level_byte, ...]`:
```python
def test_ss_battery_probe_parses_level_byte(mock_hid):
    # raw=5 → pct=20, not charging
    mock_hid.read.side_effect = (
        [[], [], []]                     # 3 warmup reads → empty
        + [[0xD2, 0x05] + [0x00] * 62]  # battery response
    )
    result = ss_battery_probe(mock_hid, 0x00)
    assert result.percent == 20
    assert result.charging is False
    assert result.voltage_mv == 0
    assert result.feature_used == "0xD2"

def test_ss_battery_probe_returns_none_on_timeout(mock_hid):
    # All reads empty → no 0xD2 response
    mock_hid.read.return_value = []
    result = ss_battery_probe(mock_hid, 0x00)
    assert result is None
```

#### Verbose/silent test — `tests/test_receiver.py` lines 56–65

```python
def test_find_receiver_silent_when_not_verbose(capsys):
    with patch("hid.enumerate") as mock_enum:
        mock_enum.return_value = [...]
        find_receiver(verbose=False)
    captured = capsys.readouterr()
    assert captured.out == ""
```

Same pattern applies to `test_find_dongle_silent_when_not_verbose`.

---

### `tests/test_service.py` (update existing file)

**Analog:** Itself — new test methods added to existing `TestPollOnce` and `TestDiscover` classes.

#### Existing dispatch patch pattern — `tests/test_service.py` lines 168–171

```python
mocker.patch(
    "monitor.service.battery_probe_chain",
    return_value=BatteryResult(percent=75, voltage_mv=3990, charging=False, feature_used="0x06/0x0D"),
)
```

After Phase 5, `battery_probe_chain` is accessed via `DEVICE_PROBES`, so new tests patch `monitor.service.DEVICE_PROBES`:
```python
mocker.patch.dict(
    "monitor.service.DEVICE_PROBES",
    {(GPRO_VID, GPRO_PID): lambda handle, idx: BatteryResult(
        percent=75, voltage_mv=3990, charging=False, feature_used="0x06/0x0D"
    )},
)
```

Or more concisely using a `MagicMock` for the probe function:
```python
mock_probe = mocker.MagicMock(return_value=BatteryResult(...))
mocker.patch.dict("monitor.service.DEVICE_PROBES", {(GPRO_VID, GPRO_PID): mock_probe})
```

Note: Existing tests that patch `"monitor.service.battery_probe_chain"` directly will break after Phase 5's dispatch change. They must be updated to patch `DEVICE_PROBES` instead.

#### New smoothing guard test — added to `TestPollOnce`

```python
SS_VID, SS_PID = 0x1038, 0x1852

def test_zero_voltage_skips_smoothing(self, mocker):
    """SteelSeries (voltage_mv=0) uses result.percent directly; no smoothing deque update."""
    service, _, ui_queue, registry = self._setup_with_open_device(mocker)
    # Inject SteelSeries key alongside G Pro X
    ss_key = (SS_VID, SS_PID, 0x00)
    service._open[ss_key] = mocker.MagicMock()
    # ... pre-populate registry with SS DeviceState ...

    mocker.patch.dict("monitor.service.DEVICE_PROBES", {
        (GPRO_VID, GPRO_PID): lambda h, i: BatteryResult(75, 3990, False, "0x06/0x0D"),
        (SS_VID, SS_PID): lambda h, i: BatteryResult(20, 0, False, "0xD2"),
    })
    asyncio.run(service.poll_once())

    ss_state = registry.get(ss_key)
    assert ss_state.percent == 20
    # Voltage history must NOT have been updated for the SS key
    assert ss_key not in service._voltage_history
```

---

## Shared Patterns

### HID open_path invariant
**Source:** `src/hidpp/receiver.py` lines 71–81 (`open_receiver`)
**Apply to:** `src/steelseries/driver.py` (`open_dongle`), any future device backend

```python
def open_receiver(info: dict):
    device = hid.device()
    device.open_path(info["path"])   # NEVER hid.open(vid, pid)
    return device
```

### BatteryResult return contract
**Source:** `src/hidpp/features.py` lines 18–22 (dataclass definition)
**Apply to:** `src/steelseries/driver.py` (`ss_battery_probe` return value)

```python
@dataclass
class BatteryResult:
    percent: int
    voltage_mv: int    # Set to 0 for SteelSeries (no voltage sensor)
    charging: bool
    feature_used: str  # Convention: hex string, e.g. "0xD2"
```

### Probe function None-sentinel contract
**Source:** `src/hidpp/features.py` lines 40–60 (`battery_probe_chain`)
**Apply to:** `src/steelseries/driver.py` (`ss_battery_probe`)

Return `None` when the device is offline or unreachable. The existing `poll_once()` path `if result is None or result.percent == 0:` handles both without new code (D-07).

### Verbose flag pattern
**Source:** `src/hidpp/receiver.py` lines 35–68 (`find_receiver`)
**Apply to:** `src/steelseries/driver.py` (`find_dongle`)

```python
def find_receiver(vid: int = LOGITECH_VID, verbose: bool = True) -> list[dict]:
    if verbose:
        print(...)
    ...
```

`find_dongle` uses `verbose=False` as default (polling must be silent, WR-03). The conditional print block structure is identical.

### Test mock_hid fixture
**Source:** `tests/conftest.py` lines 4–9
**Apply to:** `tests/test_steelseries_driver.py`

```python
@pytest.fixture
def mock_hid(mocker):
    device = mocker.MagicMock()
    device.write.return_value = None
    return device
```

Reuse without modification. `ss_battery_probe` tests configure `device.read.side_effect` to return warmup empties followed by a response packet.

### No-PySide6 / no-hid.open safety checks
**Source:** `tests/test_service.py` lines 249–277 (`TestSafetyInvariants`)
**Apply to:** Consider adding equivalent AST check to `tests/test_steelseries_driver.py`

The existing checks in `test_service.py` walk the AST of `service.py` to assert no `hid.open()` call exists. The same check pattern can be applied to `steelseries/driver.py`.

---

## No Analog Found

No files in Phase 5 lack an analog. Every new file has a close match in the codebase.

---

## Metadata

**Analog search scope:** `src/hidpp/`, `src/monitor/`, `tests/`
**Files scanned:** `receiver.py`, `features.py`, `state.py`, `service.py`, `conftest.py`, `test_receiver.py`, `test_features.py`, `test_service.py`
**Pattern extraction date:** 2026-06-04
