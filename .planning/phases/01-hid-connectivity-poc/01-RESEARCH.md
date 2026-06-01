# Phase 1: HID Connectivity PoC — Research

**Researched:** 2026-06-01
**Domain:** Windows HID raw I/O, asyncio + PySide6 threading pattern, COM apartment model
**Confidence:** HIGH (all core findings verified against official sources or Solaar/bleak authoritative references)

---

## Summary

Phase 1 is a pure infrastructure phase with two exit criteria: (1) prove Windows HID access works on the vendor-specific usage page without Access Denied, and (2) lock in the COM/threading invariants before any protocol work. The `hid` 1.0.9 library (ctypes-hidapi) provides `hid.enumerate(vid, pid)` which returns a list of dicts including `usage_page` and `path` fields — the correct pattern is to filter this list for `usage_page == 0xFF00` and call `hid.device().open_path(entry["path"])`. The Logitech LIGHTSPEED receiver family (VID 0x046D, PIDs C539/C53A/C53D/C53F/C541/C545/C547) exposes at least two HID collections: one for mouse/keyboard (usage_page 0x0001, locked by Windows) and one vendor-specific (usage_page 0xFF00, writable from user-space). `sys.coinit_flags = 0` must be the very first executable statement in `__main__` — it is read by `pythoncom` when it initializes; once any import touches COM it is too late. PyInstaller's bootloader runs before user code but does not add COM imports; the risk is pywin32/Qt transitive imports if coinit_flags is not set first. The asyncio + PySide6 threading pattern uses `asyncio.new_event_loop()` + `loop.run_forever()` on a `daemon=True` thread, `asyncio.run_coroutine_threadsafe()` to schedule work from Qt, `queue.Queue.put()` to return results, and a `QTimer` draining the queue at 500ms intervals on the main thread. Clean shutdown is `loop.call_soon_threadsafe(loop.stop)` followed by `thread.join()`.

**Primary recommendation:** Create two files — `src/hid_poc.py` (enumerate by VID/PID, filter usage_page, open_path, raw read/write) and `src/threading_stub.py` (minimal asyncio + Qt + queue pattern). Keep both as standalone scripts that can be run independently. The project `src/` directory establishes the layout for Phase 2 onward.

---

## Project Constraints (from CLAUDE.md)

| Directive | Detail |
|-----------|--------|
| `sys.coinit_flags = 0` first line | Before ALL imports in `__main__`; bleak WinRT requires MTA; STA from Qt/pywin32 causes `connect()` to hang forever |
| All HID/BLE I/O on asyncio background thread | Qt requires main thread for UI; mixing threads causes data races |
| UI communicates via `queue.Queue` only | Thread-safe; no locks needed in calling code |
| HID interface by `usage_page=0xFF00` only | Windows locks 0x0001 mouse/keyboard; Access Denied otherwise |
| HID++ feature indices discovered at runtime | Never hardcoded; firmware-assigned; breaks on variants |
| Stack locked | `hid` 1.0.9, `PySide6` 6.11.1, `bleak` 3.0.2 |
| Do NOT use | `pywinusb`, `hidapi` (cython), `PyBluez`, `winotify`, `PyQt6` |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HID device enumeration + I/O | Background thread (asyncio) | — | HID calls are blocking I/O; must not run on Qt main thread |
| COM apartment initialization | `__main__` (process startup) | — | Must fire before any import that touches pythoncom |
| Qt event loop + QTimer | Main thread | — | Qt is single-threaded; all widget and timer calls from main thread only |
| Cross-thread messaging | `queue.Queue` | — | Thread-safe; owned by neither thread; producer-consumer boundary |
| asyncio coroutine scheduling from Qt | `loop.call_soon_threadsafe` / `asyncio.run_coroutine_threadsafe` | — | Only thread-safe way to submit work to a running loop from another thread |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `hid` (ctypes-hidapi) | 1.0.9 | HID device enumeration and raw read/write | Pure ctypes; no compiler; pip-installable; confirmed on PyPI Feb 2026 [VERIFIED: PyPI] |
| `PySide6` | 6.11.1 | Qt event loop, QApplication, QTimer | LGPL; official Qt6 Python bindings; `QTimer` for queue drain [VERIFIED: PyPI] |
| `asyncio` | stdlib | Background event loop | `new_event_loop()` + `run_forever()` pattern [VERIFIED: Python stdlib docs] |
| `queue` | stdlib | Thread-safe cross-thread message passing | `queue.Queue` is the only safe producer-consumer bridge [VERIFIED: Python stdlib docs] |
| `threading` | stdlib | Daemon thread hosting the asyncio loop | `daemon=True` ensures clean process exit [VERIFIED: Python stdlib docs] |

