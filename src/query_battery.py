import sys
sys.coinit_flags = 0  # MUST be here — before any other import. bleak WinRT backend requires COM MTA.

import hid
from hidpp.receiver import find_receiver, open_receiver, discover_device_index
from hidpp.features import battery_probe_chain

"""
Phase 2 standalone integration script for Volt.

Opens the LIGHTSPEED receiver (usage_page=0xFF43), discovers the device index,
probes the G Pro X Wireless battery via the G-series 0x06/0x0D command, and
prints the result to stdout. Confirms the full chain (enumerate -> open ->
discover index -> probe -> parse -> print) works against the actual device.
"""


def main() -> None:
    # STEP 1 — Enumerate LIGHTSPEED receiver
    candidates = find_receiver()
    if not candidates:
        all_pids = [f"0x{d['product_id']:04X}" for d in hid.enumerate(0x046D, 0)]
        print(f"No usage_page=0xFF43 interface found. PIDs seen: {', '.join(all_pids) if all_pids else '(none)'}")
        sys.exit(1)
    info = candidates[0]
    print(f"Found receiver: PID=0x{info['product_id']:04X}")

    # STEP 2 — Open receiver
    device = open_receiver(info)
    try:
        # STEP 3 — Discover device index
        device_idx = discover_device_index(device)
        print(f"Device index: 0x{device_idx:02X}")

        # STEP 4 — Probe battery
        result = battery_probe_chain(device, device_idx)
        if result is None:
            print("Battery: OFFLINE (device did not respond)")
        else:
            pct_str = f"{result.percent}%" if result.percent is not None else "Charging (% unknown)"
            charging_str = "charging" if result.charging else "not charging"
            print(f"Battery: {pct_str} — {charging_str} (feature {result.feature_used})")
    finally:
        device.close()


if __name__ == "__main__":
    main()
