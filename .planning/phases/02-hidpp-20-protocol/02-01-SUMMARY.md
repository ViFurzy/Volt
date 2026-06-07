---
phase: 2
plan: "02-01"
subsystem: hidpp-protocol-layer
tags: [hid, hidpp, protocol, pytest, hardware-probe, logitech-headset]
dependency_graph:
  requires: [src/hid_poc.py, src/__main__.py]
  provides: [src/hidpp/protocol.py, src/hidpp/__init__.py, tests/conftest.py, tests/test_protocol.py, pytest.ini]
  affects: [src/hidpp/receiver.py, src/hidpp/features.py]
tech_stack:
  added: [pytest==9.0.3, pytest-mock==3.15.1]
  patterns: [HIDppError-exception, build_short_msg, send_and_recv]
key_files:
  created:
    - src/hidpp/__init__.py
    - src/hidpp/protocol.py
    - tests/conftest.py
    - tests/test_protocol.py
    - pytest.ini
  modified: []
decisions:
  - "Response OFFSET=1: response[0] IS the report ID (0x11 confirmed on G Pro X Wireless)"
  - "G Pro X Wireless uses 0xFF43 interface (not 0xFF00) for HID++ commands"
  - "G Pro X Wireless uses device_idx=0xFF (receiver itself, not a paired device index)"
  - "Battery command: feature 0x06 function 0x0D — NOT via HID++ 2.0 feature discovery chain"
  - "Response bytes [4:5] = voltage mV big-endian; byte[6] = charging state (0x01=idle, 0x03=charging)"
metrics:
  completed_date: "2026-06-02"
  tasks_completed: 3
  files_created: 5
  files_modified: 0
---

# Phase 2 Plan 01: HID++ Protocol Layer + pytest Bootstrap Summary

## What Was Built

Five files establishing the HID++ protocol layer and test framework:

- `src/hidpp/__init__.py` — package marker with architecture invariant documentation
- `src/hidpp/protocol.py` — `HIDppError`, `build_short_msg`, `send_and_recv`, constants
- `tests/conftest.py` — `mock_hid` fixture for unit tests
- `tests/test_protocol.py` — 8 unit tests covering message construction and error parsing
- `pytest.ini` — test runner config (`testpaths=tests`, `pythonpath=src`)

`protocol.py` exports:
- `REPORT_ID_SHORT = 0x10`, `REPORT_ID_LONG = 0x11`
- `ERROR_SENTINEL = 0xFF`, `ERROR_OFFLINE = 0x05`, `ERROR_BUSY = 0x08`
- `HIDppError(code)` — raised when `response[2] == 0xFF`
- `build_short_msg(device_idx, feature_idx, function, params)` — returns 7-byte list
- `send_and_recv(device, msg, timeout_ms, min_len)` — returns response list or None

## Test Results

```
pytest tests/test_protocol.py -x -q
8 passed in 0.01s
```

TDD cycle followed: RED confirmed (ImportError before protocol.py), GREEN confirmed after implementation.

## Hardware Probe Results (Task 3)

### OFFSET = 1

`response[0]` IS the report ID byte. All downstream byte access uses 1-based indexing (data starts at index 1).

Example response from battery query: `[0x11, 0xFF, 0x06, 0x0D, 0x0D, 0xF4, 0x01, 0x00, ...]`
- `response[0]` = 0x11 → report ID IS present → **OFFSET = 1**

### Critical Protocol Discovery: G Pro X Wireless Uses 0xFF43, Not 0xFF00

The G Pro X Wireless headset (PID=0x0ABA) exposed three HID interfaces:

| Usage Page | OutputReportByteLength | Output Report IDs |
|------------|------------------------|-------------------|
| 0xFF00     | 64                     | 0x00, 0x90, 0xC4  |
| 0xFF43     | 20                     | 0x11              |
| 0x000C     | —                      | —                 |

Standard HID++ 2.0 writes to 0xFF00 (report IDs 0x10/0x11) ALL returned -1. The 0xFF43 interface with report ID 0x11 (20-byte long message) is the correct write target.

### Battery Command Protocol

This is a Logitech G-series headset protocol — different from standard HID++ 2.0 feature discovery:

