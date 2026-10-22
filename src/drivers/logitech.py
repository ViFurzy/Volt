import hid
from .base import BaseDriver
from .table import devices_for, vendor_ids
from hidpp.receiver import DEVICE_IDX, open_receiver
from hidpp.features import battery_probe_chain, BatteryResult
from hidpp.protocol import send_and_recv

def get_feature_index(device, device_idx: int, feature_id: int) -> int | None:
    # Root:GetFeature is feature 0x00, function 0x00
    # Command: [0x10, device_idx, 0x00, 0x00, feature_id_high, feature_id_low, 0x00]
    cmd = [0x10, device_idx, 0x00, 0x00, (feature_id >> 8) & 0xFF, feature_id & 0xFF, 0x00]
    try:
        resp = send_and_recv(device, cmd, min_len=6)
        if resp and resp[2] == 0x00 and resp[3] == 0x00:
            feat_idx = resp[4]
            if feat_idx != 0:
                return feat_idx
    except Exception:
        pass
    return None

def query_hidpp20_battery(device, device_idx: int) -> BatteryResult | None:
    # Try modern feature 0x1004 (Unified Battery), then fallback to legacy 0x1000 (Battery status)
    for feature_id in (0x1004, 0x1000):
        feat_idx = get_feature_index(device, device_idx, feature_id)
        if feat_idx is not None:
            # Command: GetBatteryLevelStatus / GetBatteryStatus (func 0)
            cmd = [0x10, device_idx, feat_idx, 0x00, 0x00, 0x00, 0x00]
            try:
                resp = send_and_recv(device, cmd, min_len=6)
                if resp:
                    level = resp[4]
                    status = resp[5]
                    # Map charging status (1=recharging, 2=charge in final stage, 3=complete, 4=slow recharge)
                    charging = status in (0x01, 0x02, 0x03, 0x04)
                    return BatteryResult(
                        percent=level,
                        voltage_mv=0,
                        charging=charging,
                        feature_used=hex(feature_id),
                    )
            except Exception:
                pass
    return None

def query_device_name(device, device_idx: int) -> str | None:
    feat_name = get_feature_index(device, device_idx, 0x0005)
    if feat_name is not None:
        cmd_len = [0x10, device_idx, feat_name, 0x01, 0, 0, 0]
        try:
            resp_len = send_and_recv(device, cmd_len, min_len=6)
            if resp_len:
                name_len = resp_len[4]
                name_bytes = bytearray()
                for offset in range(0, name_len, 3):
                    cmd_name = [0x10, device_idx, feat_name, 0x11, offset, 0, 0]
                    resp_name = send_and_recv(device, cmd_name, min_len=6)
                    if resp_name:
                        name_bytes.extend(resp_name[4:7])
                return name_bytes[:name_len].decode("utf-8", errors="ignore").strip()
        except Exception:
            pass
    return None


class LogitechDriver(BaseDriver):
    @property
    def supported_devices(self) -> dict[tuple[int, int], str]:
        return devices_for("logitech")

    @property
    def dev_idx(self) -> int:
        return DEVICE_IDX

    def find_devices(self, verbose: bool = False) -> list[dict]:
        vids = vendor_ids("logitech")
        try:
            from ui.settings_manager import load_config
            cfg = load_config()
            for device in cfg.get("custom_hid_devices", []):
                if device.get("driver", "").lower() == "logitech":
                    from drivers import _parse_id
                    vid = _parse_id(device.get("vid"))
                    if vid is not None:
                        vids.add(vid)
        except Exception:
            pass

        res = []
        seen_paths = set()
        for vid in vids:
            try:
                all_devices = hid.enumerate(vid, 0)
                for d in all_devices:
                    path = d.get("path")
                    if path in seen_paths:
                        continue
                    
                    pid = d.get("product_id")
                    usage_page = d.get("usage_page")
                    
                    # Logitech receivers (starting with 0xC5) use usage_page == 0xFF00
                    # Headsets (like G Pro X) use usage_page == 0xFF43
                    is_receiver = pid is not None and ((pid & 0xFF00) == 0xC500)
                    if is_receiver:
                        if usage_page == 0xFF00:
                            res.append(d)
                            seen_paths.add(path)
                    else:
                        if usage_page == 0xFF43:
                            res.append(d)
                            seen_paths.add(path)
            except Exception:
                pass
        return res

    def open_device(self, info: dict) -> object:
        return open_receiver(info)

    def probe_battery(self, handle, dev_idx: int):
        pid = handle.get("product_id") if isinstance(handle, dict) else None
        
        # Check if the opened handle corresponds to a receiver (PID 0xC5XX)
        is_receiver = pid is not None and ((pid & 0xFF00) == 0xC500)
        if is_receiver:
            results = {}
            # Try to query connected paired devices on channels 1 to 6
            for idx in range(1, 7):
                res = query_hidpp20_battery(handle, idx)
                if res is not None:
                    name = query_device_name(handle, idx)
                    if not name:
                        name = f"Logitech Device {idx}"
                    res.device_name = name
                    results[idx] = res
            
            # If receiver is online but no active child devices are reporting,
            # return a placeholder representing the connected receiver itself.
            if not results:
                receiver_name = self.supported_devices.get((0x046D, pid), "Logitech Receiver")
                results[0xFF] = BatteryResult(
                    percent=None,
                    voltage_mv=0,
                    charging=False,
                    feature_used="receiver",
                    device_name=receiver_name,
                )
            return results
        else:
            res = battery_probe_chain(handle, dev_idx)
            if res is not None:
                res.device_name = self.supported_devices.get((0x046D, pid), "G Pro X Wireless")
            return res

    def close_device(self, handle) -> None:
        try:
            handle.close()
        except Exception:
            pass
