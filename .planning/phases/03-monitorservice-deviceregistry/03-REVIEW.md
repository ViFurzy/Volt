---
phase: 03-monitorservice-deviceregistry
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - src/monitor/__init__.py
  - src/monitor/state.py
  - src/monitor/registry.py
  - src/monitor/service.py
  - src/monitor/hotplug.py
  - src/monitor/app.py
  - src/run_monitor.py
  - tests/test_registry.py
  - tests/test_service.py
  - tests/test_hotplug.py
  - tests/test_integration.py
findings:
  critical: 3
  warning: 5
  info: 0
  total: 8
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-02
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

The registry, drain loop, and debounce logic are structurally sound. Three critical
defects exist: a data race in `stop()` (main thread mutates `self._open` concurrently
with the asyncio bg thread), a logical error in `_fire_rescan()` (schedules a new
concurrent coroutine while the poll loop may already be inside `discover()`), and a
PySide6 API misuse in `nativeEvent` that reads garbage bytes from the Win32 MSG pointer
on recent Qt versions. Several warnings concern the mutable "immutable" snapshot
dataclass, an async teardown ordering problem, and test reliability on path assumptions.

---

## Critical Issues

### CR-01: Data race — `stop()` mutates `self._open` from the Qt main thread

**File:** `src/monitor/service.py:82-87`

**Issue:** `stop()` is a plain method called from the Qt main thread (see
`run_monitor.py:46`). Lines 82–87 iterate over `self._open.values()`, close each
handle, and call `self._open.clear()`. The asyncio bg thread accesses and mutates
`self._open` inside `discover()` (lines 139-148, 163-175) and `poll_once()`
(lines 184-196). There is no lock or atomic hand-off protecting `self._open`. This
is an unsynchronised concurrent dict mutation: the main thread's clear/iteration and
the bg thread's del/insert can corrupt CPython's dict internal state, cause skipped
entries, or close a handle that the bg thread is mid-read on.

The `call_soon_threadsafe(self._poll_task.cancel)` posted on line 81 is delivered
asynchronously — the task is not actually cancelled before lines 82-87 execute.

**Fix:** Move all handle teardown onto the asyncio loop so `self._open` is only
ever touched from the bg thread:

```python
def stop(self) -> None:
    if self._poll_task is not None:
        self._loop.call_soon_threadsafe(self._poll_task.cancel)
    # Schedule teardown on the loop itself so self._open is only touched by the bg thread
    self._loop.call_soon_threadsafe(self._teardown_handles)
    self._loop.call_soon_threadsafe(self._loop.stop)
    if self._thread is not None and self._thread.is_alive():
        self._thread.join(timeout=5.0)

def _teardown_handles(self) -> None:
    """Close all open HID handles. Runs on the asyncio loop."""
    for handle in list(self._open.values()):
        try:
            handle.close()
        except Exception:
            pass
    self._open.clear()
```

---

### CR-02: `_fire_rescan()` calls `run_coroutine_threadsafe` from inside the asyncio loop — creates concurrent `discover()` coroutines that race on `self._open`

**File:** `src/monitor/hotplug.py:181-183` / `src/monitor/service.py:92-98`

**Issue:** `_Debouncer._fire()` runs on the asyncio event loop (it is posted by
`call_later`, which runs callbacks on the loop). It calls `self._service.rescan()`,
which calls `asyncio.run_coroutine_threadsafe(self.discover(), self._loop)`.
`run_coroutine_threadsafe` is safe to call from *outside* the loop; called from
*inside* the loop it still works mechanically (it posts a `call_soon_threadsafe`),
but more importantly it creates a second independent `discover()` coroutine that
can run concurrently with the `_poll_loop` coroutine which may itself be inside
`discover()` at that moment. Both coroutines mutate `self._open` (deletions at
lines 148, 163; insertions at lines 174-175) without any serialisation.

The correct pattern for "schedule a coroutine from within the running loop" is
`asyncio.ensure_future` or `loop.create_task`. But the real fix is to make
`_fire_rescan` schedule discover via `ensure_future` so it runs sequentially with
the poll task, or to use an asyncio `Event` that the `_poll_loop` polls.

