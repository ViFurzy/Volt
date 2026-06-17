import sys
import hid

sys.path.append("src")
from hidpp.protocol import send_and_recv, HIDppError

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
        
    print("Dumping HID++ 1.0 registers on 0xFF...")
    for reg in range(0x00, 0x100):
        # Build read register command: [0x10, 0xFF, 0x81, reg, 0x00, 0x00, 0x00]
        # In HID++ 1.0, 0x81 is Read Register, 0xFF is receiver.
        cmd = [0x10, 0xFF, 0x81, reg, 0x00, 0x00, 0x00]
        try:
            resp = send_and_recv(device, cmd, timeout_ms=30, min_len=6)
            if resp:
                print(f"Register 0x{reg:02X}: {list(resp)}")
        except HIDppError as e:
            # Check error code
            if e.code != 1:  # skip invalid subid/register not supported
                print(f"Register 0x{reg:02X}: HID++ Error {e.code}")
        except OSError:
            pass
            
    device.close()
    print("Dump complete.")

if __name__ == "__main__":
    main()
