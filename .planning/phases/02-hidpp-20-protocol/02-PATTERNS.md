# Phase 2: HID++ 2.0 Protocol - Pattern Map

**Mapped:** 2026-06-01
**Files analyzed:** 7 (4 new src/hidpp/, 3 new tests/, plus query_battery.py)
**Analogs found:** 7 / 7 (all from the 3 existing Phase 1 source files)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/hidpp/__init__.py` | config | — | `src/hid_poc.py` (module docstring style) | partial |
| `src/hidpp/protocol.py` | utility | request-response | `src/hid_poc.py` | exact |
| `src/hidpp/features.py` | service | request-response | `src/hid_poc.py` | role-match |
| `src/hidpp/receiver.py` | service | CRUD | `src/hid_poc.py` | exact |
| `src/hidpp/query_battery.py` | controller | request-response | `src/hid_poc.py` (main() pattern) | exact |
| `tests/conftest.py` | test | — | no analog (greenfield) | none |
| `tests/test_protocol.py` | test | — | no analog (greenfield) | none |
| `tests/test_features.py` | test | — | no analog (greenfield) | none |

---

## Pattern Assignments

### `src/hidpp/__init__.py` (config)

**Analog:** `src/hid_poc.py`

**Module docstring style** (`src/hid_poc.py` lines 1-9):
```python
"""
HID enumeration and raw I/O proof-of-concept for the PeriphWatcher project.

Enumerates all Logitech (VID=0x046D) HID interfaces, filters for the vendor-specific
interface (usage_page=0xFF00), opens it exclusively via open_path(), and performs a
raw write + read round-trip. This script confirms that Windows HID access on the
vendor-specific usage page works without Access Denied before any HID++ protocol
code is written.
"""
```

For `__init__.py` use the same single-paragraph style: one sentence on what the package does and what invariant it enforces. Keep it to 3-5 lines. No code — this file is intentionally empty of logic.

---

### `src/hidpp/protocol.py` (utility, request-response)

**Analog:** `src/hid_poc.py`

**Imports pattern** (`src/hid_poc.py` lines 11-12):
```python
import sys
import hid
```
Copy: `import hid` only. No `sys` needed. No third-party imports beyond stdlib and hid.

**Constants pattern** (`src/hid_poc.py` lines 14-17):
```python
LOGITECH_VID = 0x046D
VENDOR_USAGE_PAGE = 0xFF00
REPORT_SIZE = 64
READ_TIMEOUT_MS = 1000
```
Copy this style exactly: module-level SCREAMING_SNAKE_CASE constants with hex literals. For protocol.py the constants will be:
```python
REPORT_ID_SHORT = 0x10   # 7-byte HID++ 2.0 short message
REPORT_ID_LONG  = 0x11   # 20-byte HID++ 2.0 long message
ERROR_SENTINEL  = 0xFF   # response[2] == 0xFF signals a HID++ error
ERROR_OFFLINE   = 0x05   # LOGITECH_INTERNAL — device off or out of range
ERROR_BUSY      = 0x08   # device temporarily busy — retry
```

**Write + read core pattern** (`src/hid_poc.py` lines 69-89):
```python
payload = [0x00] * REPORT_SIZE  # report ID 0x00 = no report ID prefix
try:
    device.write(payload)
    print("Write: sent 64-byte null report")
except OSError as exc:
    print(f"Write OSError: {exc}")
except Exception as exc:  # noqa: BLE001
    print(f"Write error ({type(exc).__name__}): {exc}")

try:
    response = device.read(REPORT_SIZE, timeout_ms=READ_TIMEOUT_MS)
    if not response:
        print(
            "Read: timeout (empty response) — device may be off or wrong interface"
        )
    else:
        print(f"Read: {len(response)} bytes — first 8: {response[:8]}")
except OSError as exc:
    print(f"Read OSError: {exc}")
except Exception as exc:  # noqa: BLE001
    print(f"Read error ({type(exc).__name__}): {exc}")
```

For `send_and_recv()` in `protocol.py`: keep the `try/except OSError` on both write and read. Change the broad `except Exception` to re-raise (or remove it) since the contract of send_and_recv is to raise on unexpected errors, not swallow them. Empty response (`not response`) maps to returning `None`, not printing.

**Error handling pattern** (`src/hid_poc.py` lines 72-76, 87-89):
```python
except OSError as exc:
    print(f"Write OSError: {exc}")
except Exception as exc:  # noqa: BLE001
    print(f"Write error ({type(exc).__name__}): {exc}")
```
In protocol.py: replace the print with `raise` for `OSError` so the caller can decide whether to re-open or abort. The broad `except Exception` is a PoC pattern — do not carry it into production modules.

**finally / close pattern** (`src/hid_poc.py` lines 57, 91-92):
```python
device = hid.device()
try:
    device.open_path(info["path"])
    ...
finally:
    device.close()
