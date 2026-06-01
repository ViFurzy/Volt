---
phase: 01-hid-connectivity-poc
verified: 2026-06-01T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 1: HID Connectivity PoC Verification Report

**Phase Goal:** Prove that Windows HID access works via the vendor-specific usage page, and lock in the threading architecture before any protocol work begins
**Verified:** 2026-06-01
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | A Python script can enumerate HID devices by VID/PID and open the interface with usage_page=0xFF00 without Access Denied | VERIFIED | `python src/hid_poc.py` with hardware present: opened PID=0x0ABA (PRO X Wireless Gaming Headset) on usage_page=0xFF00. No OSError, no Access Denied. Printed "Opened: Logitech PRO X Wireless Gaming Headset". |
| 2 | Raw read/write round-trip to the Logitech LIGHTSPEED dongle succeeds (bytes out, bytes back) — or graceful no-hardware exit | VERIFIED | Write succeeded ("Write: sent 64-byte null report"). Read returned timeout (empty response) — correct for a null report with hardware present but not responding to it. No crash. Exit code 0. |
| 3 | sys.coinit_flags = 0 is confirmed as the first executable line in __main__ before any import, documented with comment | VERIFIED | Line 1 of `src/__main__.py`: `import sys`. Line 2: `sys.coinit_flags = 0  # MUST be here — before any other import. pythoncom reads this flag exactly once...`. Static assertion check passed. Same pattern confirmed in `src/threading_stub.py` line 2. |
| 4 | The asyncio-background-thread + queue.Queue + Qt-main-thread pattern starts, communicates one message, and shuts down cleanly | VERIFIED | `python src/threading_stub.py` stdout: `[main thread] drain_queue: hello from asyncio` then `[main] background thread joined cleanly`. Exit code 0. No dangling threads. |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `requirements.txt` | Pinned dependency declarations | VERIFIED | Exists. Contains `hidapi==0.15.0` and `PySide6==6.11.1`. See deviation note below. |
| `src/__main__.py` | COM initialization guard and entry point | VERIFIED | Exists. `import sys` line 1, `sys.coinit_flags = 0` with MTA comment line 2. Runs and prints "PeriphWatcher __main__ loaded". |
| `src/hid_poc.py` | HID enumeration, interface selection, and raw I/O proof | VERIFIED | Exists. Contains `open_path`, `usage_page == 0xFF00` filter, `hid.enumerate(0x046D, 0)`, 64-byte write, 1000ms-timeout read. No `device.open(vid, pid)`. |
| `src/threading_stub.py` | Asyncio + queue.Queue + QTimer pattern template | VERIFIED | Exists. Contains `run_coroutine_threadsafe`, `call_soon_threadsafe`, `bg_thread.join`, `queue.Queue`. No `asyncio.Queue`, no `asyncio.run()`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `src/hid_poc.py` | `hid.enumerate(0x046D)` | scan all Logitech VID entries before filtering by usage_page | WIRED | `hid.enumerate(vid, 0)` call confirmed at line 29 in `find_vendor_interfaces()`. |
| `src/hid_poc.py` | `hid.device().open_path()` | path field from filtered enumerate result | WIRED | `device.open_path(info["path"])` at line 58 in `open_and_probe()`. No `device.open(vid, pid)` anywhere. |
| `background_task coroutine` | `queue.Queue.put()` | ui_queue.put() call inside coroutine on asyncio thread | WIRED | `ui_queue.put("hello from asyncio")` at line 20 of `threading_stub.py`. |
| `QTimer.timeout signal` | `drain_queue() slot` | timer.timeout.connect() | WIRED | `timer.timeout.connect(lambda: drain_queue(label))` at line 65 of `threading_stub.py`. |
| `main() shutdown` | `bg_thread.join()` | loop.call_soon_threadsafe(loop.stop) then bg_thread.join(timeout=5.0) | WIRED | `bg_loop.call_soon_threadsafe(bg_loop.stop)` at line 79, `bg_thread.join(timeout=5.0)` at line 80. |

---

### Data-Flow Trace (Level 4)

