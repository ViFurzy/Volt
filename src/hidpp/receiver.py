"""
Receiver enumeration for the G Pro X Wireless (G-series headset protocol).

Hardware-confirmed in 02-01: the dongle uses usage_page=0xFF43 (not 0xFF00),
and the battery command targets device_idx=0xFF (the receiver itself).

Provides three functions consumed by query_battery.py:
  - find_receiver(vid)         -> list of matching HID interface dicts
  - open_receiver(info)        -> open hid.device (caller owns lifetime)
  - discover_device_index(dev) -> int (returns DEVICE_IDX=0xFF, no probing)
"""

import hid

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOGITECH_VID = 0x046D

# 0xFF43 confirmed on G Pro X Wireless (PID=0x0ABA) via hardware probe (02-01).
# Standard HID++ 2.0 uses 0xFF00; the G-series headset protocol uses 0xFF43.
VENDOR_USAGE_PAGE = 0xFF43

# Fixed receiver device index for G-series headset protocol.
# The G Pro X Wireless battery command targets the receiver itself (0xFF),
# not a paired-device index — no per-device probing via Root 0x0000 is needed.
DEVICE_IDX = 0xFF


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

    Caller owns the device lifetime. Raises OSError if open_path fails.
    NEVER calls hid.open(vid, pid) — that risks opening the wrong interface.
    """
    device = hid.device()
    device.open_path(info["path"])
    return device


def discover_device_index(device) -> int:
    """
    Return the fixed receiver device index for G-series headset protocol.

    G Pro X Wireless uses device_idx=0xFF (the LIGHTSPEED receiver itself).
    No per-device index probing via Root feature 0x0000 is needed.
    Parameter 'device' accepted for API compatibility with query_battery.py
    but is not used.
    """
    return DEVICE_IDX