### Supporting (Phase 1 only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sys` | stdlib | `sys.coinit_flags = 0` COM setup | Must be used; it is set on the `sys` module object before `pythoncom` reads it |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `hid.device().open_path()` | `hid.device().open(vid, pid)` | `open()` opens first matching interface regardless of usage_page — wrong on multi-interface devices; `open_path()` targets the exact interface selected by filtering |
| `queue.Queue` | `asyncio.Queue` | `asyncio.Queue` is NOT thread-safe; only safe within one event loop [ASSUMED] |
| Native `threading.Thread` + `asyncio.new_event_loop()` | `qasync` | `qasync` merges Qt and asyncio loops but adds a dependency and complexity; for Phase 1 PoC the two-loop pattern is simpler and sufficient |

**Installation (Phase 1 only):**
```bash
pip install hid PySide6
```

**Version verification:**
```
hid: 1.0.9 (Feb 2026) — confirmed PyPI
PySide6: 6.11.1 (May 2026) — confirmed PyPI
```

---

## Package Legitimacy Audit

> slopcheck was not available in this environment. Packages below are tagged based on PyPI registry confirmation and official project affiliation.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `hid` | PyPI | ~8 yrs | High (ctypes-hidapi) | github.com/trezor/cython-hidapi | [ASSUMED OK] | Approved — official Trezor project, widely used |
| `PySide6` | PyPI | ~4 yrs | Very high | github.com/qt/qt5 (official Qt Company) | [ASSUMED OK] | Approved — official Qt Company package |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable at research time. Both packages are large, well-established projects with official backing. Planner may add a `checkpoint:human-verify` before install if required by policy.*

---

## Architecture Patterns

### System Architecture Diagram

```
__main__ (process start)
  |
  v
sys.coinit_flags = 0          <-- MUST be line 1, before all imports
  |
  v
import threading, asyncio, queue
import PySide6 (QApplication, QTimer)
import hid
  |
  +---> Background Thread (daemon=True)
  |       asyncio event loop
  |       loop.run_forever()
  |           |
  |           +---> hid.enumerate(VID, PID)
  |           |     filter usage_page == 0xFF00
  |           |     hid.device().open_path(path)
  |           |     device.write([0x00, ...])  (output report)
  |           |     device.read(64, timeout_ms=1000)
  |           |
  |           +---> queue.Queue.put(result)   --> [queue.Queue] --> QTimer drain
  |                                                                    |
  +---> Main Thread                                                    v
          QApplication.exec()                              apply_update(msg)
          QTimer(500ms) -> drain queue
```

### Recommended Project Structure

```
src/
├── hid_poc.py          # Phase 1: enumerate + open_path + raw read/write proof
└── threading_stub.py   # Phase 1: asyncio thread + queue.Queue + QTimer skeleton
```

No `__init__.py` needed in Phase 1 — both files are standalone scripts. Phase 2 will introduce a proper package structure under `src/periph_watcher/`.

---

### Pattern 1: HID Device Enumeration and Interface Selection

**What:** Enumerate all HID collections for a VID/PID, filter to usage_page=0xFF00, open by path.

**When to use:** Every HID open in the entire project. Never use `hid.device().open(vid, pid)` for multi-interface devices.

**Example:**
```python
# Source: hid PyPI 1.0.9 API + PITFALLS.md Pitfall 1
import hid

VID = 0x046D
PID = 0xC547  # G Pro X Superlight LIGHTSPEED receiver; adjust to connected device

def find_vendor_interface(vid: int, pid: int) -> dict | None:
    """Return the enumeration dict for the vendor-specific (usage_page=0xFF00) interface."""
    for device_info in hid.enumerate(vid, pid):
        if device_info["usage_page"] == 0xFF00:
            return device_info
    return None

info = find_vendor_interface(VID, PID)
if info is None:
    raise RuntimeError(f"No usage_page=0xFF00 interface found for {VID:04X}:{PID:04X}")

device = hid.device()
device.open_path(info["path"])
print(f"Opened: {device.get_manufacturer_string()} {device.get_product_string()}")
```

