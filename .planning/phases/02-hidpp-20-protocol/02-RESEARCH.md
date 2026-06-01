# Phase 2: HID++ 2.0 Protocol — Research

**Researched:** 2026-06-01
**Domain:** HID++ 2.0 over USB receiver — feature discovery, battery reading, offline handling
**Confidence:** HIGH (protocol byte layouts from kernel source + LKML patches), MEDIUM (Python wiring patterns from Solaar), LOW (G Pro X exact feature variant — hardware-specific, requires runtime probe)

---

## Summary

Phase 2 implements the HID++ 2.0 protocol layer on top of the Phase 1 HID open-path foundation. The goal is to read a real battery percentage and charging status from the Logitech G Pro X Wireless mouse through its LIGHTSPEED USB receiver.

The protocol is well-documented across three authoritative sources: the Logitech HID++ 2.0 draft specification, the Linux kernel driver `hid-logitech-hidpp.c`, and LKML patches introducing feature 0x1004. All message byte layouts are confirmed from these sources. Three battery feature variants exist (0x1000, 0x1001, 0x1004) with incompatible response formats; the correct one must be probed at runtime in priority order. Feature indices are firmware-assigned and discovered at runtime via the Root feature (always at index 0). Device index for the wireless mouse (0x01–0x0E) is distinct from the receiver index (0xFF) and must be discovered by probing.

The primary implementation risk is which battery feature the G Pro X Wireless firmware implements — unknown until hardware test. The probe chain handles all variants, so this is not a blocking risk, but it means the exact response format exercised cannot be confirmed until test time. Error code 0x05 (`LOGITECH_INTERNAL`) is the expected response when the device is off; it must be caught and converted to an OFFLINE state without raising.

**Primary recommendation:** Build three modules — `src/hidpp/protocol.py` (message construction and parsing), `src/hidpp/features.py` (feature constants and battery probe chain), `src/hidpp/receiver.py` (device discovery and open-path). Wire them into a standalone `src/hidpp/query_battery.py` script that prints battery to stdout. No UI yet.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HID++ message construction | Background thread (asyncio) | — | All HID I/O must be off the Qt main thread (architecture invariant) |
| Feature index discovery | Background thread | — | Blocking HID read; must not touch main thread |
| Battery probe chain | Background thread | — | Three blocking read/write cycles per probe attempt |
| Device index scanning | Background thread | — | Blocking reads; called once at startup per receiver |
| Offline state detection | Background thread | — | Error classification; result pushed to queue for UI |
| Battery result surface | queue.Queue | Qt main thread reads | Cross-thread boundary via queue per architecture invariant |

---

## Standard Stack

Phase 2 adds no new dependencies. Everything needed is already in `requirements.txt`.

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `hidapi` | 0.15.0 | HID device open, read, write | Installed in Phase 1; identical API to `hid==1.0.9`; no DLL required |

### New Test Dependencies

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 9.0.3 | Test runner | Unit tests for protocol message construction and response parsing |
| `pytest-mock` | 3.15.1 | Mock `hid.device` | Simulate offline (empty reads) and error responses without hardware |

**Installation (test deps only):**
```bash
pip install pytest==9.0.3 pytest-mock==3.15.1
```

**Version verification (run before finalizing):**
```
npm view is N/A — Python project
pip index versions hidapi   → 0.15.0 (installed, confirmed Phase 1)
pip index versions pytest   → 9.0.3 [ASSUMED from PyPI JSON]
pip index versions pytest-mock → 3.15.1 [ASSUMED from PyPI JSON]
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pytest-mock` | `unittest.mock` directly | pytest-mock is thinner wrapper; `mocker` fixture cleans up automatically. Both work; pytest-mock reduces boilerplate. |
| Manual probe chain | Solaar as library | Solaar has no stable public API and pulls in many dependencies. Implementing directly is cleaner. |

---

## Package Legitimacy Audit

> slopcheck could not be installed in this environment (auto mode denied the pip install slopcheck command). All packages below are marked `[ASSUMED]` per graceful degradation protocol. The planner must gate each new install behind a `checkpoint:human-verify` task.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `hidapi` | PyPI | ~5 yrs (2020) | N/A reported by PyPI | github.com/trezor/cython-hidapi | [ASSUMED] | Approved — Trezor-maintained, known project |
| `pytest` | PyPI | ~16 yrs (2010) | Very high | github.com/pytest-dev/pytest | [ASSUMED] | Approved — standard test framework |
| `pytest-mock` | PyPI | ~11 yrs (2014) | Very high | github.com/pytest-dev/pytest-mock | [ASSUMED] | Approved — official pytest-dev project |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**slopcheck availability:** Unavailable — all packages tagged [ASSUMED]. Planner must add `checkpoint:human-verify` before install tasks for `pytest` and `pytest-mock`.

---

## HID++ 2.0 Protocol Mechanics

### Message Byte Layout