**Fix:** In `hotplug.py`, have `_fire_rescan` post a `call_soon` (not
`run_coroutine_threadsafe`) so the discover coroutine is scheduled as a Task that
shares the event loop's serial execution:

```python
# hotplug.py
def _fire_rescan(self) -> None:
    """Runs on the asyncio loop; schedules discover() as a new Task."""
    asyncio.ensure_future(self._service.discover(), loop=self._service._loop)
```

And simplify `MonitorService.rescan()` consistently:

```python
# service.py — for calls from Qt main thread (the intended use case)
def rescan(self) -> None:
    self._loop.call_soon_threadsafe(
        lambda: asyncio.ensure_future(self.discover(), loop=self._loop)
    )
```

Note: even with `ensure_future`, concurrent `discover()` tasks can still interleave
at every `await`. The cleanest fix is a serialising lock (`asyncio.Lock`) guarding
`self._open` mutations, or a dedicated "rescan requested" flag checked at the top
of `_poll_loop`.

---

### CR-03: `nativeEvent` decodes the `message` argument unsafely — reads garbage bytes on PySide6 6.x

**File:** `src/monitor/hotplug.py:160-166`

**Issue:** In PySide6 (all versions including 6.x used by this project), the second
argument to `nativeEvent` is a `sip.voidptr` object, not a raw integer. The code
calls `int(message)` to extract the address and passes it to
`ctypes.wintypes.MSG.from_address()`. The bug is that PySide6's `nativeEvent` does
NOT pass a pointer to a `MSG` struct as the `message` parameter — it passes a
platform-specific message object. On Windows / Qt 6, the `message` argument is a
`MSG *` (a pointer to a `MSG`). Calling `ctypes.wintypes.MSG.from_address(int(message))`
dereferences that pointer and reads the `MSG` struct, which is correct in theory.

However, `ctypes.wintypes.MSG` has a `wParam` field typed as `WPARAM` (alias for
`c_ulong` on 32-bit, `c_ulonglong` on 64-bit). On a 64-bit process the struct size
and field offsets depend on the exact ctypes definition; if `ctypes.wintypes.MSG`
field sizes are wrong or the pointer arithmetic drifts by one field, `msg.message`
and `msg.wParam` silently read from wrong offsets. The correct and PySide6-documented
approach is to use `ctypes.cast` with a proper pointer type, or to use
`ctypes.Structure.from_address` only after verifying the struct layout matches the
Win32 `MSG` layout exactly.

Additionally, `ctypes.get_last_error()` in `register()` (line 142) is only valid
immediately after the WinAPI call that sets it. If anything (even Python evaluation)
runs between the `RegisterDeviceNotificationW` call and `ctypes.get_last_error()`,
the error code may have been overwritten.

**Fix:** Use `ctypes.cast` with a pointer and verify you are reading the right field:

```python
_MSG_P = ctypes.POINTER(ctypes.wintypes.MSG)

def nativeEvent(self, eventType, message):
    if eventType == b"windows_generic_MSG":
        msg_ptr = ctypes.cast(int(message), _MSG_P)
        if msg_ptr[0].message == WM_DEVICECHANGE and msg_ptr[0].wParam == DBT_DEVNODES_CHANGED:
            self._schedule_rescan()
    return super().nativeEvent(eventType, message)
```

For `get_last_error`, capture it immediately after the API call:

```python
handle = ctypes.windll.user32.RegisterDeviceNotificationW(hwnd, ctypes.byref(notify_filter), flags)
err = ctypes.get_last_error()   # capture before any Python evaluation
if not handle:
    logger.error("RegisterDeviceNotificationW failed (error %d) — hot-plug disabled", err)
    return
```

---

## Warnings

### WR-01: `DeviceState` is mutable despite the "treat as immutable snapshot" contract

**File:** `src/monitor/state.py:26`

**Issue:** The docstring says consumers MUST treat instances as immutable snapshots.
The dataclass is declared without `frozen=True`, so Python does not enforce this.
Any code path that receives a `DeviceState` from the queue can accidentally mutate
it. If the registry still holds the same object (it stores whatever was passed to
`upsert`), mutation via one reference silently changes what the other holder sees.

**Fix:**

```python
@dataclass(frozen=True)
class DeviceState:
    ...
```

