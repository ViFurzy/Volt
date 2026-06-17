import sys
import hid
import struct

sys.path.append("src")
from hidpp.protocol import send_and_recv, HIDppError, build_short_msg

def get_feature_index(device, device_idx: int, feature_id: int) -> int | None:
    # Build short message for Root (0x00) -> GetFeature (0x00)
    # The fourth byte is (0x00 << 4) | 0x01 = 0x01
    cmd = build_short_msg(device_idx, 0x00, 0x00, ((feature_id >> 8) & 0xFF, feature_id & 0xFF, 0x00))
    try:
        resp = send_and_recv(device, cmd, timeout_ms=150, min_len=6)
        if resp:
            # resp[2] is feature_idx (0x00), resp[3] is func (0x01)
            # resp[4] is the dynamic index of the requested feature
            feat_idx = resp[4]
            if feat_idx != 0:
                return feat_idx
    except HIDppError as e:
        # If it returns an error (e.g. offline, not supported), return None
        pass
    except Exception:
        pass
    return None

def enumerate_features(device, device_idx: int):
    print(f"\n--- Enumerating features on Device Index 0x{device_idx:02X} ---")
    fs_idx = get_feature_index(device, device_idx, 0x0001)  # FEATURE_SET
    if fs_idx is None:
        print("FEATURE_SET (0x0001) not supported or device offline.")
        return
        
    # Call GetCount (func 0x00)
    cmd = build_short_msg(device_idx, fs_idx, 0x00, (0, 0, 0))
    try:
        resp = send_and_recv(device, cmd, timeout_ms=150, min_len=6)
        if not resp:
            print("GetCount failed to respond.")
            return
        count = resp[4]
        print(f"Device supports {count} features (excluding ROOT):")
        # Enumerate each feature index
        for i in range(1, count + 1):
            # GetFeature (func 0x01)
            cmd_feat = build_short_msg(device_idx, fs_idx, 0x01, (i, 0, 0))
            resp_feat = send_and_recv(device, cmd_feat, timeout_ms=150, min_len=6)
            if resp_feat:
                feat_id = (resp_feat[4] << 8) | resp_feat[5]
                print(f"  Feature Index {i:d} (0x{i:02X}): Feature ID 0x{feat_id:04X}")
    except Exception as e:
        print(f"Error enumerating features: {e}")

def probe_battery_features(device, device_idx: int):
    print(f"\n--- Probing Battery for Device Index 0x{device_idx:02X} ---")
    # Modern Battery feature 0x1004 (Unified Battery)
    feat_1004 = get_feature_index(device, device_idx, 0x1004)
    if feat_1004 is not None:
        print(f"Unified Battery (0x1004) index: 0x{feat_1004:02X}")
        # GetBatteryLevelStatus (func 0x00)
        cmd = build_short_msg(device_idx, feat_1004, 0x00, (0, 0, 0))
        try:
            resp = send_and_recv(device, cmd, timeout_ms=150, min_len=6)
            if resp:
                print(f"  GetBatteryLevelStatus response: {list(resp)}")
                print(f"  Level: {resp[4]}% | Status: 0x{resp[5]:02X}")
        except Exception as e:
            print(f"  Error calling GetBatteryLevelStatus: {e}")
            
    # Legacy Battery feature 0x1000 (Battery status)
    feat_1000 = get_feature_index(device, device_idx, 0x1000)
    if feat_1000 is not None:
        print(f"Battery Status (0x1000) index: 0x{feat_1000:02X}")
        # GetBatteryStatus (func 0x00)
        cmd = build_short_msg(device_idx, feat_1000, 0x00, (0, 0, 0))
        try:
            resp = send_and_recv(device, cmd, timeout_ms=150, min_len=6)
            if resp:
                print(f"  GetBatteryStatus response: {list(resp)}")
                print(f"  Level: {resp[4]}% | Status: 0x{resp[5]:02X}")
        except Exception as e:
            print(f"  Error calling GetBatteryStatus: {e}")

    if feat_1004 is None and feat_1000 is None:
        print("No battery features supported or device is offline.")

def main():
    print("Enumerating all HID interfaces for 0xC548...")
    all_devs = hid.enumerate(0x046D, 0xC548)
    if not all_devs:
        print("Logitech Bolt Receiver 0xC548 not found.")
        return
        
    for info in all_devs:
        path = info["path"]
        iface = info.get("interface_number", -1)
        usage_page = info.get("usage_page", 0)
        print(f"\n==========================================")
        print(f"Interface: {iface} | UsagePage: 0x{usage_page:04X} | Path: {path}")
        
        device = hid.device()
        try:
            device.open_path(path)
            print("Successfully opened interface.")
        except Exception as e:
            print(f"Failed to open path: {e}")
            continue
            
        # Try a quick test on the receiver index 0xFF
        print("Testing Root on receiver (0xFF)...")
        fs_idx = get_feature_index(device, 0xFF, 0x0001)
        if fs_idx is not None:
            print(f"Receiver responded! FEATURE_SET index: {fs_idx}")
            # Enumerate receiver features
            enumerate_features(device, 0xFF)
            # Enumerate features and battery on sub-devices 1 to 6
            for sub_idx in range(1, 7):
                print(f"\nChecking paired sub-device 0x{sub_idx:02X}...")
                enumerate_features(device, sub_idx)
                probe_battery_features(device, sub_idx)
        else:
            print("Receiver did not respond on this interface.")
            
        device.close()

if __name__ == "__main__":
    main()
