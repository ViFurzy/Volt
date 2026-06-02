---
phase: 02-hidpp-20-protocol
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/hidpp/__init__.py
  - src/hidpp/features.py
  - src/hidpp/protocol.py
  - src/hidpp/receiver.py
  - src/query_battery.py
  - tests/conftest.py
  - tests/test_features.py
  - tests/test_protocol.py
  - tests/test_receiver.py
findings:
  critical: 1
  warning: 3
  info: 4
  total: 8
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-02
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the HID++ protocol layer for Phase 02 (G Pro X Wireless battery via G-series headset protocol). The implementation correctly reflects the hardware-probe findings: `usage_page=0xFF43`, `device_idx=0xFF`, and the direct `[0x11, 0xFF, 0x06, 0x0D]` battery command. The voltage-to-percent calibration logic is sound. Test coverage is good for the happy path.

One critical bug: `OSError` raised by `send_and_recv` is not caught in `battery_probe_chain`, meaning a device disconnect mid-read crashes the entire program instead of returning `None`. Three warnings cover: a latent `IndexError` in the error-sentinel path if callers pass small `min_len` values, dead code in `query_battery.py` that will misreport when `percent` is 0, and debug `print()` calls baked into a library function. Four info items cover dead code, unused fixture parameters, and path decoding style.

## Critical Issues

### CR-01: `OSError` from `send_and_recv` propagates uncaught through `battery_probe_chain`

**File:** `src/hidpp/features.py:46-49`
**Issue:** `battery_probe_chain` catches only `HIDppError`. `send_and_recv` explicitly re-raises `OSError` from both `device.write()` and `device.read()` (see `protocol.py:41-46`). If the headset dongle is physically unplugged between the `open_receiver()` call and the `send_and_recv()` call — a realistic scenario for a long-running monitor — the `OSError` propagates through `battery_probe_chain` to `query_battery.main()`, which has no `except` around step 4. The `finally` block only closes the device; it does not prevent a crash. The contract established by returning `None` on timeout/offline should also cover physical disconnect errors.

**Fix:**
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
        charging=charging,
        feature_used="0x06/0x0D",
    )
```

## Warnings

### WR-01: Latent `IndexError` in `send_and_recv` error-sentinel path when `min_len < 6`

**File:** `src/hidpp/protocol.py:54-58`
**Issue:** The response length check (`if len(response) < min_len`) gates on the caller-supplied `min_len` argument. The subsequent error-sentinel branch at line 57-58 unconditionally accesses `response[5]` (`raise HIDppError(response[5])`). If a caller ever passes `min_len < 6`, a short error response of fewer than 6 bytes will pass the length guard and then throw an `IndexError` — not a `HIDppError` — at the access site. The current only caller passes `min_len=7` so this does not crash today, but the function's public contract does not prohibit `min_len < 6`.

**Fix:** Add an independent guard for the error packet minimum length before accessing `response[5]`:
```python
if response[2] == ERROR_SENTINEL:
    if len(response) < 6:
        raise HIDppError(0x00)   # malformed error packet, unknown code
    raise HIDppError(response[5])