**Write (20 bytes):**
```
[0x11, 0xFF, 0x06, 0x0D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
  ↑     ↑     ↑     ↑
 0x11  0xFF  feat  func
 long  recv  0x06  0x0D
 msg
```

- Report ID: `0x11` (HID++ long message)
- Device index: `0xFF` (the LIGHTSPEED receiver itself — no paired device index)
- Feature: `0x06`
- Function: `0x0D`

**Read response (20 bytes):**
```
[0x11, 0xFF, 0x06, 0x0D, V_hi, V_lo, state, 0x00, ...]
  [0]   [1]   [2]   [3]   [4]   [5]   [6]
```
- `response[4:6]` — voltage in mV, big-endian 16-bit
- `response[6]` — charging state: `0x01` = discharging, `0x03` = charging

**Voltage calibration curve (G Pro X Wireless, from HeadsetControl reference):**
```
Percentage: [100,  50,  30,  20,   5,   0]
Voltage mV: [4150, 3830, 3780, 3740, 3670, 3320]
```

### Live Reading from Hardware

```
Query: [0x11, 0xFF, 0x06, 0x0D, 0x00 × 16]
Response: [0x11, 0xFF, 0x06, 0x0D, 0x0D, 0xF4, 0x01, ...]
Voltage: (0x0D << 8) | 0xF4 = 3572 mV → ~3-4% battery
Charging: 0x01 → discharging
```

## Impact on Wave 2 Plans

The Phase 2 plan was written assuming standard HID++ 2.0 feature discovery (Root 0x0000 → probe chain 0x1004 → 0x1000 → 0x1001). The hardware probe reveals a different architecture:

| Assumption | Reality |
|------------|---------|
| Interface: 0xFF00 | Interface: **0xFF43** |
| device_idx discovered via Root probe | device_idx = **0xFF** (fixed) |
| Feature discovery via Root 0x0000 | **Direct command**: feature 0x06, function 0x0D |
| Returns percentage (0–100) | Returns **voltage in mV**, needs calibration curve |
| Battery features: 0x1004/0x1000/0x1001 | **Not applicable** for this device |

**Wave 2 plans (02-02, 02-03) must be updated before execution** to implement:
- `receiver.py`: enumerate and open the 0xFF43 interface
- `features.py`: G-series battery command (0x06/0x0D) + voltage→percentage conversion

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 (checkpoint) | — | pytest 9.0.3 + pytest-mock 3.15.1 installed |
| Task 2 | 87d828f | feat(02-01): implement HID++ protocol layer + pytest bootstrap |
| Task 3 (checkpoint) | — | Hardware probe: OFFSET=1, 0xFF43 protocol confirmed |

## Deviations from Plan

### Major Deviation: G Pro X Wireless Uses G-Series Headset Protocol, Not HID++ 2.0

**Found during:** Task 3 hardware probe  
**Issue:** All HID++ 2.0 writes to 0xFF00 (report IDs 0x10/0x11) returned -1. HID descriptor analysis (HidP_GetCaps, HidP_GetValueCaps) confirmed that 0xFF00 uses non-standard output report IDs (0x00, 0x90, 0xC4). The battery command lives on 0xFF43 interface with report ID 0x11.  
**Fix:** Discovered via HeadsetControl open-source project + ctypes HID API investigation. Working protocol confirmed on hardware.  
**Impact:** Wave 2 implementation must target 0xFF43 and use the G-series direct battery command instead of HID++ 2.0 feature discovery chain. The `protocol.py` layer built in this plan remains valid but the higher-level layers need different implementations.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/hidpp/protocol.py | FOUND |
| src/hidpp/__init__.py | FOUND |
| tests/test_protocol.py | FOUND (8 tests pass) |
| tests/conftest.py | FOUND |
| pytest.ini | FOUND |
| OFFSET confirmed | OFFSET = 1 (response[0] = report ID) |
| Hardware protocol confirmed | 0xFF43, device_idx=0xFF, feature 0x06/0x0D |
| Voltage reading | 3572 mV (~3-4%) confirmed live on hardware |
| Commit 87d828f | FOUND |
