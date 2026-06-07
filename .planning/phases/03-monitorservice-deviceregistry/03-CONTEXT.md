# Phase 3: MonitorService + DeviceRegistry - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Battery data flows automatically from HID background polling to a UI-consumable queue;
hot-plug events trigger device discovery and teardown without user action.

Scope: MonitorService (asyncio bg thread, 60s polling loop), DeviceRegistry (thread-safe
store), hot-plug detection (WM_DEVICECHANGE via Qt main thread), queue-based updates to
mock UI consumer. Full Qt UI is Phase 4.

Out of scope: real UI window, system tray, notifications, SteelSeries backend.
</domain>

<decisions>
## Implementation Decisions

### DeviceState shape
- **D-01:** DeviceState is a full snapshot dataclass with fields: `vid` (int), `pid` (int),
  `dev_idx` (int), `device_name` (str), `percent` (int | None), `charging` (bool),
  `status` (DeviceStatus enum).
- **D-02:** Queue carries full DeviceState snapshots, not diffs. Consumer (QTimer drain)
  always has the complete current state of a device — no need to merge deltas.
- **D-03:** DeviceStatus enum has three values: `ONLINE`, `OFFLINE`, `CHARGING`.
  `charging=True` maps to `status=CHARGING`; `charging=False` + reachable maps to `ONLINE`;
  unreachable maps to `OFFLINE`.

### VID/PID known-device registry
- **D-04:** Known devices are a hardcoded dict in Python:
  `KNOWN_DEVICES = {(0x046D, 0x0ABA): "G Pro X Wireless"}`.
  Phase 5 adds SteelSeries by adding an entry to this dict. No config file or JSON needed
  until multiple users need to customise the list.
- **D-05:** `device_name` in DeviceState comes from `KNOWN_DEVICES` lookup (not
  `hid.enumerate` product_string), so the name is stable across firmware updates.

### Hot-plug reception
- **D-06:** WM_DEVICECHANGE is received on the Qt main thread. MonitorService creates a
  hidden `QWidget` (never shown) solely to obtain a Win32 HWND for
  `RegisterDeviceNotification`. The notification callback runs on the Qt main thread's
  message loop and calls `asyncio.run_coroutine_threadsafe()` to post a discovery job
  to the asyncio bg loop.
- **D-07:** This hidden widget is a Phase 3 placeholder. Phase 4 replaces it with the
  real application window as the HWND owner.
- **D-08:** 500ms debounce on WM_DEVICECHANGE before re-scanning: schedule a
  `loop.call_later(0.5, _rescan)` and cancel/reschedule on each repeat event.
  WM_DEVICECHANGE (DBT_DEVNODES_CHANGED) fires 5-6x per plug event — without debounce,
  MonitorService would attempt 5-6 simultaneous re-discoveries.

### Claude's Discretion
- DeviceRegistry thread-safety mechanism: choose between `threading.Lock` around a plain
  dict, or making all writes bg-thread-only with main thread reading only via queue. Either
  is acceptable; pick whichever matches the existing patterns from `threading_stub.py`.
- Polling failure handling: if `battery_probe_chain` returns None mid-session (device turned
  off during poll), push `DeviceState(..., status=OFFLINE)` to queue. Wait for next
  WM_DEVICECHANGE (plug) before attempting re-open — don't keep hammering a closed handle.
- Queue drain interval: `threading_stub.py` uses 500ms QTimer. Keep that cadence for Phase 3.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Threading pattern
- `src/threading_stub.py` — Canonical asyncio bg thread + queue.Queue + QTimer drain pattern.
  Phase 3 MonitorService extends this pattern — read before designing the service class.

### HID backend (Phase 2 outputs)
- `src/hidpp/receiver.py` — `find_receiver()`, `open_receiver()`, `discover_device_index()`.
  Note: `find_receiver()` has unconditional `print()` calls — add `verbose=False` parameter
  before using in background polling (code review finding WR-03).
- `src/hidpp/features.py` — `battery_probe_chain(device, device_idx)` → `BatteryResult | None`.
  `BatteryResult` has `percent`, `charging`, `feature_used`.

### Architecture invariants
- `CLAUDE.md` §Architecture Invariants — all HID I/O on bg thread, queue-only cross-thread
  communication, sys.coinit_flags = 0 first in __main__.

### Prior phase summaries
- `.planning/phases/02-hidpp-20-protocol/02-04-SUMMARY.md` — Phase 2 proof of life output;
  confirms G Pro X protocol (0xFF43, 0x06/0x0D), DEVICE_IDX=0xFF, calibration curve.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `threading_stub.py`: `run_background(loop)`, `run_coroutine_threadsafe()` pattern — copy
  directly into MonitorService. The `drain_queue(label)` function becomes the Phase 4 UI
  callback; Phase 3 uses a mock consumer for testing.
- `hidpp/receiver.py`: `find_receiver()` + `open_receiver()` — MonitorService calls these
  on hot-plug discovery after filtering against `KNOWN_DEVICES`.
- `hidpp/features.py`: `battery_probe_chain(device, 0xFF)` — the polling call.

### Established Patterns
- `queue.Queue` at module level, shared between threads (from `threading_stub.py` line 14).
- `asyncio.new_event_loop()` + `threading.Thread(daemon=True)` — background thread launch
  pattern (threading_stub.py lines 55-56).
- `loop.call_soon_threadsafe(loop.stop)` for clean shutdown.
- `QTimer.timeout.connect(drain_fn)` at 500ms for queue polling.

### Integration Points
- MonitorService's `asyncio bg loop` ← `run_coroutine_threadsafe()` ← Qt main thread
  WM_DEVICECHANGE callback (new in Phase 3).
- `ui_queue.put(DeviceState)` from bg thread → `QTimer.drain_queue()` on main thread.
- Phase 4 wires `drain_queue()` to the real device card UI; Phase 3 proves the pipe works
  with a mock consumer (print/assertion).
</code_context>

<specifics>
## Specific Ideas

No specific UI references — Phase 3 is pure backend with a mock consumer.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 03-monitorservice-deviceregistry*
*Context gathered: 2026-06-02*