**Short message — 7 bytes total (Report ID 0x10):** [CITED: lekensteyn.nl/files/logitech/logitech_hidpp_2.0_specification_draft_2012-06-04.pdf]

```
Byte 0: report_id   = 0x10 (short)
Byte 1: device_idx  = 0xFF (receiver) or 0x01–0x0E (wireless device)
Byte 2: feature_idx = runtime-discovered index for a feature ID
Byte 3: func_swid   = upper nibble: function number (0–15)
                      lower nibble: software ID (1–15; use 0x01 for all our calls)
Bytes 4–6: parameters (3 bytes; fill unused with 0x00)
```

**Long message — 20 bytes total (Report ID 0x11):** [CITED: lekensteyn.nl/files/logitech/logitech_hidpp_2.0_specification_draft_2012-06-04.pdf]

```
Byte 0:    report_id   = 0x11 (long)
Byte 1:    device_idx
Byte 2:    feature_idx
Byte 3:    func_swid
Bytes 4–19: parameters (16 bytes; fill unused with 0x00)
```

**Error message — same size as request, indicated by Report ID:** [CITED: linux/drivers/hid/hid-logitech-hidpp.c]

```
Byte 0: report_id   = 0x10 or 0x11 (matches request)
Byte 1: device_idx  (echo of request)
Byte 2: 0xFF        (HIDPP20_ERROR sentinel — this is feature_idx position)
Byte 3: feature_idx (echo — which feature the error came from)
Byte 4: func_swid   (echo)
Byte 5: error_code  (see table below)
Bytes 6+: 0x00
```

Detection: `response[2] == 0xFF` signals an error response. [CITED: linux/drivers/hid/hid-logitech-hidpp.c]

**func_swid byte construction:**

```python
func_swid = (function_number << 4) | software_id
# function_number: 0–15 (which function of this feature)
# software_id: 1–15 (tag for correlating responses; use 0x01)
```

### Error Code Table [CITED: spinics.net/lists/linux-input/msg82674.html — PATCH: Add constants for HID++ 2.0 error codes]

| Code | Constant | Meaning in PeriphWatcher Context |
|------|----------|----------------------------------|
| 0x00 | NO_ERROR | Success |
| 0x01 | UNKNOWN | Unknown internal error |
| 0x02 | INVALID_ARGS | Wrong feature ID or function number — usually means feature absent or wrong variant |
| 0x03 | OUT_OF_RANGE | Parameter out of range |
| 0x04 | HW_ERROR | Hardware error on device side |
| 0x05 | LOGITECH_INTERNAL | **Device offline / unreachable** — receiver accepted request but mouse is off or out of range |
| 0x06 | INVALID_FEATURE_INDEX | Queried a feature index that no feature occupies |
| 0x07 | INVALID_FUNCTION_ID | Wrong function number for the feature |
| 0x08 | BUSY | Device temporarily busy — retry after short delay |
| 0x09 | UNSUPPORTED | Feature exists but function is not implemented on this device |

**Critical:** Error 0x05 (`LOGITECH_INTERNAL`) is the expected response when the wireless mouse is turned off. Treat this as OFFLINE, not as a crash condition. [CITED: github.com/pwr-Solaar/Solaar — issues/2600]

---

## Feature Discovery via Root Feature 0x0000

### Why Runtime Discovery is Mandatory

Feature indices are assigned by device firmware at manufacturing time. Two mice with identical VID/PID on different firmware versions may have the same feature at different indices. Hardcoding breaks on firmware updates. [CITED: lekensteyn.nl HID++ 2.0 draft spec — architecture invariant already locked in STATE.md]

### Root Feature Location

The Root feature (feature ID 0x0000) is **always at feature index 0x00**. This is the only hardcoded index — everything else is discovered through it. [CITED: linux/drivers/hid/hid-logitech-hidpp.c]

### GetFeature Request (function 0, feature index 0x00)

```python
# Request: discover what runtime index feature 0x1004 lives at
# func_swid = (0 << 4) | 0x01 = 0x01   (function 0, software_id 1)
msg = [
    0x10,        # report_id: short message
    device_idx,  # 0x01 (or whichever index the mouse is on)
    0x00,        # feature_idx: Root feature is always at 0
    0x01,        # func_swid: function 0, SW ID 1
    (feature_id >> 8) & 0xFF,   # feature ID high byte (e.g., 0x10 for 0x1004)
    feature_id & 0xFF,           # feature ID low byte  (e.g., 0x04 for 0x1004)
    0x00,        # pad
]
# Write: prefix with 0x00 report ID for hidapi (total 8 bytes written)
device.write([0x00] + msg)
response = device.read(16, timeout_ms=100)
```

### GetFeature Response Parsing [CITED: PixlOne/logiops wiki HIDPP 2.0 — Function 0 Get Feature returns Byte 0: Feature Index]

