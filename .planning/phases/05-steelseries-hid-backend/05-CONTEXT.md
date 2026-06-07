# Phase 5: SteelSeries HID Backend - Context

**Gathered:** 2026-06-04 (--auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Read battery level from the SteelSeries Aerox 5 Wireless via its 2.4GHz USB dongle using
raw proprietary HID. Wire the result into the existing MonitorService/DeviceRegistry pipeline
so the device appears as a live card in the main window alongside the Logitech device.

Out of scope: UI changes (Phase 4 already handles any DeviceState snapshot), notifications
(Phase 6), BLE backend (v2), any SteelSeries device other than Aerox 5 Wireless.
</domain>

<decisions>
## Implementation Decisions

### Module structure
- **D-01:** New `src/steelseries/` package with `__init__.py` and `driver.py`.
  `driver.py` exposes: `find_dongle()`, `open_dongle()`, `ss_battery_probe(device, dev_idx)`.
  This mirrors the `src/hidpp/receiver.py` + `src/hidpp/features.py` split and keeps the
  SteelSeries protocol completely isolated from the Logitech code.

### Backend dispatch in MonitorService
- **D-02:** Add a `DEVICE_PROBES: dict[tuple[int, int], callable]` registry in
  `src/monitor/state.py` alongside `KNOWN_DEVICES`. Keyed by `(vid, pid)`, value is the
  probe function `(device, dev_idx) -> BatteryResult | None`.
  `poll_once()` in `MonitorService` calls `DEVICE_PROBES[(vid, pid)](handle, dev_idx)`
  instead of the hardcoded `battery_probe_chain(...)`.
  Both `KNOWN_DEVICES` and `DEVICE_PROBES` are updated in the same file when adding the
  SteelSeries device — single place to register a new device.

- **D-03:** `ss_battery_probe` must return `BatteryResult | None` — same type as
  `battery_probe_chain`. `BatteryResult` already has `percent`, `voltage_mv`, `charging`,
  `feature_used`. SteelSeries doesn't use voltage; set `voltage_mv=0` for this backend.
  The smoothing deque in `MonitorService` uses `voltage_mv` — SteelSeries should bypass
  smoothing (or the deque fills with zeros, giving a misleading average). Add a flag or
  check: if `voltage_mv == 0`, use `result.percent` directly without smoothing.

### Protocol research strategy
- **D-04:** Use HeadsetControl and rivalcfg as the primary source for command bytes.
  HeadsetControl (GitHub: nickel110/HeadsetControl) contains battery query commands for
  many SteelSeries devices; rivalcfg (GitHub: flozz/rivalcfg) has the full SteelSeries
  HID protocol specification. Treat these as authoritative starting points, then verify
  on hardware before shipping.

### SteelSeries dongle interface selection
- **D-05:** The SteelSeries Aerox 5 Wireless 2.4GHz dongle exposes a vendor-specific HID
  interface. Expected usage_page: `0xFF00` (generic vendor, same invariant as Logitech's
  non-primary interface). If hardware probe reveals a different page (e.g., `0xFF06`),
  use whatever the dongle actually exposes — never open the primary mouse interface
  (`usage_page=0x0001`). The architecture invariant from CLAUDE.md holds for SteelSeries.

### Charging status
- **D-06:** Include `charging: bool` in `ss_battery_probe` result if the protocol exposes
  it. If the SteelSeries protocol does not report charging state, hardcode `charging=False`.
  BATT-02 is already satisfied for the Logitech device; omitting it for SteelSeries is
  acceptable for v1.

### Offline / zero-battery handling
- **D-07:** Reuse the same sentinel contract: `ss_battery_probe` returns `None` if the
  mouse is off or the dongle can't reach it. `MonitorService.poll_once()` already handles
  `result is None` → mark OFFLINE; no new code path needed. The `percent == 0` check also
  applies: a zero reading from SteelSeries is a transient power-down, not a real empty
  battery.

### Claude's Discretion
- Exact SteelSeries VID/PID constants (hardware research determines these)
- Device index value for the SteelSeries command (0x00, 0x01, or other — protocol research)
- Whether `find_dongle()` needs a `verbose` parameter (match Logitech's `verbose=False` default)
- Report ID and payload structure (fully determined by HeadsetControl/hardware probe)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Integration targets (existing code to wire into)
- `src/monitor/state.py` — `KNOWN_DEVICES`, `DeviceState`, `DeviceStatus`. Phase 5 adds
  `DEVICE_PROBES` dict here alongside `KNOWN_DEVICES`. Phase 5 adds SteelSeries VID/PID entry
  to both dicts.
- `src/monitor/service.py` — `MonitorService.poll_once()` hardcodes `battery_probe_chain`.
  Phase 5 changes this call to dispatch via `DEVICE_PROBES[(vid,pid)]`.
- `src/hidpp/features.py` — `BatteryResult` dataclass. `ss_battery_probe` must return the
  same type. Note: `voltage_mv` field added in latest session; SteelSeries sets it to 0.

### Pattern to mirror (Logitech backend)
- `src/hidpp/receiver.py` — `find_receiver()`, `open_receiver()` pattern. Phase 5 creates
  analogous `find_dongle()`, `open_dongle()` in `src/steelseries/driver.py`.
- `src/hidpp/features.py` — `battery_probe_chain(device, dev_idx)` → `BatteryResult | None`.
  Phase 5 creates analogous `ss_battery_probe(device, dev_idx)` → `BatteryResult | None`.

### Architecture invariants
- `CLAUDE.md` §Architecture Invariants — HID I/O on bg asyncio thread; open via
  `open_path()` after filtering by usage_page; never `hid.open(vid, pid)`.

### External protocol sources (researcher must consult)
- HeadsetControl project — battery query commands for SteelSeries devices
- rivalcfg project — SteelSeries HID protocol specification and report formats

### Voltage smoothing side-effect
- `src/monitor/service.py` lines with `_voltage_history` / `_VOLTAGE_WINDOW` — smoothing
  uses `result.voltage_mv`. SteelSeries returns `voltage_mv=0`; service must not smooth
  when voltage_mv is 0 (would average to 0 and corrupt the percent). Fix this in Phase 5.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/hidpp/receiver.py:open_receiver(info)` — `hid.device().open_path(info["path"])` pattern.
  `find_dongle()` and `open_dongle()` in `steelseries/driver.py` are near-copies.
- `src/monitor/service.py:discover()` — already handles multi-device iteration;
  adding SteelSeries to `KNOWN_DEVICES` automatically makes discovery find the dongle.
- `src/monitor/service.py:poll_once()` — only the probe call needs to change (D-02).

### Established Patterns
- `usage_page=0xFF??` vendor interface, opened via `open_path()` — never `hid.open(vid,pid)`.
- `battery_probe_chain` returns `BatteryResult | None`; `None` = offline.
- `DEVICE_IDX = 0xFF` is Logitech-specific. SteelSeries will have its own constant.
- Tests use `pytest-mock` to patch `battery_probe_chain` at `monitor.service` namespace.
  Phase 5 tests patch `monitor.service.DEVICE_PROBES` or the individual probe function.

### Integration Points
- `KNOWN_DEVICES` in `state.py` + new `DEVICE_PROBES` in `state.py` — add one entry each.
- `MonitorService.poll_once()` — replace `battery_probe_chain(handle, dev_idx)` with
  `DEVICE_PROBES[(vid, pid)](handle, dev_idx)`.
- `MonitorService._voltage_history` — guard: skip history update when `voltage_mv == 0`.
- Phase 4 UI (`src/ui/device_card.py`) — already handles any `DeviceState` snapshot;
  no UI changes needed when SteelSeries device appears.
</code_context>

<specifics>
## Specific Ideas

- SteelSeries Aerox 5 Wireless (2.4GHz) — VID: 0x1038, exact PID to be confirmed via
  hardware enumeration or HeadsetControl device table.
- Command format is likely a single-byte report ID + payload; HeadsetControl's
  `STEELSERIES_ARCTIS_7_2019` or similar mouse entries are the closest reference.
</specifics>

<deferred>
## Deferred Ideas

- Other SteelSeries devices (Rival 650, Aerox 9, etc.) — add to backlog when Aerox 5 is working
- Charging status via USB power detection — if protocol doesn't expose it, this is a v2 enhancement
</deferred>

---

*Phase: 05-steelseries-hid-backend*
*Context gathered: 2026-06-04*