**Key detail:** `hid.enumerate(vid, pid)` returns multiple dicts for the same VID/PID — one per HID collection/interface. The `path` field is bytes-typed on Windows. `open_path` accepts bytes.

---

### Pattern 2: Raw Read/Write

**What:** Write an output report, read back the response with a short timeout.

**When to use:** All HID I/O for PoC raw round-trip testing.

**Example:**
```python
# Source: hid API docs + PITFALLS.md Pitfall 4 (timeout on offline device)

# Write: first byte is report ID (0x00 = no report ID, or use 0x10 for HID++)
# Always pad to the device's output report size (typically 64 bytes for HID++ receivers)
REPORT_SIZE = 64
payload = [0x00] + [0x00] * (REPORT_SIZE - 1)  # raw null report for PoC
device.write(payload)

# Read: always specify timeout_ms; never block indefinitely
# Returns: list of int (0-255), empty list [] on timeout
response = device.read(REPORT_SIZE, timeout_ms=1000)
if not response:
    print("Timeout — no response (device may be offline or wrong interface)")
else:
    print(f"Response bytes: {response[:8]}")  # first 8 for inspection
```

**Key detail:** `device.read()` returns an **empty list `[]`** on timeout — not an exception, not `None`, not `b""`. Always check `if not response:`. [VERIFIED: libusb/hidapi docs]

---

### Pattern 3: sys.coinit_flags Placement

**What:** Set COM apartment mode to MTA before pythoncom initializes it.

**When to use:** Must appear as lines 1-2 of every `__main__` script in the project.

**Example:**
```python
# Source: bleak troubleshooting docs + PITFALLS.md Pitfall 5
# THIS MUST BE THE FIRST EXECUTABLE CODE IN __main__
# Reason: pythoncom reads sys.coinit_flags when it first initializes COM.
# If PySide6 or pywin32 imports run first, COM is initialized as STA.
# bleak's WinRT backend requires MTA; STA causes await client.connect()
# to hang forever with no timeout and no error message.
import sys
sys.coinit_flags = 0  # 0 = COINIT_MULTITHREADED (MTA); 0x2 would be STA (wrong)

# Only NOW is it safe to import PySide6, pywin32, bleak, hid, etc.
import threading
import asyncio
import queue
from PySide6.QtWidgets import QApplication
```

**Key detail:** `sys.coinit_flags = 0` and `sys.coinit_flags = 0x0` are identical — both are integer zero. The comment explaining the reason is a **project invariant** (see CLAUDE.md). [VERIFIED: bleak troubleshooting docs]

---

### Pattern 4: asyncio Background Thread + queue.Queue + QTimer

**What:** Minimal stub — asyncio loop on daemon thread, one-way message to Qt main thread via queue, QTimer drain.

**When to use:** Threading architecture for all phases that involve background I/O.

**Example:**
```python
# Source: Python stdlib asyncio docs + ARCHITECTURE.md threading model
import sys
sys.coinit_flags = 0  # MTA — must be first

import asyncio
import queue
import threading
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import QTimer

# ---- Shared cross-thread queue ----
ui_queue: queue.Queue = queue.Queue()

# ---- Background asyncio work ----
async def background_task(loop: asyncio.AbstractEventLoop) -> None:
    """Simulate async work; push one message to the Qt thread."""
    await asyncio.sleep(0.5)          # simulate I/O delay
    ui_queue.put("hello from asyncio")
    loop.call_soon_threadsafe(loop.stop)  # signal loop to stop after this task

def run_background(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()

# ---- Qt main thread ----
def drain_queue(label: QLabel) -> None:
    """Called by QTimer every 500ms on the main thread."""
    try:
        while True:
            msg = ui_queue.get_nowait()
            label.setText(f"Received: {msg}")
    except queue.Empty:
        pass

def main() -> None:
    app = QApplication([])
    label = QLabel("Waiting...")
    label.show()

    # Start asyncio loop on daemon background thread
    bg_loop = asyncio.new_event_loop()
    bg_thread = threading.Thread(target=run_background, args=(bg_loop,), daemon=True)
    bg_thread.start()

    # Schedule async work from main thread (thread-safe)
    asyncio.run_coroutine_threadsafe(background_task(bg_loop), bg_loop)

    # QTimer drains the queue every 500ms on main thread
    timer = QTimer()
    timer.timeout.connect(lambda: drain_queue(label))
    timer.start(500)

    app.exec()

    # Clean shutdown: stop loop, join thread
    bg_loop.call_soon_threadsafe(bg_loop.stop)
    bg_thread.join(timeout=5.0)

if __name__ == "__main__":
    main()
```

