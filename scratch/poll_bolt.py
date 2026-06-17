import sys
import hid
import time
import struct

sys.path.append("src")
from hidpp.protocol import send_and_recv, HIDppError, build_short_msg

# HID++ 2.0 Error Codes
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
        resp = send_and_recv(device, cmd, timeout_ms=150, min_len=6)
        if resp:
            feat_idx = resp[4]
            if feat_idx != 0:
                return feat_idx
    except HIDppError as e:
        # e.code is the error returned
        pass
    except Exception:
        pass
    return None

def probe_device(device, device_idx: int):
    # 1. Try to check if device is online by querying FEATURE_SET (0x0001)
    fs_idx = get_feature_index(device, device_idx, 0x0001)
    if fs_idx is None:
        # Check if we got an offline error or feature not supported
        # We can try to send the command directly and catch the error
        cmd = build_short_msg(device_idx, 0x00, 0x00, (0x00, 0x01, 0x00))
        try:
            send_and_recv(device, cmd, timeout_ms=150, min_len=6)
            # If no exception, it supported it but returned 0? Unlikely
        except HIDppError as e:
            err_msg = ERR_NAMES.get(e.code, f"UNKNOWN_ERROR (0x{e.code:02X})")
            if e.code == 0x04:
                # Device is paired but currently offline/asleep
                return "offline", err_msg
            elif e.code == 0x01:
                # Feature not supported (maybe a very old device or receiver index)
                return "unsupported", err_msg
            else:
                return "error", err_msg
        except Exception as e:
            return "error", str(e)
        return "inactive", "No response"
        
    # If we got a feature set index, the device is ONLINE!
    # Let's query battery features: 0x1004 (Unified Battery) then 0x1000 (Battery Status)
    battery_info = "Unknown"
    
    # Check Unified Battery 0x1004
    feat_1004 = get_feature_index(device, device_idx, 0x1004)
    if feat_1004 is not None:
        cmd = build_short_msg(device_idx, feat_1004, 0x00, (0, 0, 0))
        try:
            resp = send_and_recv(device, cmd, timeout_ms=150, min_len=6)
            if resp:
                level = resp[4]
                status = resp[5]
                battery_info = f"Unified Battery (0x1004): {level}% (status: 0x{status:02X})"
        except Exception as e:
            battery_info = f"Error querying 0x1004: {e}"
    else:
        # Check Battery Status 0x1000
        feat_1000 = get_feature_index(device, device_idx, 0x1000)
        if feat_1000 is not None:
            cmd = build_short_msg(device_idx, feat_1000, 0x00, (0, 0, 0))
            try:
                resp = send_and_recv(device, cmd, timeout_ms=150, min_len=6)
                if resp:
                    level = resp[4]
                    status = resp[5]
                    battery_info = f"Battery Status (0x1000): {level}% (status: 0x{status:02X})"
            except Exception as e:
                battery_info = f"Error querying 0x1000: {e}"
        else:
            battery_info = "No battery features supported"
            
    # Also try to get the device name if feature 0x0005 (Device Name) is supported
    name_info = "Unknown Name"
    feat_name = get_feature_index(device, device_idx, 0x0005)
    if feat_name is not None:
        # GetNameLength (func 0x00)
        cmd_len = build_short_msg(device_idx, feat_name, 0x00, (0, 0, 0))
        try:
            resp_len = send_and_recv(device, cmd_len, timeout_ms=150, min_len=6)
            if resp_len:
                name_len = resp_len[4]
                # GetName (func 0x01), packet by packet (each packet has up to 16 bytes)
                name_bytes = bytearray()
                offset = 0
                while offset < name_len:
                    # GetName has params (offset, length, ...) or similar
                    # For 0x0005 GetName: func is 0x01
                    cmd_name = build_short_msg(device_idx, feat_name, 0x01, (offset, 0, 0))
                    resp_name = send_and_recv(device, cmd_name, timeout_ms=150, min_len=6)
                    if resp_name:
                        # Append bytes from position 4 onwards
                        # Short packet response has params in bytes 4..19? Wait, short response only has 3 parameter bytes!
                        # Ah, GetName might use long reports! Let's check Solaar's GetName logic:
                        # Long message is used for GetName. Let's see if we can just print the name.
                        pass
        except Exception:
            pass
            
    return "online", f"{battery_info}"

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
        
    print(f"Using Receiver path: {target['path']}")
    device = hid.device()
    try:
        device.open_path(target['path'])
        print("Successfully opened Bolt Receiver.")
    except Exception as e:
        print(f"Failed to open receiver: {e}")
        return
        
    print("\nStarting continuous polling of sub-devices 1 to 6...")
    print("Press Ctrl+C to stop.\n")
    
    last_status = {}
    try:
        while True:
            for idx in range(1, 7):
                status_type, msg = probe_device(device, idx)
                key = idx
                if last_status.get(key) != (status_type, msg):
                    last_status[key] = (status_type, msg)
                    timestamp = time.strftime("%H:%M:%S")
                    if status_type == "online":
                        print(f"[{timestamp}] Device {idx}: ONLINE - {msg}")
                    elif status_type == "offline":
                        print(f"[{timestamp}] Device {idx}: Paired but OFFLINE (asleep)")
                    elif status_type == "unsupported":
                        print(f"[{timestamp}] Device {idx}: Not paired or feature unsupported")
                    else:
                        # Only print other errors if they are not connect errors
                        print(f"[{timestamp}] Device {idx}: Status: {status_type} ({msg})")
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("\nPolling stopped.")
    finally:
        device.close()

if __name__ == "__main__":
    main()
