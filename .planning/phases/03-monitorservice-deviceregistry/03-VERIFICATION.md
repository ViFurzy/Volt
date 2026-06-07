---
phase: 03-monitorservice-deviceregistry
verified: 2026-06-02T18:00:00Z
status: human_needed
score: 13/13 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Plug in the Logitech LIGHTSPEED dongle with the G Pro X Wireless headset ON, then run `src/run_monitor.py`"
    expected: "ONLINE event appears within ~1s; exactly one discovery line (debounce collapsed 5-6 WM_DEVICECHANGE events); battery % appears within 60s"
    why_human: "WM_DEVICECHANGE reception on the Qt main thread requires a live Windows message pump — untestable via grep or unit tests. The 03-04 hardware checkpoint already passed, but formal sign-off is required by the gate."
  - test: "Unplug the dongle while run_monitor.py is running"
    expected: "OFFLINE update appears immediately (fast path in discover()/WM_DEVICECHANGE), not deferred to the next 60s poll cycle"
    why_human: "Real hot-plug event and timing behaviour cannot be verified without hardware."
  - test: "Press Ctrl+C to exit run_monitor.py"
    expected: "Clean shutdown with no 'Task was destroyed but it is pending!' asyncio warning and no hang"
    why_human: "Signal-handler + Qt event loop interaction requires a live process to verify."
---

# Phase 3: MonitorService + DeviceRegistry Verification Report

**Phase Goal:** Battery data flows automatically from background polling to a UI-consumable queue; hot-plug events trigger device discovery and teardown without user action
**Verified:** 2026-06-02T18:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Step 0: Previous Verification

No previous VERIFICATION.md found. Initial verification mode.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | MonitorService runs its polling loop on a daemon asyncio background thread | VERIFIED | `service.py:69` — `threading.Thread(target=self._run_loop, daemon=True)`; `_run_loop` sets event loop and calls `run_forever()` |
| 2 | discover() enumerates the receiver, filters against KNOWN_DEVICES, opens the device, and registers an ONLINE DeviceState | VERIFIED | `service.py:129-184` — calls `find_receiver(verbose=False)`, checks `(vid,pid) in KNOWN_DEVICES`, calls `open_receiver`, upserts `DeviceStatus.ONLINE` state, puts on queue |
| 3 | poll_once() reads battery via battery_probe_chain and pushes a full DeviceState snapshot to the queue | VERIFIED | `service.py:186-220` — iterates `self._open`, calls `battery_probe_chain(handle, dev_idx)`, builds full `DeviceState`, calls `self._ui_queue.put(state)` |
| 4 | A device that returns None mid-session is pushed as OFFLINE and its handle is released | VERIFIED | `service.py:196-205` — on `result is None`, calls `registry.mark_offline(key)`, puts OFFLINE state on queue, calls `handle.close()`, deletes from `self._open` |
| 5 | find_receiver supports verbose=False so background polling does not spam stdout | VERIFIED | `receiver.py:35` — `def find_receiver(vid: int = LOGITECH_VID, verbose: bool = True)`; three `print()` calls wrapped in `if verbose:` guards |
| 6 | HotPlugWatcher creates a hidden QWidget solely to obtain a Win32 HWND for RegisterDeviceNotification | VERIFIED | `hotplug.py:97-117` — `class HotPlugWatcher(QWidget)`, `super().__init__()`, never calls `.show()`, uses `int(self.winId())` in `register()` |
| 7 | WM_DEVICECHANGE with DBT_DEVNODES_CHANGED triggers a debounced rescan | VERIFIED | `hotplug.py:160-166` — `nativeEvent` checks `msg.message == WM_DEVICECHANGE and msg.wParam == DBT_DEVNODES_CHANGED`, then calls `self._schedule_rescan()` |
| 8 | Repeated WM_DEVICECHANGE events within 500ms collapse into a single rescan (cancel+reschedule) | VERIFIED | `hotplug.py:61-90` — `_Debouncer.schedule()` cancels `self._handle` before calling `call_later`; 5 rapid-call test passes (`test_five_rapid_calls_produce_one_callback`) |
| 9 | The debounced rescan calls MonitorService.rescan() which posts discover() to the asyncio loop via run_coroutine_threadsafe | VERIFIED | `hotplug.py:181-189` — `_fire_rescan` calls `asyncio.ensure_future(self._service.discover())`; `service.py:101-107` — `rescan()` calls `asyncio.run_coroutine_threadsafe(self.discover(), self._loop)` |
| 10 | MonitorService + DeviceRegistry + HotPlugWatcher are wired together behind a single entry point | VERIFIED | `app.py:26-96` — `MonitorApp.__init__` creates `DeviceRegistry`, `MonitorService`; `build_hotplug()` constructs and registers `HotPlugWatcher`; `make_timer()` connects drain; `run_monitor.py` wires all via `MonitorApp` |
| 11 | A QTimer on the main thread drains the queue every 500ms into a mock consumer | VERIFIED | `app.py:79-88` — `make_timer()` creates `QTimer`, connects `timeout` to `self.drain`, starts at `self._drain_ms` (default 500) |
| 12 | sys.coinit_flags = 0 is the first executable statement in the entry point before all imports | VERIFIED | `run_monitor.py:1-2` — `import sys` then `sys.coinit_flags = 0` on line 2, before all other imports; automated check passes |
| 13 | DeviceRegistry is thread-safe (threading.Lock around plain dict, all four methods lock-guarded) | VERIFIED | `registry.py:24-66` — `__init__` creates `threading.Lock`; all four methods (`upsert`, `get`, `all`, `mark_offline`) use `with self._lock:`; concurrency test with 10 threads x 100 upserts passes |