```python
if not response:
    # timeout — device offline
    return None

if response[2] == 0xFF:
    # error response
    error_code = response[5]
    # error 0x05 = device off; error 0x06 = invalid feature index
    raise HIDppError(error_code)

# response[0] = report_id (echo)
# response[1] = device_idx (echo)
# response[2] = feature_idx (echo, should be 0x00 for root)
# response[3] = func_swid (echo)
# response[4] = discovered feature index  ← THIS IS WHAT WE WANT
# response[5] = feature flags/version (not needed for battery query)

feature_index = response[4]
if feature_index == 0x00:
    # Feature ID not supported on this device
    return None   # probe next variant
```

**Key rule:** If `response[4] == 0x00`, the feature is absent on this device. Probe the next lower-priority variant. [CITED: PITFALLS.md — Pitfall 2]

---

## Device Index Discovery

### Why 0xFF Cannot Be Used for Device Queries

`device_idx = 0xFF` addresses the USB receiver/dongle itself. Battery feature queries sent to 0xFF go to the receiver firmware, not the mouse. The receiver may return error 0x06 (invalid feature index) or respond with receiver-specific data. [CITED: PITFALLS.md — Pitfall 3]

### Wireless Device Index Range

Logitech LIGHTSPEED and Unifying receivers support device indices 0x01 through 0x0E (14 slots). In practice, a single paired mouse is almost always at index 0x01, but this MUST be discovered dynamically. [CITED: linux/drivers/hid/hid-logitech-hidpp.c — "device_index between 1 and 6"]

### Discovery Method: Root Feature Probe

The reliable method is to send a GetFeature(0x0000) request (asking for the Root feature, which is always supported) to each index in order. A valid response confirms a live device at that index.

```python
def find_device_index(device) -> int | None:
    """Probe indices 0x01–0x06 until one responds to a Root feature query."""
    for idx in range(0x01, 0x07):  # 0x01 through 0x06 inclusive
        msg = [0x00, 0x10, idx, 0x00, 0x01, 0x00, 0x00, 0x00]
        # [hidapi_prefix, report_id, device_idx, feature_idx=Root,
        #  func_swid=(fn0|sw1), featureID_hi=0x00, featureID_lo=0x00, pad]
        try:
            device.write(msg)
            response = device.read(16, timeout_ms=100)
        except OSError:
            continue
        if not response:
            continue
        if response[2] == 0xFF:
            continue  # error — no device at this index
        return idx
    return None  # no device found
```

[ASSUMED] — Index scanning up to 0x06 is the common safe range; some receivers support up to 0x0E. For G Pro X Wireless with a single-device LIGHTSPEED receiver, 0x01 will almost certainly be correct, but the probe remains required per architecture invariant.

---

## Battery Feature Variants

### Priority Order (locked in STATE.md): 0x1004 → 0x1000 → 0x1001

### Feature 0x1004 — UNIFIED_BATTERY (Preferred)

**Why preferred:** Most recent standard; supports both true percentage and categorical levels; explicit charging status enum. Introduced post-2019. [CITED: yhbt.net/lore — LKML patch "add support for Unified Battery (1004) feature"]

#### Step 1: GetCapabilities (function 0)

```python
# func_swid = (0 << 4) | 0x01 = 0x01
request = [0x00, 0x10, device_idx, feature_idx_1004, 0x01, 0x00, 0x00, 0x00]
device.write(request)
response = device.read(16, timeout_ms=100)
```

Response parsing: [CITED: yhbt.net/lore — LKML patch 0x1004]
```
response[4]: supported_levels bitmask (which of critical/low/good/full the device reports)
response[5]: feature_flags
  bit 0: FLAG_RECHARGEABLE  (device can charge)
  bit 1: FLAG_STATE_OF_CHARGE  ← if set, GetStatus returns true 0–100% in byte[4]
```

If `response[5] & 0x02 == 0`: device implements 0x1004 but only returns level categories, not true %. Map categories to representative values (see Pitfall 8 below).

#### Step 2: GetStatus (function 1)

```python
# func_swid = (1 << 4) | 0x01 = 0x11
request = [0x00, 0x10, device_idx, feature_idx_1004, 0x11, 0x00, 0x00, 0x00]
device.write(request)
response = device.read(16, timeout_ms=100)
```

Response parsing: [CITED: yhbt.net/lore — LKML patch 0x1004]
```
response[4]: state_of_charge  (0–100 %; valid only if FLAG_STATE_OF_CHARGE was set)
response[5]: battery_level flags
  bit 0: CRITICAL  (maps to ~0–5%)
  bit 1: LOW       (maps to ~6–30%)
  bit 2: GOOD      (maps to ~31–89%)
  bit 3: FULL      (maps to 100%)
response[6]: charging_status
  0 = DISCHARGING
  1 = CHARGING (standard)
  2 = CHARGING_SLOW
  3 = CHARGE_COMPLETE (full)
  4 = ERROR_CHARGING
response[7]: external_power (0=no external power, 1=external power connected)
```

