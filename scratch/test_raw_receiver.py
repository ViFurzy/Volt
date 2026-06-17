import sys
import hid

def main():
    all_devs = hid.enumerate(0x046D, 0xC548)
    # Find MI_02 which is the HID++ interface
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
    device.open_path(target['path'])
    
    # Query FEATURE_SET index on 0xFF
    # Short packet: [0x10, device_idx, feature_idx, func, param0, param1, param2]
    # Root feature is 0x00. GetFeature function is 0x00. Software ID is 0x01 (or 0x00, let's try 0x01).
    # cmd: [0x10, 0xFF, 0x00, 0x01, 0x00, 0x01, 0x00]
    cmd = [0x10, 0xFF, 0x00, 0x01, 0x00, 0x01, 0x00]
    device.write(cmd)
    try:
        resp = device.read(20, timeout_ms=300)
        print(f"Response to Root:GetFeature(0x0001) on 0xFF: {list(resp)}")
    except Exception as e:
        print("Read error:", e)
        
    # Let's also check index 1
    cmd = [0x10, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00]
    device.write(cmd)
    try:
        resp = device.read(20, timeout_ms=300)
        print(f"Response to Root:GetFeature(0x0001) on 0x01: {list(resp)}")
    except Exception as e:
        print("Read error:", e)
        
    device.close()

if __name__ == "__main__":
    main()
