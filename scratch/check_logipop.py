import sys
import hid
import time

sys.path.append("src")
from hidpp.protocol import send_and_recv, HIDppError, build_short_msg

# Error names mapping
ERR_NAMES = {
    0x00: "NO_ERROR",
    0x01: "INVALID_SUBID (Feature not supported)",
    0x02: "INVALID_ADDRESS",
    0x03: "INVALID_VALUE",
    0x04: "CONNECT_ERR (Device offline/asleep)",
    0x05: "TOO_MANY_DEVICES / NOT_ALLOWED",
    0x06: "ALREADY_EXISTS",
    0x07: "BUSY",
    0x08: "UNKNOWN",
}

def get_feature_index(device, device_idx: int, feature_id: int) -> int | None:
    cmd = build_short_msg(device_idx, 0x00, 0x00, ((feature_id >> 8) & 0xFF, feature_id & 0xFF, 0x00))
    try:
        resp = send_and_recv(device, cmd, timeout_ms=100, min_len=6)
        if resp:
            feat_idx = resp[4]
            if feat_idx != 0:
                return feat_idx
    except HIDppError:
        pass
    except Exception:
        pass
    return None

def get_device_name(device, device_idx: int) -> str:
    # Try HID++ 2.0 Device Name feature 0x0005
    feat_name = get_feature_index(device, device_idx, 0x0005)
    if feat_name is not None:
        # GetNameLength (func 0x00)
        cmd_len = build_short_msg(device_idx, feat_name, 0x00, (0, 0, 0))
        try:
            resp_len = send_and_recv(device, cmd_len, timeout_ms=100, min_len=6)
            if resp_len:
                name_len = resp_len[4]
                name_bytes = bytearray()
                # GetName (func 0x01) with offsets
                # We can fetch chunks of 3 bytes using short messages
                for offset in range(0, name_len, 3):
                    cmd_name = build_short_msg(device_idx, feat_name, 0x01, (offset, 0, 0))
                    resp_name = send_and_recv(device, cmd_name, timeout_ms=100, min_len=6)
                    if resp_name:
                        # resp_name[4..6] contain up to 3 name bytes
                        chunk = resp_name[4:7]
                        # Trim any trailing zero bytes
                        name_bytes.extend(chunk)
                return name_bytes[:name_len].decode("utf-8", errors="ignore").strip()
        except Exception:
            pass
    return "Unknown Device"

def get_device_battery(device, device_idx: int) -> str:
    # 1. Try modern Unified Battery (0x1004)
    feat_1004 = get_feature_index(device, device_idx, 0x1004)
    if feat_1004 is not None:
        cmd = build_short_msg(device_idx, feat_1004, 0x00, (0, 0, 0))
        try:
            resp = send_and_recv(device, cmd, timeout_ms=100, min_len=6)
            if resp:
                return f"{resp[4]}% (Unified Battery)"
        except Exception:
            pass
            
    # 2. Try legacy Battery Status (0x1000)
    feat_1000 = get_feature_index(device, device_idx, 0x1000)
    if feat_1000 is not None:
        cmd = build_short_msg(device_idx, feat_1000, 0x00, (0, 0, 0))
        try:
            resp = send_and_recv(device, cmd, timeout_ms=100, min_len=6)
            if resp:
                return f"{resp[4]}% (Battery Status)"
        except Exception:
            pass
            
    return "N/A"

def probe_device(device, device_idx: int) -> tuple[str, str]:
    # Query root feature to see connection status
    cmd = build_short_msg(device_idx, 0x00, 0x00, (0x00, 0x01, 0x00))
    try:
        resp = send_and_recv(device, cmd, timeout_ms=100, min_len=6)
        if resp:
            # Device responded successfully! It is online!
            name = get_device_name(device, device_idx)
            battery = get_device_battery(device, device_idx)
            return "online", f"{name} | Battery: {battery}"
    except HIDppError as e:
        if e.code == 4:
            return "offline", "Asleep / Offline"
        elif e.code == 1:
            return "unsupported", "Feature set unsupported"
        else:
            return "error", f"HID++ Error code {e.code}"
    except Exception as e:
        return "error", str(e)
    return "inactive", "No response / Empty slot"

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
        print("Error: Could not find the Logitech Bolt Receiver's 0xFF00 interface.")
        return
        
    print(f"Opening path: {target['path']}")
    device = hid.device()
    try:
        device.open_path(target['path'])
        print("Receiver opened successfully.")
    except Exception as e:
        print("Open failed:", e)
        return
        
    # Enable receiver notifications (Register 0x00 = 0x01)
    write_cmd = [0x10, 0xFF, 0x80, 0x00, 0x01, 0x00, 0x00]
    try:
        send_and_recv(device, write_cmd, timeout_ms=100)
        print("Notifications enabled on receiver.")
    except Exception:
        pass
        
    print("\n--- Monitoring Logitech Bolt Receiver ---")
    print("Press Ctrl+C to exit.")
    print("Please make sure your Pop Mouse and Pop Keyboard are turned on,")
    print("and set to the channel paired with this receiver (usually channel 1).")
    print("Then type a few keys or move the mouse to wake them up.\n")
    
    last_states = {}
    try:
        while True:
            for idx in range(1, 7):
                status_type, msg = probe_device(device, idx)
                key = idx
                if last_states.get(key) != (status_type, msg):
                    last_states[key] = (status_type, msg)
                    timestamp = time.strftime("%H:%M:%S")
                    if status_type == "online":
                        print(f"[{timestamp}] Device {idx}: ONLINE -> {msg}")
                    elif status_type == "offline":
                        # Only print paired-but-offline on start or when transitioning to offline
                        print(f"[{timestamp}] Device {idx}: Paired but OFFLINE (asleep)")
                    elif status_type == "inactive":
                        pass
                    else:
                        print(f"[{timestamp}] Device {idx}: {status_type} ({msg})")
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    finally:
        device.close()

if __name__ == "__main__":
    main()