**Level-only mapping (when SOC not available):**
```python
LEVEL_MAP = {0x01: 5, 0x02: 20, 0x04: 70, 0x08: 100}
# Pick the highest set bit
```

### Feature 0x1000 — BATTERY_LEVEL_STATUS (Fallback 1)

Older standard. Returns percentage directly but reports 0% while charging. [CITED: linux/drivers/hid/hid-logitech-hidpp.c — CMD_BATTERY_LEVEL_STATUS_GET_BATTERY_LEVEL]

#### GetBatteryLevelStatus (function 0)

```python
# func_swid = (0 << 4) | 0x01 = 0x01
request = [0x00, 0x10, device_idx, feature_idx_1000, 0x01, 0x00, 0x00, 0x00]
device.write(request)
response = device.read(16, timeout_ms=100)
```

Response: [CITED: linux/drivers/hid/hid-logitech-hidpp.c + libratbag DeepWiki]
```
response[4]: battery_level (0–100 %; returns 0 when charging — do not display 0%)
response[5]: next_level (next level that will be reported; 0 if charging or at lowest)
response[6]: battery_status
  0 = DISCHARGING
  1 = RECHARGING
  2 = CHARGE_COMPLETE
  3 = CHARGE_FAILED (error)
```

**Charging detection:** if `response[6] == 1` → charging = True; display battery as "Charging" rather than "0%" when `response[4] == 0`.

### Feature 0x1001 — BATTERY_VOLTAGE (Fallback 2)

Used by post-2019 mice that use voltage reporting (MX Master 3, G Pro X Superlight 2). Returns millivolts; percentage must be calculated via LiPo curve. [CITED: patchwork.kernel.org — "hid-logitech-hidpp: read battery voltage from newer devices"]

#### GetBatteryVoltage (function 0)

```python
# func_swid = (0 << 4) | 0x01 = 0x01
request = [0x00, 0x10, device_idx, feature_idx_1001, 0x01, 0x00, 0x00, 0x00]
device.write(request)
response = device.read(16, timeout_ms=100)
```

Response: [CITED: patchwork.kernel.org — v6 patch]
```
response[4]: voltage MSB  (big-endian 16-bit mV)
response[5]: voltage LSB
response[6]: status bitset
  bits 5-7 = 000 (0x00): Charging
  bits 5-7 = 001 (0x20): Full
  bits 5-7 = 010 (0x40): Discharging
  bits 5-7 = 111 (0xe0): Not charging
  bit 3: Fast charge active
  bit 4: Trickle charge active
  bit 5: Critical battery level
```

**Voltage to percentage (LiPo curve):** [ASSUMED — standard LiPo, accuracy ±5–10%]
```python
def voltage_to_percent(mv: int) -> int:
    # Standard LiPo cell: 3000mV = 0%, 3700mV = 50%, 4200mV = 100%
    if mv >= 4200: return 100
    if mv >= 3700: return 50 + int((mv - 3700) / 500 * 50)
    if mv >= 3000: return int((mv - 3000) / 700 * 50)
    return 0
```

**Charging detection:** `(response[6] & 0xE0) in (0x00, 0x20)` → charging or full.

---

## hidapi Write Prefix Rule

The `hidapi` Python package requires the write buffer to include the HID report ID as the first byte. For a 7-byte HID++ short message (report ID 0x10), the actual `device.write()` call sends 8 bytes: `[0x10] + payload[1:]` where `payload[0]` is already 0x10. In practice, write the full message including the report ID byte: [CITED: hidapi PyPI + hid_poc.py pattern from Phase 1]

```python
# Correct — report ID is byte[0] of the write buffer
device.write([0x10, device_idx, feature_idx, func_swid, p0, p1, p2])
# hidapi adds no implicit prefix on Windows with the hid/hidapi package
```

**Note:** Phase 1 used `[0x00] + payload` (report ID 0x00 = no report). For HID++ we use the actual report IDs 0x10/0x11. Verify with the hardware that 0x10 is the correct report ID for the LIGHTSPEED receiver.

The `device.read(size, timeout_ms)` return value does NOT include the report ID byte on Windows with hidapi — `response[0]` is the first data byte after the report ID. However, confirm this empirically with the hardware since some configurations include it. [ASSUMED — hidapi Windows behavior varies by version; verify in Wave 1 hardware test]

---

## Architecture Patterns

### Recommended File Structure

```
src/
├── hidpp/
│   ├── __init__.py          # empty
│   ├── protocol.py          # message construction, parsing, error detection
│   ├── features.py          # feature ID constants, battery probe chain
│   └── receiver.py          # device open (reuses hid_poc open_path pattern), index discovery
├── query_battery.py         # standalone CLI: open receiver, probe, print to stdout
├── hid_poc.py               # Phase 1 — keep as-is, not modified
├── threading_stub.py        # Phase 1 — keep as-is, not modified
└── __main__.py              # Phase 1 — not modified in Phase 2
tests/
├── test_protocol.py         # unit tests for message construction and parsing (no hardware)
├── test_features.py         # unit tests for probe chain logic with mocked hid.device
└── conftest.py              # shared fixtures (mock_hid_device factory)
```

