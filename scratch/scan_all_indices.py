import sys
import hid
import time

sys.path.append("src")
from hidpp.protocol import send_and_recv, HIDppError, build_short_msg

def main():
    all_devs = hid.enumerate(0x046D, 0xC548)
    target = None
    for d in all_devs:
        if d.get("interface_number") == 2 and d.get("usage_page") == 0xFF00:
            target = d
            break
    if not target:
        for d in all_devs:
            if d.get("usage_page") == 0xFF00:
                target = d
                break
    if not target:
        print("No 0xFF00 interface found.")
        return
        
    print(f"Opening path: {target['path']}")
    device = hid.device()
    try:
        device.open_path(target['path'])
        print("Receiver opened successfully.")
    except Exception as e:
        print("Open failed:", e)
        return
        
    print("Scanning indices 1 to 254 (0x01 to 0xFE) via Root:GetFeature(0x0001)...")
    print("Please move the mouse and type on the keyboard while this runs!\n")
    
    # We will send a query to each index
    for idx in range(1, 255):
        # build Root:GetFeature(0x0001)
        cmd = build_short_msg(idx, 0x00, 0x00, (0x00, 0x01, 0x00))
        try:
            resp = send_and_recv(device, cmd, timeout_ms=30, min_len=6)
            if resp:
                print(f"Index 0x{idx:02X} ({idx:d}): Success response -> {list(resp)}")
        except HIDppError as e:
            # We got an error response (which means the index is valid/active or paired)
            if e.code == 4:
                # Paired but offline
                print(f"Index 0x{idx:02X} ({idx:d}): Paired but OFFLINE (error code 4)")
            elif e.code == 1:
                # Feature not supported
                print(f"Index 0x{idx:02X} ({idx:d}): Feature Unsupported (error code 1)")
            else:
                print(f"Index 0x{idx:02X} ({idx:d}): Error response -> code {e.code:d}")
        except OSError:
            # Low-level HID error
            pass
            
    device.close()
    print("\nScan complete.")

if __name__ == "__main__":
    main()