```
`protocol.py` itself does not open or close devices — that is `receiver.py`'s job. The `finally: device.close()` pattern lives in `receiver.py`.

---

### `src/hidpp/receiver.py` (service, CRUD)

**Analog:** `src/hid_poc.py`

**enumerate + usage_page filter pattern** (`src/hid_poc.py` lines 20-48):
```python
def find_vendor_interfaces(vid: int) -> list:
    """
    Enumerate all HID interfaces for the given VID and return those with
    usage_page == VENDOR_USAGE_PAGE (0xFF00).

    Prints every enumerated interface first so the exact PID is visible.
    Returns a list of matching dicts (may be empty).
    """
    print(f"=== All Logitech (0x{vid:04X}) HID interfaces ===")
    all_devices = hid.enumerate(vid, 0)

    if not all_devices:
        print("  (no devices found for this VID)")
        return []

    for info in all_devices:
        path = info["path"]
        path_str = path.decode("utf-8", errors="replace") if isinstance(path, bytes) else repr(path)
        print(
            f"  PID=0x{info['product_id']:04X}  "
            f"usage_page=0x{info['usage_page']:04X}  "
            f"usage=0x{info['usage']:04X}  "
            f"path={path_str}  "
            f"manufacturer={info.get('manufacturer_string', '')}  "
            f"product={info.get('product_string', '')}"
        )

    vendor_interfaces = [d for d in all_devices if d["usage_page"] == VENDOR_USAGE_PAGE]
    return vendor_interfaces
```
Copy this function into `receiver.py` nearly verbatim. Rename to `find_receiver()` or keep as `find_vendor_interfaces()`. The `path.decode("utf-8", errors="replace")` guard for bytes paths is critical — keep it.

**open_path pattern** (`src/hid_poc.py` lines 51-67):
```python
def open_and_probe(info: dict) -> None:
    """
    Open the HID interface described by `info` via open_path() and perform a
    raw write + read round-trip. Closes the device in a finally block.
    """
    device = hid.device()
    try:
        device.open_path(info["path"])
        print(
            f"Opened: {device.get_manufacturer_string()} {device.get_product_string()}"
        )
        ...
    finally:
        device.close()
```
For `receiver.py`: split this into `open_receiver(info: dict) -> hid.device` (returns the open handle, does not close it — caller owns lifetime) and a separate `close_receiver(device)`. The `finally: device.close()` moves to the caller's context manager or to `query_battery.py`'s main() try/finally.

**Guard: no open(vid, pid)** (`src/hid_poc.py` — note: `open_path()` is used, not `hid.open()`):
```python
device.open_path(info["path"])   # CORRECT — opens specific interface
# NOT: hid.open(vid, pid)        # WRONG — opens first/wrong interface, Access Denied
```
This invariant is already enforced in `hid_poc.py`. Carry it into `receiver.py` by never calling `hid.open()`.

---

### `src/hidpp/features.py` (service, request-response)

**Analog:** `src/hid_poc.py` (write/read pair) + RESEARCH.md probe chain pattern

The write/read pair from `hid_poc.py` (lines 69-89) is the atomic unit that `features.py` delegates to `protocol.send_and_recv()`. The probe chain structure itself has no existing analog in the codebase — follow the RESEARCH.md pattern verbatim.

**Constants style** (`src/hid_poc.py` lines 14-17 — same style):
```python
# Feature IDs — runtime indices are discovered, these are the 16-bit IDs
FEAT_ROOT            = 0x0000
FEAT_BATTERY_STATUS  = 0x1000
FEAT_BATTERY_VOLTAGE = 0x1001
FEAT_UNIFIED_BATTERY = 0x1004

BATTERY_PROBE_ORDER = [FEAT_UNIFIED_BATTERY, FEAT_BATTERY_STATUS, FEAT_BATTERY_VOLTAGE]
```

**Error handling style for offline** (`src/hid_poc.py` lines 80-83 — the `not response` check):
```python
if not response:
    print(
        "Read: timeout (empty response) — device may be off or wrong interface"
    )
```
In `features.py`, the equivalent is: `if result is None: return None` (device offline — timeout). For `HIDppError(ERROR_OFFLINE)` caught from `protocol.send_and_recv()`: return `None` rather than propagating upward, per RESEARCH.md pattern.

---

### `src/hidpp/query_battery.py` (controller, request-response)

**Analog:** `src/hid_poc.py` (main() function structure)

**main() structure** (`src/hid_poc.py` lines 95-121):
```python
def main() -> None:
    # STEP 1 — Full Logitech VID scan
    vendor_interfaces = find_vendor_interfaces(LOGITECH_VID)

    # STEP 2 — Filter for LIGHTSPEED candidates
    if not vendor_interfaces:
        all_pids = [
            f"0x{d['product_id']:04X}"
            for d in hid.enumerate(LOGITECH_VID, 0)
        ]
        print(
            f"No usage_page=0xFF00 interface found. "
            f"PIDs seen: {', '.join(all_pids) if all_pids else '(none)'}"
        )
        sys.exit(1)

    print(f"Found {len(vendor_interfaces)} interface(s) with usage_page=0xFF00")

    # Use the first matching entry
    target = vendor_interfaces[0]

    # STEP 3 + 4 + 5 — Open, probe, close
    open_and_probe(target)