### System Architecture Diagram

```
query_battery.py (entry point — stdout only, no UI)
  │
  ▼
receiver.py
  enumerate(VID, PID)
    └─ filter usage_page=0xFF00  (reuse hid_poc.find_vendor_interfaces pattern)
    └─ open_path(path)
    └─ find_device_index()  ──── writes Root probe to device, reads response
  │
  ▼
features.py — battery_probe_chain(device, device_idx) → BatteryResult | None
  │
  ├─ try 0x1004: get_feature_index(device, device_idx, 0x1004)
  │   ├─ None → skip
  │   └─ idx  → get_capabilities(idx) → get_status(idx)
  │             └─ BatteryResult(percent, charging, feature="0x1004")
  │
  ├─ try 0x1000: get_feature_index(device, device_idx, 0x1000)
  │   ├─ None → skip
  │   └─ idx  → get_battery_level(idx)
  │             └─ BatteryResult(percent, charging, feature="0x1000")
  │
  └─ try 0x1001: get_feature_index(device, device_idx, 0x1001)
      ├─ None → None (device has no battery feature)
      └─ idx  → get_battery_voltage(idx)
                └─ BatteryResult(percent, charging, feature="0x1001")
  │
  ▼ on HIDppError(0x05) at any point
  return None  (device OFFLINE)
  │
  ▼
protocol.py — used by features.py for all message I/O
  build_short_msg(device_idx, feature_idx, function, params) → list[int]
  send_and_recv(device, msg, timeout_ms) → list[int] | None
  parse_error(response) → int | None  (returns error_code or None if not error)
```

### Pattern 1: HIDppError Exception for Protocol Errors

```python
# src/hidpp/protocol.py

class HIDppError(Exception):
    """Raised when the device returns a HID++ 2.0 error response."""
    def __init__(self, code: int):
        self.code = code
        super().__init__(f"HID++ error 0x{code:02X}")

ERROR_OFFLINE = 0x05      # LOGITECH_INTERNAL — device is off or out of range
ERROR_INVALID_FEATURE = 0x02  # queried feature not present / wrong args
ERROR_BUSY = 0x08         # retry after short delay

def send_and_recv(device, msg: list[int], timeout_ms: int = 100) -> list[int] | None:
    """Send a HID++ message and return the response, or None on timeout."""
    device.write(msg)
    response = device.read(20, timeout_ms=timeout_ms)
    if not response:
        return None  # timeout — device may be off; caller decides meaning
    if response[2] == 0xFF:  # error sentinel in feature_idx position
        raise HIDppError(response[5])
    return response
```

[CITED: linux/drivers/hid/hid-logitech-hidpp.c — HIDPP20_ERROR = 0xFF check]

### Pattern 2: Probe Chain with Graceful Fallback

```python
# src/hidpp/features.py

BATTERY_PROBE_ORDER = [0x1004, 0x1000, 0x1001]

def battery_probe_chain(device, device_idx: int) -> BatteryResult | None:
    for feature_id in BATTERY_PROBE_ORDER:
        try:
            idx = get_feature_index(device, device_idx, feature_id)
        except HIDppError as e:
            if e.code == ERROR_OFFLINE:
                return None   # device is off — stop probing
            continue          # error on this feature, try next
        if idx is None:
            continue          # feature not supported on this device
        try:
            if feature_id == 0x1004:
                return _read_1004(device, device_idx, idx)
            elif feature_id == 0x1000:
                return _read_1000(device, device_idx, idx)
            elif feature_id == 0x1001:
                return _read_1001(device, device_idx, idx)
        except HIDppError as e:
            if e.code == ERROR_OFFLINE:
                return None
            continue  # feature present but read failed; try next
    return None  # no battery feature found
```

### Anti-Patterns to Avoid

- **Hardcoding feature indices**: `feature_idx = 0x04` for battery — breaks on any firmware variant. Always use Root discovery. [CITED: architecture invariant]
- **Using device_idx = 0xFF for device queries**: Returns receiver data, not mouse data. [CITED: PITFALLS.md — Pitfall 3]
- **Blocking indefinitely on read**: `device.read(20)` with no timeout hangs when device is off. Always pass `timeout_ms=100` or less. [CITED: PITFALLS.md — Pitfall 4]
- **Displaying 0% when charging via 0x1000**: Feature 0x1000 explicitly returns 0 during charging. Check `status == RECHARGING` before displaying level. [CITED: PITFALLS.md — Pitfall 8]
- **Probing all features speculatively**: Do not enumerate all feature indices — only probe the three battery features needed. Newer G Pro X firmware marks some features hidden/restricted; aggressive probing returns error 5 for restricted features. [CITED: PITFALLS.md — Pitfall 11]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LiPo discharge curve (0x1001 only) | Custom voltage-to-percent formula | Standard 3-point LiPo curve (3.0V/3.7V/4.2V) | Only needed if 0x1004 and 0x1000 are absent; accuracy ±5% is fine for a battery indicator |
| HID++ message checksum | None needed | Protocol has no checksum | HID++ 2.0 has no checksum field — USB layer guarantees integrity |
| Feature caching | Complex cache invalidation | Session-scoped dict | Indices are stable for the lifetime of one receiver session; re-discover on reconnect only |

