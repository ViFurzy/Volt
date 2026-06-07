import hid
from .base import BaseDriver
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

class LogitechDriver(BaseDriver):
    @property
    def supported_devices(self) -> dict[tuple[int, int], str]:
        return {
            (0x046D, 0x0ABA): "G Pro X Wireless",
            (0x046D, 0xC548): "Logitech Bolt Receiver",
            (0x046D, 0xC52B): "Logitech Unifying Receiver",
            (0x046D, 0xC53F): "Logitech Lightspeed Receiver",
            (0x046D, 0xC534): "Logitech Nano Receiver",
            (0x046D, 0xC52F): "Logitech Nano Receiver",
        }

    @property
    def dev_idx(self) -> int:
        return DEVICE_IDX

    def find_devices(self, verbose: bool = False) -> list[dict]:
        vids = {0x046D}
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
            # Try to query connected paired devices on channels 1 to 6
            for idx in range(1, 7):
                res = query_hidpp20_battery(handle, idx)
                if res is not None:
                    return res
            # If receiver is online but no active child devices are reporting,
            # return a placeholder representing the connected receiver itself.
            return BatteryResult(
                percent=None,
                voltage_mv=0,
                charging=False,
                feature_used="receiver",
            )
        else:
            return battery_probe_chain(handle, dev_idx)

    def close_device(self, handle) -> None:
        try:
            handle.close()
        except Exception:
            pass
