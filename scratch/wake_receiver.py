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
        
    device = hid.device()
    try:
        device.open_path(target['path'])
        print("Receiver opened successfully.")
    except Exception as e:
        print("Open failed:", e)
        return
        
    # Write to Register 0x00: Enable Notifications (value 0x01)
    # Write Register command is 0x80
    print("Enabling receiver notifications (writing 0x01 to Register 0x00)...")
    write_cmd = [0x10, 0xFF, 0x80, 0x00, 0x01, 0x00, 0x00]
    try:
        resp = send_and_recv(device, write_cmd, timeout_ms=100)
        print("Write response:", list(resp) if resp else "None")
    except Exception as e:
        print("Write failed:", e)
        
    print("\nQuerying device indices 1 to 6...")
    for idx in range(1, 7):
        cmd = build_short_msg(idx, 0x00, 0x00, (0x00, 0x01, 0x00))
        try:
            resp = send_and_recv(device, cmd, timeout_ms=100, min_len=6)
            if resp:
                print(f"Index {idx}: Success! -> {list(resp)}")
        except HIDppError as e:
            if e.code == 4:
                print(f"Index {idx}: Paired but OFFLINE (error code 4)")
            elif e.code == 1:
                print(f"Index {idx}: Feature Unsupported (error code 1)")
            else:
                print(f"Index {idx}: Error response -> code {e.code}")
        except Exception as e:
            print(f"Index {idx}: Exception: {e}")
            
    device.close()

if __name__ == "__main__":
    main()