**Key insight:** HID++ 2.0 is a well-documented protocol with three implementation references (kernel, libratbag, Solaar). The protocol layer is 50–80 lines of Python; the complexity is correctness of byte positions, not algorithmic difficulty.

---

## Common Pitfalls

### Pitfall 1: report[2] == 0xFF is the Error Signal, Not report[0]

**What goes wrong:** Checking `response[0] == 0xFF` to detect errors. The error report ID is 0x10 or 0x11 (matches the request); the sentinel 0xFF appears at byte index 2 (feature_idx position).

**Why it happens:** Confusion between HID++ 1.0 (where errors use report ID 0x8F) and HID++ 2.0.

**How to avoid:** Always check `response[2] == 0xFF` for error detection in HID++ 2.0. [CITED: linux/drivers/hid/hid-logitech-hidpp.c — HIDPP20_ERROR check]

### Pitfall 2: hidapi read() Response Byte Offset

**What goes wrong:** Reading `response[4]` for the feature index discovery result, but on some Windows hidapi builds `response[0]` contains the report ID, so the actual data starts at index 1. This shifts all byte positions by 1.

**Why it happens:** hidapi on Windows includes the report ID in the read buffer differently depending on version and OS HID layer behavior. Phase 1's `hid_poc.py` already exercised this — check what `response[0]` was in the Phase 1 output.

**How to avoid:** In Wave 1 (hardware test), log the full raw response bytes. If `response[0] == 0x10` or `response[0] == 0x11`, the report ID IS included and all offsets shift +1. Adjust `RESPONSE_OFFSET = 0` vs `RESPONSE_OFFSET = 1` based on the hardware test output. [ASSUMED — requires hardware confirmation]

**Warning signs:** Feature index returned is 0x10 or 0x11 (a report ID value) rather than a small feature number like 0x03 or 0x04.

### Pitfall 3: 0x1004 GetCapabilities Must Precede GetStatus

**What goes wrong:** Calling GetStatus (fn 1) on 0x1004 without first calling GetCapabilities (fn 0) to check `FLAG_STATE_OF_CHARGE`. If the flag is not set, `response[4]` (state_of_charge) is undefined/0 even when the device is at 80%.

**Why it happens:** 0x1004 defines state_of_charge as optional. Devices that don't implement it return 0 in that byte position.

**How to avoid:** Always call GetCapabilities first. Cache the `FLAG_STATE_OF_CHARGE` bit. If not set, fall back to level-bucket mapping.

### Pitfall 4: OSError During Write on Receiver Reconnect

**What goes wrong:** The receiver is unplugged and replugged between polling cycles. The HID handle is stale — `device.write()` raises `OSError` rather than returning an error response.

**Why it happens:** Windows HID handles become invalid on device removal. The OS does not update the existing handle.

**How to avoid:** Wrap all `device.write()` and `device.read()` calls in `try/except OSError`. On `OSError`, close the handle and re-enumerate. This is Phase 3 responsibility (MonitorService); Phase 2 should catch and log without crashing.

---

## Testing Without Hardware Off

### Unit Testing (no hardware required)

Mock `hid.device` to control `read()` return values and `write()` behavior:

```python
# tests/conftest.py
import pytest

@pytest.fixture
def mock_hid(mocker):
    """Factory that returns a mock hid.device with configurable read behavior."""
    device = mocker.MagicMock()
    device.write.return_value = None  # hidapi write returns byte count; mock ignores
    return device

# tests/test_features.py
def test_offline_returns_none(mock_hid):
    """When device is off, read returns [] (timeout). probe chain must return None."""
    mock_hid.read.return_value = []  # simulate timeout
    result = battery_probe_chain(mock_hid, device_idx=0x01)
    assert result is None

def test_error_5_returns_none(mock_hid):
    """When receiver replies with error 0x05, probe chain returns None (not raise)."""
    # Error response: [0x10, 0x01, 0xFF, 0x00, 0x00, 0x05, 0x00]
    mock_hid.read.return_value = [0x10, 0x01, 0xFF, 0x00, 0x00, 0x05, 0x00]
    result = battery_probe_chain(mock_hid, device_idx=0x01)
    assert result is None

def test_feature_absent_falls_back(mock_hid):
    """If 0x1004 returns feature_index=0 (not found), probe continues to 0x1000."""
    responses = iter([
        [0x10, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00],  # 0x1004 not found (idx=0)
        [0x10, 0x01, 0x00, 0x01, 0x04, 0x00, 0x00],  # 0x1000 at index 4
        [0x10, 0x01, 0x04, 0x01, 75,   0x00, 0x00],  # 0x1000 GetBatteryLevel → 75%
    ])
    mock_hid.read.side_effect = lambda size, timeout_ms: next(responses)
    result = battery_probe_chain(mock_hid, device_idx=0x01)
    assert result.percent == 75
```

