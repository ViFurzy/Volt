import sys
import hid
import time

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
        print(f"Opened receiver: {target['path']}")
    except Exception as e:
        print("Open failed:", e)
        return
        
    print("\nListening for reports on interface 2 for 10 seconds...")
    print("Please move the mouse and type on the keyboard now!\n")
    
    start_time = time.time()
    count = 0
    try:
        while time.time() - start_time < 10.0:
            # Non-blocking read (timeout_ms=100)
            data = device.read(64, timeout_ms=100)
            if data:
                count += 1
                print(f"[{count}] Received report: {list(data)}")
    except KeyboardInterrupt:
        pass
    finally:
        device.close()
    print(f"\nFinished listening. Total reports received: {count}")

if __name__ == "__main__":
    main()
