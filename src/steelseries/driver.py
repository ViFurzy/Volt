"""
SteelSeries Aerox 5 Wireless 2.4GHz dongle driver.

Interface selection: filter by interface_number==3 (not usage_page).
The dongle presents 7 HID interfaces; interface 3 (usage_page=0xFFC0) is the
vendor-specific one that accepts battery commands. Interfaces 0–2 are primary
mouse/keyboard/consumer-control interfaces that Windows locks with Access Denied.

Handle lifecycle: open_path + close per call to ss_battery_probe.
The dongle responds to the battery command exactly once per device open;
this is a hardware constraint. Callers must open a fresh handle before each
call to ss_battery_probe and close it after.
"""

import hid

from hidpp.features import BatteryResult

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

SS_VID = 0x1038
SS_AEROX5_PID = 0x1852

# interface_number, NOT usage_page. The vendor-specific interface is always
# interface 3 (usage_page=0xFFC0) on the Aerox 5 Wireless dongle.
SS_VENDOR_INTERFACE = 3

# Placeholder dev_idx for (vid, pid, dev_idx) key in MonitorService._open.
# Not used in the command payload — SteelSeries protocol has no device index byte.
SS_DEVICE_IDX = 0x00

# ---------------------------------------------------------------------------
# Private constants
# ---------------------------------------------------------------------------

# 0x92 (base battery command) | 0x40 (wireless flag) = 0xD2
# Source: rivalcfg/devices/aerox5_wireless_wireless.py
_SS_BATTERY_CMD = 0xD2

# Windows hidapi transfer queue must have at least one read submitted before
# write, or the response is never queued. 3 warmup reads verified on hardware.
_SS_WARMUP_READS = 3

# Scan at most 20 response packets after write. The dongle broadcasts 0x61
# async notification packets (~15/sec) that must be skipped before 0xD2 arrives.
_SS_MAX_RESPONSE_READS = 20


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_dongle(vid: int = SS_VID, verbose: bool = False) -> list[dict]:
    """
    Enumerate all HID interfaces for ``vid`` and return those with
    interface_number == SS_VENDOR_INTERFACE (3).

    When verbose=True, prints every enumerated interface (PID, interface_number,
    usage_page, path) to stdout for diagnostic use. Pass verbose=False (default)
    during background polling to keep the 60s poll loop silent.

    Returns a list of matching dicts (may be empty if dongle is not connected).
    """
    all_devices = hid.enumerate(vid, 0)
    if verbose:
        for d in all_devices:
            path = d["path"]
            path_str = path.decode("utf-8", errors="replace") if isinstance(path, bytes) else repr(path)
            print(
                f"  PID=0x{d['product_id']:04X}  "
                f"iface={d['interface_number']}  "
                f"page=0x{d['usage_page']:04X}  "
                f"path={path_str}"
            )
    return [d for d in all_devices if d["interface_number"] == SS_VENDOR_INTERFACE]


def open_dongle(info: dict):
    """
    Open the HID interface described by ``info`` via open_path() and return the
    open hid.device object.

    Open via open_path(). Never hid.open(vid, pid).
    Caller owns the device lifetime. Raises OSError if open_path fails.
    """
    device = hid.device()
    device.open_path(info["path"])
    return device


def ss_battery_probe(device, dev_idx: int) -> "BatteryResult | None":
    """
    Read battery level from SteelSeries Aerox 5 Wireless via the 0xD2 command.

    dev_idx is accepted for DEVICE_PROBES API compatibility but is not used —
    the SteelSeries protocol is single-device and has no device index byte in
    the command payload.

    The caller must provide a freshly opened device handle (via open_dongle).
    The dongle responds exactly once per device open; reusing a handle across
    calls will yield None on the second call.

    Returns None if the mouse is off or out of range (no 0xD2 response within
    _SS_MAX_RESPONSE_READS packets).
    """
    # Warmup: submit reads to initialize the Windows hidapi transfer queue.
    # Without these, the battery command write succeeds but no response arrives.
    for _ in range(_SS_WARMUP_READS):
        device.read(64, timeout_ms=100)

    # Send battery command: report_id=0x00, cmd=0xD2
    device.write([0x00, _SS_BATTERY_CMD])

    # Scan response packets. Skip 0x61 async notification packets (serial
    # number broadcast, ~15/sec). Stop early on empty read (no more data).
    for _ in range(_SS_MAX_RESPONSE_READS):
        resp = device.read(64, timeout_ms=100)
        if not resp:
            break
        if resp[0] == _SS_BATTERY_CMD:
            raw = resp[1] & 0x7F
            pct = (raw - 1) * 5 if raw > 0 else 0
            # Clamp to valid range (T-05-01 threat mitigation)
            pct = max(0, min(100, pct))
            return BatteryResult(
                percent=pct,
                voltage_mv=0,           # SteelSeries doesn't report voltage
                charging=bool(resp[1] & 0x80),
                feature_used="0xD2",
            )

    return None  # mouse off or out of range