if __name__ == "__main__":
    main()
```
Copy this numbered-step comment style and `sys.exit(1)` on missing device. For `query_battery.py` the steps become: enumerate → open → discover device index → probe chain → print result → close (in finally).

**if __name__ == "__main__" guard** (`src/hid_poc.py` line 120-121):
```python
if __name__ == "__main__":
    main()
```
All standalone scripts in this project use this guard. Copy verbatim.

---

### `tests/conftest.py`, `tests/test_protocol.py`, `tests/test_features.py` (test)

**No analog in codebase.** The `tests/` directory does not exist yet. Use the RESEARCH.md code examples directly.

**conftest.py fixture pattern** (from RESEARCH.md lines 581-588):
```python
import pytest

@pytest.fixture
def mock_hid(mocker):
    """Factory that returns a mock hid.device with configurable read behavior."""
    device = mocker.MagicMock()
    device.write.return_value = None  # hidapi write returns byte count; mock ignores
    return device
```

**test function pattern** (from RESEARCH.md lines 591-614):
```python
def test_offline_returns_none(mock_hid):
    """When device is off, read returns [] (timeout). probe chain must return None."""
    mock_hid.read.return_value = []  # simulate timeout
    result = battery_probe_chain(mock_hid, device_idx=0x01)
    assert result is None
```
All test functions: single docstring, arrange mock behavior, call function under test, single assert. No class wrappers.

---

## Shared Patterns

### HID device open/close lifecycle
**Source:** `src/hid_poc.py` lines 56-92
**Apply to:** `receiver.py`, `query_battery.py`
```python
device = hid.device()
try:
    device.open_path(info["path"])
    # ... all I/O here ...
finally:
    device.close()
```
Always use `try/finally` to guarantee `device.close()`. Never rely on garbage collection.

### OSError wrapping on write/read
**Source:** `src/hid_poc.py` lines 72-89
**Apply to:** `protocol.py` (send_and_recv), `receiver.py` (find_device_index)
```python
try:
    device.write(payload)
except OSError as exc:
    # ... handle or re-raise
try:
    response = device.read(REPORT_SIZE, timeout_ms=READ_TIMEOUT_MS)
except OSError as exc:
    # ... handle or re-raise
```
`OSError` is the expected exception when the receiver is unplugged mid-session. Always catch it separately from the broad `Exception`.

### Module-level constants block
**Source:** `src/hid_poc.py` lines 14-17
**Apply to:** All `src/hidpp/*.py` files
```python
LOGITECH_VID     = 0x046D
VENDOR_USAGE_PAGE = 0xFF00
REPORT_SIZE      = 64
READ_TIMEOUT_MS  = 1000
```
Place all numeric constants at module level with hex literals. No magic numbers inline in function bodies.

### Empty response = offline, not error
**Source:** `src/hid_poc.py` lines 80-83
**Apply to:** `protocol.py` (send_and_recv returns None), `features.py` (probe chain returns None)
```python
if not response:
    print("Read: timeout (empty response) — device may be off or wrong interface")
```
An empty list from `device.read()` means timeout. This is a normal operational state (mouse switched off), not a bug. Return `None` and let the caller decide.

### sys.coinit_flags = 0 guard
**Source:** `src/__main__.py` line 1, `src/threading_stub.py` line 1
**Apply to:** `src/hidpp/query_battery.py` only (standalone entry point)
```python
import sys
sys.coinit_flags = 0  # MUST be here — before any other import.
```
Any file with `if __name__ == "__main__"` that might eventually be called in a context with bleak must set this flag first. `query_battery.py` is Phase 2 standalone only (no bleak yet), but the pattern must be established now to prevent future mistakes.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `tests/conftest.py` | test fixture | — | No tests exist yet; use RESEARCH.md mock_hid fixture verbatim |
| `tests/test_protocol.py` | test | — | No tests exist yet; use RESEARCH.md examples as starting point |
| `tests/test_features.py` | test | — | No tests exist yet; use RESEARCH.md examples as starting point |

---

## Metadata

**Analog search scope:** `src/` (3 files: `hid_poc.py`, `__main__.py`, `threading_stub.py`)
**Files scanned:** 3
**Pattern extraction date:** 2026-06-01
**Primary analog:** `src/hid_poc.py` — provides 100% of the HID I/O patterns needed
**Secondary analog:** `src/__main__.py` + `src/threading_stub.py` — provide `sys.coinit_flags = 0` guard and threading patterns (Phase 3 relevance; reference only for Phase 2 entry point)
