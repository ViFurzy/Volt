import hid
from .base import BaseDriver
from hidpp.features import BatteryResult

class GenericDriver(BaseDriver):
    @property
    def supported_devices(self) -> dict[tuple[int, int], str]:
        devices = {
            (0x258A, 0x0150): "SinoWealth Gaming KB",
        }
        # Include custom generic devices from config
        try:
            from ui.settings_manager import load_config
            from drivers import _parse_id
            cfg = load_config()
            for device in cfg.get("custom_hid_devices", []):
                if device.get("driver", "").lower() == "generic":
                    vid = _parse_id(device.get("vid"))
                    pid = _parse_id(device.get("pid"))
                    name = device.get("name")
                    if vid is not None and pid is not None and name:
                        devices[(vid, pid)] = name
        except Exception:
            pass
        return devices

    @property
    def dev_idx(self) -> int:
        return 0x00

    def find_devices(self, verbose: bool = False) -> list[dict]:
        targets = {(0x258A, 0x0150)}
        try:
            from ui.settings_manager import load_config
            from drivers import _parse_id
            cfg = load_config()
            for device in cfg.get("custom_hid_devices", []):
                if device.get("driver", "").lower() == "generic":
                    vid = _parse_id(device.get("vid"))
                    pid = _parse_id(device.get("pid"))
                    if vid is not None and pid is not None:
                        targets.add((vid, pid))
        except Exception:
            pass

        res = []
        seen_devices = set()
        for vid, pid in targets:
            try:
                all_devices = hid.enumerate(vid, pid)
                # Filter to avoid opening the same physical device path multiple times
                for d in all_devices:
                    path = d.get("path")
                    if path in seen_devices:
                        continue
                    # Standard desktop controls/first interface is generally preferred
                    if d.get("interface_number", 0) == 0:
                        res.append(d)
                        seen_devices.add(path)
                        break
                else:
                    # Fallback to the first one found if no interface 0 exists
                    for d in all_devices:
                        path = d.get("path")
                        if path not in seen_devices:
                            res.append(d)
                            seen_devices.add(path)
                            break
            except Exception:
                pass
        return res

    def open_device(self, info: dict) -> object:
        device = hid.device()
        device.open_path(info["path"])
        return device

    def probe_battery(self, handle, dev_idx: int):
        return BatteryResult(
            percent=None,
            voltage_mv=0,
            charging=False,
            feature_used="generic",
        )