**Score:** 13/13 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/monitor/__init__.py` | Package marker | VERIFIED | Exists; docstring documents cross-thread invariant |
| `src/monitor/state.py` | DeviceState dataclass, DeviceStatus enum, KNOWN_DEVICES dict | VERIFIED | 52 lines; `DeviceStatus` has 3 members (ONLINE, OFFLINE, CHARGING via `enum.auto()`); `DeviceState` frozen dataclass with 7 locked fields; `KNOWN_DEVICES[(0x046D, 0x0ABA)] == "G Pro X Wireless"` |
| `src/monitor/registry.py` | DeviceRegistry thread-safe store | VERIFIED | 67 lines; `threading.Lock` guard on all 4 methods; `mark_offline` uses `dataclasses.replace()` |
| `src/monitor/service.py` | MonitorService asyncio polling engine | VERIFIED | 221 lines; daemon thread, discover, poll_once, rescan, start, stop; no PySide6, no hid.open() |
| `src/monitor/hotplug.py` | HotPlugWatcher hidden QWidget + _Debouncer | VERIFIED | 190 lines; `_Debouncer` extracted for Qt-free testability; all Win32 constants at module level |
| `src/monitor/app.py` | MonitorApp wiring layer | VERIFIED | 97 lines; wires all components; QTimer drain; no HID I/O |
| `src/run_monitor.py` | Standalone entry point with coinit guard | VERIFIED | 52 lines; coinit on line 2; mock_consumer; SIGINT handler; clean shutdown |
| `tests/test_registry.py` | Unit tests for state/registry | VERIFIED | 15 tests covering all behaviour including concurrency |
| `tests/test_service.py` | Unit tests for MonitorService | VERIFIED | 11 tests covering discover/poll mapping, safety invariants |
| `tests/test_hotplug.py` | Debounce logic tests | VERIFIED | 5 tests; _Debouncer driven on real asyncio loop, no Qt/Win32 required |
| `tests/test_integration.py` | Queue end-to-end test | VERIFIED | 5 tests; FIFO delivery, empty-queue safety, OFFLINE forwarding |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `registry.py` | `state.py` | `from monitor.state import DeviceState, DeviceStatus` | WIRED | `registry.py:14` |
| `service.py` | `hidpp/features.py` | `battery_probe_chain` call in poll_once | WIRED | `service.py:26` import; `service.py:195` call inside `poll_once` coroutine |
| `service.py` | `registry.py` | `registry.upsert` / `registry.mark_offline` | WIRED | `service.py:183,152,198,219` |
| `service.py` | `ui_queue` | `queue.put(DeviceState)` | WIRED | `service.py:152,184,200,220` |
| `hotplug.py` | `MonitorService.rescan` | debounced callback invokes `service.rescan()` or `ensure_future(service.discover())` | WIRED | `hotplug.py:189` — `asyncio.ensure_future(self._service.discover())`; `hotplug.py:179` — `call_soon_threadsafe(self._debouncer.schedule)` |
| `hotplug.py` | `RegisterDeviceNotificationW` | ctypes user32 call with HWND | WIRED | `hotplug.py:136` |
| `app.py` | `service.py` | `MonitorService(...)` instantiation + `start()` | WIRED | `app.py:50-51,91-92` |
| `app.py` | `ui_queue drain` | `QTimer.timeout` → `drain` → consumer | WIRED | `app.py:86-87` — `timer.timeout.connect(self.drain)` |
| `app.py` | `hotplug.py` | `HotPlugWatcher(service).register()` | WIRED | `app.py:61-62` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `service.py` / `poll_once` | `result` (BatteryResult) | `battery_probe_chain(handle, dev_idx)` on real HID handle | Yes — hardware-confirmed ~35-40% reading | FLOWING |
| `service.py` / `discover` | `interfaces` | `find_receiver(verbose=False)` → real HID enumeration | Yes — returns actual USB interface dicts | FLOWING |
| `app.py` / `drain` | `state` (DeviceState) | `ui_queue.get_nowait()` from background thread puts | Yes — queue filled by service polling coroutines | FLOWING |
| `registry.py` | `_devices` dict | `upsert(state)` from MonitorService coroutines | Yes — written by poll_once/discover on bg thread | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 62 tests pass | `.venv-1/Scripts/pytest -q --tb=no` | `62 passed in 1.09s` | PASS |
| Phase 3 tests (36) pass | `.venv-1/Scripts/pytest tests/test_registry.py tests/test_service.py tests/test_hotplug.py tests/test_integration.py -v` | `36 passed in 1.06s` | PASS |
| coinit_flags on line 2 | `python -c "t=open('src/run_monitor.py')..."` | `coinit-ok: line 2 is: 'sys.coinit_flags = 0 ...'` | PASS |
| No PySide6 in service.py | AST safety test (test_no_pyside6_import) | PASSED | PASS |
| No hid.open() in service.py | AST walk test (test_no_hid_open_direct_call) | PASSED | PASS |

---

### Probe Execution

Step 7c: SKIPPED — no probe scripts exist in `scripts/*/tests/probe-*.sh`. Hardware checkpoint was human-executed and approved in plan 03-04.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| HID-03 | 03-01, 03-02, 03-03, 03-04 | App auto-discovers known devices when their USB dongle is plugged in (built-in VID/PID registry, no user config required) | SATISFIED | `KNOWN_DEVICES` hardcoded dict; `discover()` filters against it; `HotPlugWatcher` triggers `rescan()` on plug; no config-file loader added |
| HID-04 | 03-02, 03-03, 03-04 | App detects when a dongle is unplugged and marks affected device as offline | SATISFIED | `discover()` fast-path marks handles gone from enumeration as OFFLINE immediately; `poll_once()` marks OFFLINE on None battery result; hardware-confirmed immediate OFFLINE on unplug |

No orphaned requirements: REQUIREMENTS.md maps both HID-03 and HID-04 to Phase 3, and both plans claim them.

---

### Anti-Patterns Found

Scan of all phase 3 source files (`src/monitor/*.py`, `src/run_monitor.py`):

| File | Line | Pattern | Severity | Impact |
|------|------|---------|---------|--------|
| `src/run_monitor.py` (mock_consumer) | 12-21 | `mock_consumer` prints to stdout — intentional Phase 3 stand-in | Info | Documented in plan 03-04 Known Stubs; Phase 4 replaces with real UI consumer. Not a blocker. |

No TBD, FIXME, XXX, TODO, HACK, or PLACEHOLDER markers found in any modified file. No empty return bodies. No hardcoded empty data passed to rendering paths.

---

### Human Verification Required

#### 1. Plug-in triggers single ONLINE discovery within ~1s

**Test:** Run `src/run_monitor.py` with the dongle unplugged, then plug in the G Pro X Wireless LIGHTSPEED dongle with the headset powered on.
**Expected:** Exactly one `[consumer] G Pro X Wireless | None% | ONLINE | charging=False` line appears within ~1 second. No duplicate discovery lines. Battery percentage appears on the next poll (~60s, or lower `poll_interval` for testing).
**Why human:** WM_DEVICECHANGE message-pump delivery and the 500ms debounce collapse require a live Windows process with a running Qt event loop. Unit tests cover _Debouncer logic in isolation; the real message pump path cannot be grepped.

#### 2. Unplug marks device OFFLINE immediately

**Test:** Unplug the dongle while run_monitor.py is running (after a successful ONLINE + battery reading).
**Expected:** `[consumer] G Pro X Wireless | None% | OFFLINE | charging=False` appears within the WM_DEVICECHANGE debounce window (~500ms), not deferred to the next 60s poll cycle.
**Why human:** The fast-path in `discover()` triggered by `WM_DEVICECHANGE` on unplug requires a real device change event. The 03-04 hardware checkpoint confirmed this; formal sign-off records it.

#### 3. Ctrl+C exits cleanly

**Test:** While run_monitor.py is running with a connected device, press Ctrl+C.
**Expected:** Clean exit with no `Task was destroyed but it is pending!` asyncio warning and no hang. The `stop()` method cancels `_poll_task` before stopping the loop.
**Why human:** Signal handling in a Qt event loop + asyncio background thread requires a live process. The 03-04 hardware checkpoint confirmed this behavior after fix commit `db92152`.

---

### Gaps Summary

No gaps found. All 13 must-have truths are verified in the codebase. Three human verification items remain — all are behavioral/runtime checks for hardware + OS interaction that cannot be satisfied programmatically. The 03-04 hardware checkpoint (approved, documented in SUMMARY) constitutes strong prior evidence that these will pass; formal sign-off is what elevates status from human_needed to passed.

---

_Verified: 2026-06-02T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
