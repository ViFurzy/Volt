"""
Receiver enumeration and device index discovery for Logitech LIGHTSPEED dongles.

Provides three functions consumed by query_battery.py (Wave 3):
  - find_receiver(vid)         -> list of matching HID interface dicts
  - open_receiver(info)        -> open hid.device (caller owns lifetime)
  - discover_device_index(dev) -> int | None (probes 0x01–0x06)

OFFSET note (confirmed in 02-01-SUMMARY.md): response[0] IS the report ID byte.
All byte indexing in this module uses 1-based data offsets accordingly.

Hardware note: G Pro X Wireless (PID=0x0ABA) uses VENDOR_USAGE_PAGE=0xFF43 and
device_idx=0xFF (the receiver itself). discover_device_index probes 0x01–0x06
for generic HID++ 2.0 paired-device discovery; the G Pro X battery command uses
0xFF directly (handled by query_battery.py, not here).
"""

import hid
from hidpp.protocol import build_short_msg, send_and_recv, HIDppError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOGITECH_VID = 0x046D

# 0xFF43 confirmed on G Pro X Wireless (PID=0x0ABA) via hardware probe (02-01).
# Standard HID++ 2.0 uses 0xFF00; the G-series headset/mouse protocol uses 0xFF43.
VENDOR_USAGE_PAGE = 0xFF43

DEVICE_INDEX_MIN = 0x01
DEVICE_INDEX_MAX = 0x06  # safe scan range for LIGHTSPEED single-device receivers


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_receiver(vid: int = LOGITECH_VID) -> list[dict]:
    """
    Enumerate all HID interfaces for `vid` and return those with
    usage_page == VENDOR_USAGE_PAGE (0xFF43).

    Prints every enumerated interface to stdout so PIDs are visible during
    integration runs. Returns a list of matching dicts (may be empty).
    """
    print(f"=== All Logitech (0x{vid:04X}) HID interfaces ===")
    all_devices = hid.enumerate(vid, 0)

    if not all_devices:
        print("  (no devices found for this VID)")
        return []

    for info in all_devices:
        path = info["path"]
        # bytes-path guard: hid.enumerate may return bytes on some platforms
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


def open_receiver(info: dict):
    """
    Open the HID interface described by `info` via open_path() and return the
    open hid.device object.

    The caller owns the device lifetime — do NOT close here. This matches the
    threat model: only open_path() after usage_page filter (T-02-03).

    Raises OSError if open_path fails (propagates; do not swallow).
    """
    device = hid.device()
    device.open_path(info["path"])  # NEVER hid.open(vid, pid) — wrong interface risk
    return device


def discover_device_index(device) -> int | None:
    """
    Probe device indices 0x01–0x06 for a responsive wireless device.

    Sends a Root feature (0x0000) query to each index; returns the first index
    that returns a valid (non-error, non-timeout) response. Returns None if no
    device is found. Device index 0xFF is never used here.

    OSError per-index is caught and skipped (T-02-04: stale handle resilience).
    HIDppError per-index is caught and skipped (offline/busy device at that index).
    """
    for idx in range(DEVICE_INDEX_MIN, DEVICE_INDEX_MAX + 1):
        msg = build_short_msg(device_idx=idx, feature_idx=0x00, function=0)
        try:
            result = send_and_recv(device, msg, timeout_ms=100)
        except (HIDppError, OSError):
            continue
        if result is not None:
            return idx
    return None