```

### WR-02: Dead `is not None` guard in `query_battery.py` masks the real `percent == 0` case

**File:** `src/query_battery.py:40`
**Issue:** `result.percent is not None` is always `True` because `BatteryResult.percent: int` and `voltage_to_percent` always returns `int`. The intended distinction is between a known percentage (including 0%) and an unknown-while-charging state. As written, `percent == 0` will display as `"0%"` not as `"Charging (% unknown)"`, which is probably correct — but the branch condition is misleading and will silently break if `voltage_to_percent` ever starts returning `None` (e.g., to indicate a parse failure), because the guard still passes.

**Fix:** Remove the dead branch and replace with an explicit check matching the actual type:
```python
# If percent is always int, just format it directly:
pct_str = f"{result.percent}%"
charging_str = "charging" if result.charging else "not charging"
print(f"Battery: {pct_str} — {charging_str} (feature {result.feature_used})")
```
If "unknown while charging" is a real future state, update `BatteryResult.percent` to `int | None` and keep the guard.

### WR-03: `print()` calls inside `find_receiver()` library function

**File:** `src/hidpp/receiver.py:43-60`
**Issue:** `find_receiver()` is a library function imported by `query_battery.py` and eventually will be called by the background monitoring thread. It unconditionally prints every enumerated HID interface to stdout on every call. This couples enumeration to a specific output channel and makes it impossible to use the function silently (e.g., in a periodic poll loop, in tests, or when the UI is the output channel). In `test_receiver.py`, the tests invoke `find_receiver()` and all that output goes to the test console unfiltered.

**Fix:** Accept an optional `verbose: bool = False` parameter, or remove the prints entirely and let callers log what they need. For the integration script, logging at caller level is sufficient:
```python
def find_receiver(vid: int = LOGITECH_VID, verbose: bool = False) -> list[dict]:
    all_devices = hid.enumerate(vid, 0)
    if verbose:
        # ... print loop ...
    return [d for d in all_devices if d["usage_page"] == VENDOR_USAGE_PAGE]
```

## Info

### IN-01: Unreachable `return 0` in `voltage_to_percent`

**File:** `src/hidpp/features.py:36`
**Issue:** The boundary checks on lines 26-29 ensure that by the time the loop is entered, `_CALIB[0][0] < mv < _CALIB[-1][0]`. The calibration table is contiguous (each segment's upper bound equals the next segment's lower bound), so the loop is guaranteed to find and return from a matching segment. The final `return 0` on line 36 is unreachable dead code. It is not harmful, but it obscures the fact that falling through the loop is impossible.

**Fix:** Replace with `raise AssertionError("unreachable: calibration table has a gap")` or a comment `# unreachable — calibration table is contiguous`. Do not silently return 0.

### IN-02: `mock_hid` fixture used as parameter in tests that never use it

**File:** `tests/test_protocol.py:5,10,16`
**Issue:** `test_build_short_msg_basic`, `test_build_short_msg_function_nibble`, and `test_build_short_msg_params` all accept `mock_hid` as a parameter but never reference it. `build_short_msg` is a pure function; no mock device is needed. The unused parameter is noisy and misleading.

**Fix:** Remove `mock_hid` from the signature of all three tests:
```python
def test_build_short_msg_basic():
    assert build_short_msg(device_idx=0x01, feature_idx=0x00, function=0) == [0x10, 0x01, 0x00, 0x01, 0, 0, 0]
```

### IN-03: Module docstring position in `query_battery.py`

**File:** `src/query_battery.py:8-15`
**Issue:** The module docstring (triple-quoted string at lines 8-15) appears after the `import` block. PEP 257 requires module docstrings to be the first statement of the module. Python's `__doc__` attribute will be `None` for this module because the docstring follows imports. This is a minor conformance issue, not a runtime bug.

**Fix:** Move the docstring to line 1 (before `import sys`). Since `sys.coinit_flags = 0` must be line 2, the module docstring must come first — this is actually compatible: a module docstring does not import anything and does not affect COM initialization.

```python
"""
Phase 2 standalone integration script for PeriphWatcher.
...
"""
import sys
sys.coinit_flags = 0  # MUST be here — before any other import.
```

### IN-04: `path` decoding in `find_receiver` uses `repr()` fallback for non-bytes paths

**File:** `src/hidpp/receiver.py:52-53`
**Issue:** When `path` is not `bytes` (which is the typical case on Windows where hidapi returns a string path), the fallback is `repr(path)`. `repr()` on a string wraps it in single quotes: `repr("\\\\?\\HID#VID...")` → `"'\\\\?\\HID#...'"`. The quotes become part of the printed output, making it look like a Python literal rather than a path. This is a log-readability issue.

**Fix:**
```python
path_str = path.decode("utf-8", errors="replace") if isinstance(path, bytes) else path
```

---

_Reviewed: 2026-06-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