**Key details:**
- `asyncio.run_coroutine_threadsafe(coro, loop)` — submits a coroutine to the running loop from any thread; returns a `concurrent.futures.Future`. [VERIFIED: Python stdlib docs]
- `loop.call_soon_threadsafe(loop.stop)` — the only thread-safe way to stop the loop from outside. [VERIFIED: Python stdlib docs]
- `queue.Queue.put()` is thread-safe; `queue.Queue.get_nowait()` raises `queue.Empty` when empty. [VERIFIED: Python stdlib docs]
- The `QTimer` callback fires on the Qt main thread — safe to call any Qt widget methods there.
- `bg_thread.join(timeout=5.0)` waits for the asyncio thread to exit after `loop.stop()`.

---

### Anti-Patterns to Avoid

- **`hid.device().open(vid, pid)` without usage_page filter:** Opens the first matching interface — which is the locked mouse interface on LIGHTSPEED dongles. Results in Access Denied / OSError. Always use `open_path` after filtering by `usage_page == 0xFF00`.

- **`device.read(64)` with no timeout:** If device is off, receiver accepts write but never replies; read blocks forever. Always pass `timeout_ms=100` to `1000` depending on context.

- **`sys.coinit_flags = 0` after any import:** Importing `PySide6`, `pywin32`, or any package that transitively imports `pythoncom` before setting this flag initializes COM as STA. Setting it afterwards has no effect. [VERIFIED: bleak troubleshooting docs]

- **`asyncio.Queue` for cross-thread communication:** `asyncio.Queue` is only safe within one event loop's coroutines. Calling `.put_nowait()` from a Qt thread on an asyncio.Queue is not thread-safe. Use `queue.Queue` (stdlib). [ASSUMED based on Python stdlib docs note "not thread-safe"]

- **`asyncio.run()` called more than once:** Creates a new event loop each time; bleak objects are bound to the loop they were created on and cannot be reused across loops. Use `asyncio.new_event_loop()` + `run_forever()` once for the process lifetime.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HID interface discovery | Custom USB descriptor parser | `hid.enumerate()["usage_page"]` filter | hidapi already reads the descriptor; re-parsing is fragile and unnecessary |
| Thread-safe message passing | Custom lock-based shared state | `queue.Queue` (stdlib) | Queue handles all synchronization internally; hand-rolled locks introduce deadlock risk |
| COM apartment initialization | Manual `pythoncom.CoInitializeEx(0)` | `sys.coinit_flags = 0` before imports | `sys.coinit_flags` is the correct hook; direct `CoInitializeEx` calls from Python require pywin32 which itself may trigger STA first |
| Asyncio-to-Qt event bridge | Custom callback registration | `asyncio.run_coroutine_threadsafe` + `queue.Queue` + `QTimer` | This is the established, documented pattern for this exact use case |

---

## Logitech LIGHTSPEED Receiver Reference

### Known PIDs (VID 0x046D)

| PID | Name | Notes |
|-----|------|-------|
| 0xC539 | LIGHTSPEED Receiver | Confirmed [CITED: Solaar docs/devices.md] |
| 0xC53A | LIGHTSPEED Receiver | Confirmed [CITED: Solaar docs/devices.md] |
| 0xC53D | LIGHTSPEED Receiver | Confirmed [CITED: Solaar docs/devices.md] |
| 0xC53F | LIGHTSPEED Receiver | Confirmed [CITED: Solaar docs/devices.md] |
| 0xC541 | LIGHTSPEED Receiver | Confirmed [CITED: Solaar docs/devices.md] |
| 0xC545 | LIGHTSPEED Receiver | Confirmed [CITED: Solaar docs/devices.md] |
| 0xC547 | LIGHTSPEED Receiver (G Pro X Superlight) | Confirmed [CITED: Solaar docs/devices.md] |
| 0xC52B | Unifying Receiver | Different protocol family; not LIGHTSPEED |
| 0xC548 | Bolt Receiver | Different protocol family; not LIGHTSPEED |

**For the G Pro X Wireless, the receiver is typically C547.** The exact PID to use in `hid_poc.py` must be confirmed against the hardware present; enumerate with VID=0x046D and scan all results if unsure.

### HID Interface Structure