[CITED: pytest-mock docs — mocker.MagicMock pattern]

### Hardware Integration Test (Wave 1)

Phase 2 Wave 1 must include a hardware-required script `src/hidpp/query_battery.py` that:
1. Opens the receiver
2. Discovers device index
3. Runs the probe chain
4. Prints: feature used, battery %, charging status, raw response bytes

This is the only way to confirm: actual feature variant on the G Pro X Wireless, report ID offset (Pitfall 2), and that error 0x05 correctly fires when mouse is switched off mid-run.

---

## Runtime State Inventory

Step 2.5 is SKIPPED — this is a greenfield protocol implementation phase. No renames, no data migrations.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | All code | ✓ | 3.12.13 (uv-managed) | — |
| `hidapi==0.15.0` | HID I/O | Unknown (not confirmed in Bash env) | 0.15.0 per requirements.txt | Re-run `pip install hidapi==0.15.0` |
| `PySide6==6.11.1` | threading_stub.py, not Phase 2 | Unknown | 6.11.1 per requirements.txt | Not needed for Phase 2 standalone scripts |
| `pytest` | Unit tests | Not confirmed | 9.0.3 (latest) | Must install: `pip install pytest pytest-mock` |
| Logitech LIGHTSPEED dongle (VID=0x046D) | Wave 1 hardware test | Unknown | — | No fallback — hardware required for integration test |

**Missing dependencies with no fallback:**
- LIGHTSPEED dongle + G Pro X Wireless mouse — required for Wave 1 hardware integration test. Unit tests (Wave 0) run without hardware.

**Missing dependencies with fallback:**
- `pytest` + `pytest-mock` — install before Wave 0. Unit tests blocked until installed.

**Note on Bash environment:** The project runs on Windows with a uv-managed venv. The Linux Bash environment (WSL) used for research commands does not have the project venv activated. All `pip install` commands must be run in a Windows terminal inside the project venv.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — Wave 0 creates one |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HID-01 | Battery % reads from G Pro X via HID++ 2.0 | Integration (hardware) | `python src/hidpp/query_battery.py` | No — Wave 1 creates |
| BATT-01 | Battery % is an integer 0–100 | Unit | `pytest tests/test_features.py::test_percent_range -x` | No — Wave 0 creates |
| BATT-02 | Charging status is read and surfaced | Unit | `pytest tests/test_features.py::test_charging_status -x` | No — Wave 0 creates |
| (implicit) | Offline → None, no crash | Unit | `pytest tests/test_features.py::test_offline_returns_none -x` | No — Wave 0 creates |
| (implicit) | Feature absent → probe next | Unit | `pytest tests/test_features.py::test_feature_absent_falls_back -x` | No — Wave 0 creates |
| (implicit) | Message construction correct bytes | Unit | `pytest tests/test_protocol.py -x` | No — Wave 0 creates |

### Sampling Rate

- Per task commit: `pytest tests/ -x -q`
- Per wave merge: `pytest tests/ -v`
- Phase gate: `pytest tests/ -v` green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — `mock_hid` fixture (see Code Examples above)
- [ ] `tests/test_protocol.py` — covers message construction and error detection
- [ ] `tests/test_features.py` — covers probe chain, offline, fallback, charging
- [ ] `pytest.ini` — minimal config (testpaths = tests, python_files = test_*.py)
- [ ] Framework install: `pip install pytest==9.0.3 pytest-mock==3.15.1`

---

## Security Domain

HID++ 2.0 reads from a local USB device. There is no network, no user input, no auth, and no storage in Phase 2.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Partial | HID response byte bounds-check before array index (prevent IndexError on short/malformed responses) |
| V6 Cryptography | No | N/A |

### Applicable Threat Pattern

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed HID response (short buffer, unexpected bytes) | Tampering | Check `len(response) >= expected_length` before reading any byte index; return None on short response |
| Stale HID handle after receiver unplug | DoS | Catch `OSError` on all `device.write()` / `device.read()` calls |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Feature 0x1000 (all devices) | Probe chain: 0x1004 → 0x1000 → 0x1001 | ~2019 (0x1001), ~2021 (0x1004) | Must handle all three; 0x1000 alone is incomplete |
| Hardcoded device index 0x01 | Runtime discovery via Root probe | Always required | Assumption 0x01 is almost always true for LIGHTSPEED single-device receiver, but discovery is mandated |
| Blocking reads | Short timeout (100ms) + empty=offline | Best practice from kernel driver | Prevents polling loop hang when device is off |