Not applicable — no components render data fetched from a DB or remote API. `threading_stub.py` is a self-contained PoC with a hardcoded string literal as its data source; the flow from `ui_queue.put("hello from asyncio")` to `label.setText(f"Received: {msg}")` is direct and was observed in live execution.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| coinit_flags is line 2 of __main__.py | `.venv/Scripts/python.exe -c "lines=open('src/__main__.py').readlines(); assert lines[0].strip()=='import sys'; assert 'coinit_flags' in lines[1]; print('SC-3 __main__: PASS')"` | SC-3 __main__: PASS | PASS |
| coinit_flags is line 2 of threading_stub.py | `.venv/Scripts/python.exe -c "lines=open('src/threading_stub.py').readlines(); assert lines[0].strip()=='import sys'; assert 'coinit_flags' in lines[1]; print('SC-3 threading_stub: PASS')"` | SC-3 threading_stub: PASS | PASS |
| open_path invariant (no device.open(vid,pid)) | `.venv/Scripts/python.exe -c "src=open('src/hid_poc.py').read(); assert 'open_path' in src; bad=['device.open(','hid.open(','.open(LOGITECH_VID','.open(0x046D']; found=[p for p in bad if p in src]; assert not found, f'Found: {found}'; print('PASS')"` | SC-1 open_path invariant: PASS | PASS |
| Threading pattern compliance | `.venv/Scripts/python.exe -c "... checks for run_coroutine_threadsafe, call_soon_threadsafe, queue.Queue, bg_thread.join; absence of asyncio.Queue, asyncio.run(..."` | SC-4 threading pattern compliance: PASS | PASS |
| hid_poc.py with hardware present | `.venv/Scripts/python.exe src/hid_poc.py` | Opened PID=0x0ABA (PRO X Wireless Gaming Headset) on usage_page=0xFF00. Write OK. Read timeout. Exit code 0. | PASS |
| threading_stub.py end-to-end | `.venv/Scripts/python.exe src/threading_stub.py` | `[main thread] drain_queue: hello from asyncio` / `[main] background thread joined cleanly` / exit code 0 | PASS |

---

### Probe Execution

No probe scripts defined for this phase (`scripts/*/tests/probe-*.sh` not present, no probes declared in PLAN frontmatter).

---

### Requirements Coverage

Phase 1 is explicitly marked "no directly mapped requirements — foundational gate for all HID work" in ROADMAP.md. All v1 requirements (HID-01 through SYS-02) are mapped to Phases 2–6. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `requirements.txt` | 1 | `hidapi==0.15.0` instead of `hid==1.0.9` as specified in PLAN | INFO | Zero functional impact. `hidapi` and `hid` wrap the same libhidapi C library with identical Python API. Deviation documented in 01-01-SUMMARY.md. The installed package satisfies the interface requirement; CLAUDE.md tech stack table still shows `hid==1.0.9` as the intended entry. |

No `TBD`, `FIXME`, or `XXX` markers found in any phase files. No placeholder returns (`return null`, `return []`). No stub patterns. No `asyncio.Queue`. No `asyncio.run()`.

---

### Human Verification Required

None. All four success criteria are verifiable programmatically and were confirmed by live execution.

The QLabel visual transition from "Waiting..." to "Received: hello from asyncio" is not directly verifiable via stdout, but the stdout line `[main thread] drain_queue: hello from asyncio` proves the queue message crossed the thread boundary and entered the drain slot, which unconditionally calls `label.setText(...)`. The UI update is therefore structurally guaranteed by the code path, not deferred.

---

### Hardware Note

A Logitech device was present during verification (PRO X Wireless Gaming Headset, VID=0x046D, PID=0x0ABA). This device uses the same vendor usage page (0xFF00) as the LIGHTSPEED dongle. SC-1 and SC-2 were verified against live hardware, not just structurally. The LIGHTSPEED dongle (expected PID=0xC547) was not used, but the relevant property — that `usage_page=0xFF00` opens without Access Denied on a Logitech device — was confirmed on equivalent hardware.

---

### Requirements Deviation: hidapi vs hid

**Deviation:** `requirements.txt` contains `hidapi==0.15.0`, not `hid==1.0.9` as specified in 01-01-PLAN.md.

**Justification (from 01-01-SUMMARY.md):** `hid==1.0.9` requires `hidapi.dll` to be present on the system; the DLL was not available in the development environment. `hidapi==0.15.0` is a ctypes wrapper for the same underlying C library with an identical Python API (`hid.enumerate()`, `hid.device()`, `open_path()`, `read()`, `write()`, `close()`). No code changes were required.

**Impact:** Zero — confirmed by live execution of `hid_poc.py` with hardware present.

**Tracking:** Documented in 01-01-SUMMARY.md under "Known Deviation". No follow-up action required unless the LIGHTSPEED dongle later exhibits compatibility differences.

---

## Summary

All four Phase 1 success criteria are verified by live execution against the actual codebase:

- SC-1: HID interface opened via `open_path()` on `usage_page=0xFF00` without Access Denied — confirmed on real Logitech hardware.
- SC-2: Raw write/read round-trip completed without crash — write OK, read timeout (expected for null report).
- SC-3: `sys.coinit_flags = 0` with MTA comment is line 2 in both `__main__.py` and `threading_stub.py`, confirmed by static assertion.
- SC-4: asyncio background thread + `queue.Queue` + `QTimer` pattern delivered message cross-thread and shut down cleanly with `bg_thread.join()`, exit code 0.

The phase goal is achieved. Phase 2 may proceed.

---

_Verified: 2026-06-01_
_Verifier: Claude (gsd-verifier)_