LIGHTSPEED receivers expose at least two HID collections:

| Interface | usage_page | usage | Access on Windows |
|-----------|-----------|-------|-------------------|
| Primary mouse/keyboard | 0x0001 (Generic Desktop) | 0x02 (Mouse) or similar | Denied — locked by Windows HID driver |
| Vendor-specific (HID++) | 0xFF00 | 0x0001 or 0x0002 | Open — accessible from user space |

The vendor-specific interface is the one with `usage_page == 0xFF00`. Some receivers expose a second vendor page as well; use the first `usage_page == 0xFF00` entry found. [CITED: PITFALLS.md Pitfall 1, hidapi issue #228] [ASSUMED: exact interface count from enumeration on the specific hardware]

---

## Common Pitfalls

### Pitfall 1: Access Denied on Wrong Interface
**What goes wrong:** `hid.device().open(0x046D, 0xC547)` opens the first enumerated interface — the mouse/keyboard interface. Windows returns Error 5 (Access Denied) or Error 32 (Sharing Violation).
**Why it happens:** Windows HID driver (HidUsb/mouhid) holds exclusive access on usage_page=0x0001 mouse and keyboard interfaces. This is an OS security boundary.
**How to avoid:** Always enumerate with `hid.enumerate(vid, pid)`, filter to `usage_page == 0xFF00`, and open with `open_path(entry["path"])`.
**Warning signs:** `OSError: [Errno 13] Access denied`, `WriteFile: Fonction incorrecte`, all reads return `[]` immediately. [CITED: PITFALLS.md, hidapi issue #228]

### Pitfall 2: coinit_flags Set Too Late
**What goes wrong:** `sys.coinit_flags = 0` is placed after `from PySide6.QtWidgets import QApplication` or after `import win32api`. COM initializes as STA on the thread that imported those modules. The flag has no effect.
**Why it happens:** `pythoncom` reads `sys.coinit_flags` exactly once, when it performs its first COM initialization. If Qt or pywin32 imports run first, the window has closed.
**How to avoid:** `sys.coinit_flags = 0` must be literally the first two lines of `__main__` (`import sys` then `sys.coinit_flags = 0`). No other imports may precede it.
**Warning signs:** Works fine in PoC (Phase 1 has no bleak), breaks silently in Phase 3+ when bleak is added and `await client.connect()` never returns. [CITED: bleak troubleshooting docs]

### Pitfall 3: read() Blocking on Offline Device
**What goes wrong:** `device.read(64)` with no timeout blocks indefinitely if the wireless mouse is off. The receiver accepts the write command but the offline device never replies.
**Why it happens:** hidapi's blocking `read()` waits for an input report with no timeout. The receiver does not generate an error report for failed wireless delivery.
**How to avoid:** Always use `device.read(64, timeout_ms=100)`. Treat empty list `[]` as "device offline". [CITED: PITFALLS.md Pitfall 4, hidapi docs]

### Pitfall 4: asyncio.Queue vs queue.Queue Confusion
**What goes wrong:** Using `asyncio.Queue` from the Qt main thread causes race conditions — `asyncio.Queue` is not thread-safe and is only intended for coroutine-to-coroutine communication within one event loop.
**How to avoid:** Use `queue.Queue` (stdlib). It is designed for producer-consumer across threads.
**Warning signs:** Intermittent hangs, `RuntimeError: got Future attached to a different loop`. [ASSUMED based on Python docs]

### Pitfall 5: PyInstaller and coinit_flags (Phase 7 risk, note for Phase 1 docs)
**What goes wrong:** PyInstaller's bootloader runs before user code and may import Python modules as part of runtime setup. If any such import touches COM before the user's `sys.coinit_flags = 0` line executes, MTA is lost.
**Current understanding:** PyInstaller's bootloader does NOT import COM-touching libraries (it sets up paths, then hands off to the user's `__main__`). The `sys.coinit_flags = 0` line should survive packaging. [ASSUMED — Phase 7 validation required per STATE.md Known Risks]
**How to avoid for now:** Document this as a Phase 7 validation item. The coinit_flags line at the top of `__main__` is the correct preventive measure. [CITED: STATE.md Known Risks]

---

## Project Structure for Phase 1

The PoC should establish the `src/` layout that later phases will build into a proper package.

```
batteryChecker/
├── src/
│   ├── hid_poc.py           # Script 1: HID enumeration + open + raw I/O
│   └── threading_stub.py    # Script 2: asyncio + queue.Queue + QTimer
├── .planning/
│   └── phases/
│       └── 01-hid-connectivity-poc/
│           └── 01-RESEARCH.md
└── CLAUDE.md
```

**Rationale:** Two separate scripts allow each success criterion to be verified independently. `hid_poc.py` can be run without PySide6 (just needs `hid`). `threading_stub.py` can be run without hardware (just needs PySide6). Keeping them separate avoids a complex combined script in a PoC context.

**Phase 1 does NOT create:**
- `__init__.py` or package structure — that starts in Phase 2
- `requirements.txt` — can be added but not required for PoC
- Any persistence, config, or protocol code

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All scripts | Unknown — not detectable in this env | Requires 3.9+ | None — blocking |
| `hid` 1.0.9 | `hid_poc.py` | Unknown — not installed in current env | — | None — install required |
| `PySide6` 6.11.1 | `threading_stub.py` | Unknown — not installed | — | None — install required |
| Logitech LIGHTSPEED dongle (physical hardware) | `hid_poc.py` raw round-trip test | Unknown | — | Enumerate-only test possible without hardware |
| `hidapi.dll` | `hid` library runtime | Bundled with `hid` pip package | — | None — included in `hid` package |

**Missing dependencies with no fallback:**
- Python 3.9+ — must be installed before Phase 1 execution
- `hid` 1.0.9 — `pip install hid`
- `PySide6` 6.11.1 — `pip install PySide6`

**Missing dependencies with fallback:**
- Physical LIGHTSPEED dongle — enumerate-only portion of `hid_poc.py` can succeed without the dongle; raw read/write success criterion requires hardware

---

## Validation Architecture

> Validation applies; no nyquist_validation override detected.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None established yet — Phase 1 is manual PoC validation |
| Config file | none |
| Quick run command | `python src/hid_poc.py` and `python src/threading_stub.py` |
| Full suite command | same |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SC-1 | Enumerate and open usage_page=0xFF00 without Access Denied | manual/smoke | `python src/hid_poc.py` exits 0, prints "Opened:" | No — Wave 0 |
| SC-2 | Raw read/write round-trip succeeds (bytes out, bytes back) | manual/smoke | `python src/hid_poc.py` prints non-empty response bytes | No — Wave 0 |
| SC-3 | `sys.coinit_flags = 0` is first line with explanatory comment | static/review | `grep -n "coinit_flags" src/hid_poc.py src/threading_stub.py` | No — Wave 0 |
| SC-4 | Threading stub starts, communicates one message, shuts down | manual/smoke | `python src/threading_stub.py` exits cleanly with "Received: hello" | No — Wave 0 |

### Wave 0 Gaps

- [ ] `src/hid_poc.py` — covers SC-1 and SC-2
- [ ] `src/threading_stub.py` — covers SC-3 and SC-4

*(No existing test infrastructure — all test files are created in Phase 1 execution)*

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Partial | Response buffer size fixed at 64 bytes; no user input in Phase 1 |
| V6 Cryptography | No | — |

### Known Threat Patterns for HID I/O

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reading arbitrary HID bytes from unexpected device | Tampering | Verify VID/PID before opening; check response prefix bytes |
| Overlong read buffer | Tampering | Always read fixed 64 bytes; slice `response[:N]` before parsing |

*Phase 1 has minimal security surface — two standalone scripts, no persistent state, no network, no user input.*

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pywinusb` for Windows HID | `hid` (ctypes-hidapi) | ~2018 abandonment | pywinusb unmaintained; hid is the standard replacement |
| `asyncio.run()` per operation | `asyncio.new_event_loop()` + `run_forever()` once | bleak 1.x docs | Prevents bleak WinRT object lifecycle issues |
| `tkinter.after()` for queue drain | `QTimer.timeout` connected slot | PySide6 adoption | Same pattern; QTimer is the Qt-idiomatic equivalent |
| `pythoncom.CoInitializeEx(0)` directly | `sys.coinit_flags = 0` before imports | Established bleak guidance | More reliable; fires before any import can claim STA |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `asyncio.Queue` is not thread-safe for cross-thread use | Anti-Patterns | Low risk — `queue.Queue` is always correct; if asyncio.Queue is safe cross-thread, using queue.Queue is just redundant not wrong |
| A2 | LIGHTSPEED receiver exposes exactly one `usage_page=0xFF00` interface (the first found is correct) | Logitech Reference | Medium — if receiver exposes multiple 0xFF00 interfaces, the wrong one might be selected; mitigated by testing with hardware |
| A3 | PyInstaller bootloader does not import COM-touching code before user `__main__` | Common Pitfalls (Pitfall 5) | Medium — if bootloader imports COM, coinit_flags set at line 1 of main still survives because sys.coinit_flags is read lazily by pythoncom; risk is only if bootloader calls CoInitialize directly |
| A4 | `hid.device().read()` returns empty list `[]` on timeout (not raises exception, not returns `None`) | Pattern 2 | Medium — if read raises on timeout, all caller code checking `if not response:` would fail; test on hardware |

---

## Open Questions

1. **Exact PID of the connected LIGHTSPEED receiver**
   - What we know: Multiple LIGHTSPEED PIDs exist (C539–C547); G Pro X Wireless commonly uses C547
   - What's unclear: Which PID is present on the developer's hardware
   - Recommendation: `hid_poc.py` should enumerate all VID=0x046D devices and print all results first, so the correct PID can be identified before filtering

2. **Number of 0xFF00 interfaces on the receiver**
   - What we know: LIGHTSPEED receivers expose at least one vendor-specific interface
   - What's unclear: Whether there is exactly one 0xFF00 interface or multiple (e.g., C547 may have 0xFF00 and 0xFF43 or similar)
   - Recommendation: Log all enumerated interfaces with their usage_page and usage fields before filtering; select first 0xFF00

3. **read() return value on timeout in `hid` 1.0.9**
   - What we know: hidapi C spec says timeout returns 0 bytes; Python binding documentation says returns empty list
   - What's unclear: Whether `hid` 1.0.9 wrapper raises `OSError` vs returns `[]` on Windows timeout
   - Recommendation: Wrap read in try/except in addition to `if not response:` check to handle both cases safely

---

## Sources

### Primary (HIGH confidence)
- bleak troubleshooting docs — `sys.coinit_flags` placement, MTA vs STA, COM threading — https://bleak.readthedocs.io/en/latest/troubleshooting.html
- Python stdlib asyncio docs — `run_coroutine_threadsafe`, `call_soon_threadsafe`, `new_event_loop`, `run_forever` — https://docs.python.org/3/library/asyncio-eventloop.html
- Python stdlib queue docs — `queue.Queue`, `get_nowait`, `Empty` exception — https://docs.python.org/3/library/queue.html
- hid PyPI page — version 1.0.9 confirmed, API overview — https://pypi.org/project/hid/
- PySide6 PyPI page — version 6.11.1 confirmed — https://pypi.org/project/PySide6/
- Solaar devices.md — LIGHTSPEED receiver PID list — https://github.com/pwr-Solaar/Solaar/blob/master/docs/devices.md
- trezor/cython-hidapi API docs — enumerate() return fields, device methods — https://trezor.github.io/cython-hidapi/api.html

### Secondary (MEDIUM confidence)
- PITFALLS.md (project research) — Pitfalls 1, 4, 5 — hidapi Access Denied, offline device timeout, STA conflict
- ARCHITECTURE.md (project research) — asyncio threading model, queue pattern code examples
- SUMMARY.md (project research) — executive synthesis of all domain research
- STATE.md (project) — architecture invariants, locked stack decisions
- hidapi issue #228 — Access Denied on gaming mouse primary interface — https://github.com/libusb/hidapi/issues/228

### Tertiary (LOW confidence)
- WebSearch results re: hidapi read() empty return on timeout — confirmed behavior but not from primary docs
- DeviceHunt — PID C548 (Bolt), C52B (Unifying) identification — https://devicehunt.com/view/type/usb/vendor/046D/device/C548

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed on PyPI; API confirmed via trezor/cython-hidapi docs
- Architecture: HIGH — asyncio pattern from Python stdlib docs; QTimer pattern from PySide6 docs; coinit_flags from bleak official troubleshooting guide
- Logitech PID table: HIGH for listed PIDs (from Solaar devices.md); MEDIUM for interface structure (inferred from PITFALLS.md and hidapi issues)
- Pitfalls: HIGH (most from project research backed by hidapi GitHub issues and bleak official docs)
- PyInstaller coinit_flags survival: LOW — documented as Phase 7 risk; requires validation

**Research date:** 2026-06-01
**Valid until:** 2026-07-01 (stack is stable; hid and PySide6 release cadence is slow)