**Deprecated:**
- Assuming feature 0x1000 is universal — post-2019 devices use 0x1001 or 0x1004
- Using `hid.open(vid, pid)` without path — opens wrong interface (Access Denied)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | G Pro X Wireless implements one of 0x1004, 0x1000, or 0x1001 | Battery Feature Variants | If device uses an undocumented feature, probe chain returns None forever. Mitigated: probe all three; log which returned None to diagnose. |
| A2 | hidapi read() on Windows does NOT include the report ID byte in response[0] | hidapi Write Prefix Rule | All response byte offsets shift +1. Confirmed by hardware test in Wave 1 via full raw byte log. |
| A3 | Device is at index 0x01 on LIGHTSPEED single-device receiver | Device Index Discovery | Discovery probe handles this; assumption only affects which index to check first. |
| A4 | 100ms timeout is sufficient for receiver-to-device round-trip | send_and_recv pattern | If timeout is too short, reads return [] (offline false positive). Increase to 200ms if hardware test shows false offline. |
| A5 | pytest 9.0.3 and pytest-mock 3.15.1 are the current PyPI versions | Package Legitimacy Audit | Version mismatch on install. Planner must add checkpoint:human-verify before install. |

---

## Open Questions

1. **Which battery feature does the G Pro X Wireless implement?**
   - What we know: 0x1004 is preferred for post-2019 devices; G Pro X Wireless released 2019
   - What's unclear: Firmware version shipped on this specific unit — unknown until hardware test
   - Recommendation: Wave 1 hardware test must log `feature_used` in BatteryResult; plan around probe chain, not a specific feature

2. **Does hidapi.read() include report ID in response[0] on Windows?**
   - What we know: Behavior varies by hidapi version and OS config; hid_poc.py Phase 1 printed `response[:8]` but no hardware was present
   - What's unclear: Whether offset adjustment is needed
   - Recommendation: Wave 1 must log raw response and confirm offset before any byte-indexed parsing is locked in

3. **Does the G Pro X Wireless LIGHTSPEED receiver support long reports (0x11)?**
   - What we know: Most LIGHTSPEED receivers support both 0x10 and 0x11
   - What's unclear: Whether short (0x10) is sufficient for all battery queries
   - Recommendation: Use short reports (0x10) throughout Phase 2; they are sufficient for battery features whose responses fit in 3–7 param bytes

---

## Sources

### Primary (HIGH confidence)
- Logitech HID++ 2.0 draft specification — lekensteyn.nl/files/logitech/logitech_hidpp_2.0_specification_draft_2012-06-04.pdf — message format, feature discovery
- Linux kernel hid-logitech-hidpp.c — github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-hidpp.c — error codes, HIDPP20_ERROR sentinel, report sizes
- LKML patch: "add support for Unified Battery (1004) feature" — yhbt.net/lore — 0x1004 response byte positions, GetCapabilities/GetStatus format
- LKML patch v6: "hid-logitech-hidpp: read battery voltage" — patchwork.kernel.org — 0x1001 response bytes, status bitset
- "Add constants for HID++ 2.0 error codes" kernel patch — spinics.net/lists/linux-input/msg82674.html — complete error code table

### Secondary (MEDIUM confidence)
- libratbag DeepWiki — deepwiki.com/libratbag/libratbag/3.2-logitech-hid++-2.0-driver — feature architecture, supported_report_types, battery status enums
- logiops wiki HIDPP 2.0 — github.com/PixlOne/logiops/wiki — GetFeature function 0 returns byte 0 = Feature Index (cross-verifies spec)
- Solaar hidpp20.py — github.com/pwr-Solaar/Solaar — Python probe pattern reference
- Solaar PITFALLS (project research) — .planning/research/PITFALLS.md — Pitfalls 2, 3, 4, 8, 11
- ARCHITECTURE.md (project research) — .planning/research/ARCHITECTURE.md — receiver addressing, polling pattern

### Tertiary (LOW confidence)
- Community reports on Solaar issues #2600, #3036 — error 5 = offline behavior in practice

---

## Metadata

**Confidence breakdown:**
- Protocol byte layouts: HIGH — confirmed from kernel source and LKML patches (primary authoritative sources)
- Feature probe chain: HIGH — well-established pattern in multiple independent implementations
- Exact G Pro X feature variant: LOW — unknown until hardware test; all three variants handled
- hidapi response offset: LOW — requires hardware test to confirm
- Python wiring patterns: MEDIUM — derived from Solaar source structure, not directly verified

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 (protocol specs are stable; no fast-moving dependencies)