This makes all field assignments after construction raise `FrozenInstanceError` at
runtime, enforcing the immutability contract that `dataclasses.replace()` relies on.

---

### WR-02: `discover()` creates an ONLINE `DeviceState` with `percent=None` — contradicts the spec

**File:** `src/monitor/service.py:165-175`

**Issue:** When a new device is opened for the first time, `discover()` inserts an
initial state with `status=DeviceStatus.ONLINE` and `percent=None`. The `DeviceState`
docstring (state.py:33) explicitly says "`percent` is None when the device is OFFLINE
(no battery reading available)". An ONLINE device with `percent=None` is an invalid
state per the data model; any UI that tries to render `percent` without a None-guard
while assuming ONLINE devices have a reading will misbehave.

The initial state pushed by `discover()` is also enqueued to the UI immediately
(line 175) before `poll_once()` has been called, so the UI may show "online, no
reading" transiently.

**Fix:** Use `DeviceStatus.ONLINE` only after the first successful `poll_once()`.
Set the initial state to `DeviceStatus.OFFLINE` (or a new `CONNECTING` status) when
first opening a handle, and let `poll_once()` upgrade it to `ONLINE` on first
successful read:

```python
state = DeviceState(
    vid=vid, pid=pid, dev_idx=DEVICE_IDX, device_name=device_name,
    percent=None, charging=False,
    status=DeviceStatus.OFFLINE,   # will become ONLINE after first poll
)
```

---

### WR-03: `stop()` closes handles and stops the loop before the cancel propagates — may call into closed handles

**File:** `src/monitor/service.py:77-90`

**Issue:** Line 81 posts `_poll_task.cancel` via `call_soon_threadsafe`. This is
non-blocking: the cancel is queued but not yet delivered. Lines 82-87 then close all
handles and clear `self._open` on the main thread. Line 88 posts `self._loop.stop`.
The order in which the loop processes these two posted callbacks is:
`_poll_task.cancel` first (posted earlier), then `loop.stop` second. But between the
two, the loop may resume `_poll_loop` for one more iteration (if `asyncio.sleep` was
already done) and call `battery_probe_chain` on handles that have already been closed
by the main thread at line 82-87. This results in HID I/O on closed file handles.

This is closely related to CR-01; fixing CR-01 (moving handle teardown to the bg
thread via `_teardown_handles`) naturally fixes this ordering problem too.

---

### WR-04: `test_no_pyside6_import` and `test_no_hid_open_direct_call` use hardcoded relative paths — fragile

**File:** `tests/test_service.py:251-258`

**Issue:** Both safety-invariant tests open `"src/monitor/service.py"` as a relative
path. This path is only valid when pytest is run from the project root. If run from
`tests/` or any other directory (e.g., a CI runner with a different working
directory), `open("src/monitor/service.py")` / `pathlib.Path("src/monitor/service.py")`
will raise `FileNotFoundError`, which causes the test to error (not fail cleanly with
an assertion message). The safety invariant is silently not checked.

**Fix:** Use `pathlib.Path(__file__)` to anchor the path relative to the test file:

```python
import pathlib
SERVICE_PATH = pathlib.Path(__file__).parent.parent / "src" / "monitor" / "service.py"
source = SERVICE_PATH.read_text()
```

---

### WR-05: No test coverage for `MonitorService.stop()` / `start()` lifecycle

**File:** `tests/test_service.py` (gap)

**Issue:** `TestSafetyInvariants` checks source-level properties only. There is no
test that calls `service.start()` and `service.stop()` and verifies that the bg
thread exits cleanly, that `_open` is empty after stop, or that a second `stop()`
call does not raise. The `stop()` method contains the most dangerous cross-thread
code in the codebase (see CR-01, WR-03) and is entirely uncovered by the test suite.

**Fix:** Add lifecycle tests using a mocked `discover()` / `poll_once()` to exercise
start/stop without real hardware:

```python
def test_stop_joins_thread(mocker):
    mocker.patch("monitor.service.find_receiver", return_value=[])
    service = MonitorService(queue.Queue(), DeviceRegistry(), poll_interval=60.0)
    service.start()
    service.stop()
    assert service._thread is not None
    assert not service._thread.is_alive()
```

---

_Reviewed: 2026-06-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
