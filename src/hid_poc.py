"""
HID enumeration and raw I/O proof-of-concept for the PeriphWatcher project.

Enumerates all Logitech (VID=0x046D) HID interfaces, filters for the vendor-specific
interface (usage_page=0xFF00), opens it exclusively via open_path(), and performs a
raw write + read round-trip. This script confirms that Windows HID access on the
vendor-specific usage page works without Access Denied before any HID++ protocol
code is written.
"""

import sys
import hid

LOGITECH_VID = 0x046D
VENDOR_USAGE_PAGE = 0xFF00
REPORT_SIZE = 64
READ_TIMEOUT_MS = 1000


def find_vendor_interfaces(vid: int) -> list:
    """
    Enumerate all HID interfaces for the given VID and return those with
    usage_page == VENDOR_USAGE_PAGE (0xFF00).

    Prints every enumerated interface first so the exact PID is visible.
    Returns a list of matching dicts (may be empty).
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


def open_and_probe(info: dict) -> None:
    """
    Open the HID interface described by `info` via open_path() and perform a
    raw write + read round-trip. Closes the device in a finally block.
    """
    device = hid.device()
    try:
        device.open_path(info["path"])
        print(
            f"Opened: {device.get_manufacturer_string()} {device.get_product_string()}"
        )
        print(
            f"  VID: 0x{info['vendor_id']:04X}  "
            f"PID: 0x{info['product_id']:04X}  "
            f"usage_page: 0xFF00"
        )

        # STEP 4 — Raw write + read round-trip
        payload = [0x00] * REPORT_SIZE  # report ID 0x00 = no report ID prefix
        try:
            device.write(payload)
            print("Write: sent 64-byte null report")
        except OSError as exc:
            print(f"Write OSError: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"Write error ({type(exc).__name__}): {exc}")

        try:
            response = device.read(REPORT_SIZE, timeout_ms=READ_TIMEOUT_MS)
            if not response:
                print(
                    "Read: timeout (empty response) — device may be off or wrong interface"
                )
            else:
                print(f"Read: {len(response)} bytes — first 8: {response[:8]}")
        except OSError as exc:
            print(f"Read OSError: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"Read error ({type(exc).__name__}): {exc}")

    finally:
        device.close()


def main() -> None:
    # STEP 1 — Full Logitech VID scan
    vendor_interfaces = find_vendor_interfaces(LOGITECH_VID)

    # STEP 2 — Filter for LIGHTSPEED candidates
    if not vendor_interfaces:
        all_pids = [
            f"0x{d['product_id']:04X}"
            for d in hid.enumerate(LOGITECH_VID, 0)
        ]
        print(
            f"No usage_page=0xFF00 interface found. "
            f"PIDs seen: {', '.join(all_pids) if all_pids else '(none)'}"
        )
        sys.exit(1)

    print(f"Found {len(vendor_interfaces)} interface(s) with usage_page=0xFF00")

    # Use the first matching entry
    target = vendor_interfaces[0]

    # STEP 3 + 4 + 5 — Open, probe, close
    open_and_probe(target)


if __name__ == "__main__":
    main()
