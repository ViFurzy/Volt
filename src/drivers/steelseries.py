import os
import sqlite3
import shutil
import tempfile
import glob

from .base import BaseDriver
from steelseries.driver import SS_DEVICE_IDX, find_dongle, open_dongle, ss_battery_probe
from hidpp.features import BatteryResult

def get_steelseries_db_path() -> str | None:
    program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
    paths = [
        os.path.join(program_data, "SteelSeries", "GG", "apps", "engine", "db", "database.db"),
        os.path.join(program_data, "SteelSeries", "SteelSeries Engine 3", "db", "database.db"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    wildcard_pattern = os.path.join(program_data, "SteelSeries", "**", "engine", "db", "database.db")
    found = glob.glob(wildcard_pattern, recursive=True)
    if found:
        return found[0]
    return None

def load_devices_from_db() -> dict[tuple[int, int], str]:
    devices = {}
    db_path = get_steelseries_db_path()
    if not db_path:
        return devices
    temp_dir = tempfile.gettempdir()
    temp_db = os.path.join(temp_dir, "ss_engine_temp.db")
    try:
        shutil.copy2(db_path, temp_db)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT product_id, connected_product_id, full_name, name FROM devices")
        for prod_id, conn_prod_id, full_name, name in cursor.fetchall():
            display_name = full_name or name or "SteelSeries Device"
            if prod_id:
                vid = (prod_id >> 16) & 0xFFFF
                pid = prod_id & 0xFFFF
                if vid == 0x1038:
                    devices[(vid, pid)] = display_name
            if conn_prod_id:
                vid = (conn_prod_id >> 16) & 0xFFFF
                pid = conn_prod_id & 0xFFFF
                if vid == 0x1038:
                    devices[(vid, pid)] = display_name
        conn.close()
    except Exception:
        pass
    finally:
        if os.path.exists(temp_db):
            try:
                os.remove(temp_db)
            except Exception:
                pass
    return devices

def ss_headset_battery_probe(device, pid: int) -> "BatteryResult | None":
    # Category 2: Nova Pro Wireless Base Station (0x12E0, 0x12E5)
    if pid in (0x12E0, 0x12E5):
        # Warmup reads
        for _ in range(3):
            device.read(64, timeout_ms=50)
        # Write [0x06, 0xb0] padded to 31 bytes
        device.write([0x00, 0x06, 0xb0] + [0] * 29)
        
        resp = None
        for _ in range(20):
            r = device.read(64, timeout_ms=100)
            if r and r[0] in (0x06, 0xb0):
                resp = list(r)
                break
        if not resp or len(resp) < 16:
            return None
            
        status_byte = resp[15]
        if status_byte == 0x01:  # HEADSET_OFFLINE
            return None
        charging = (status_byte == 0x02)  # HEADSET_CABLE_CHARGING
        level_raw = resp[6]
        level = level_raw * 100 // 8
        level = max(0, min(100, level))
        return BatteryResult(
            percent=level,
            voltage_mv=0,
            charging=charging,
            feature_used="0x06,0xb0",
        )
        
    # Category 3: Nova 5 / 5X (0x2232, 0x2253)
    elif pid in (0x2232, 0x2253):
        # Warmup reads
        for _ in range(3):
            device.read(64, timeout_ms=50)
        device.write([0x00, 0xb0])
        
        resp = None
        for _ in range(20):
            r = device.read(64, timeout_ms=100)
            if r and r[0] == 0xb0:
                resp = list(r)
                break
        if not resp or len(resp) < 16:
            return None
            
        if resp[1] == 0x02:  # HEADSET_OFFLINE
            return None
        charging = (resp[4] == 0x01)
        level = max(0, min(100, resp[3]))
        return BatteryResult(
            percent=level,
            voltage_mv=0,
            charging=charging,
            feature_used="0x00,0xb0",
        )
        
    # Category 4: Other Nova headsets (0x12XX, 0x22XX, 0x23XX)
    else:
        # Warmup reads
        for _ in range(3):
            device.read(64, timeout_ms=50)
        device.write([0x00, 0xb0])
        
        resp = None
        for _ in range(20):
            r = device.read(64, timeout_ms=100)
            if r and r[0] == 0xb0:
                resp = list(r)
                break
        if not resp or len(resp) < 4:
            return None
            
        status_byte = resp[3]
        if status_byte == 0x00:  # HEADSET_OFFLINE
            return None
        charging = status_byte in (0x01, 0x02)
        level_raw = resp[2]
        
        # Discrete models map 0-4 to 0-100
        discrete_pids = {0x2202, 0x2206, 0x220A, 0x223A, 0x227A, 0x2244, 0x2249}
        if pid in discrete_pids:
            level = level_raw * 25
        else:
            level = level_raw
            
        level = max(0, min(100, level))
        return BatteryResult(
            percent=level,
            voltage_mv=0,
            charging=charging,
            feature_used="0x00,0xb0",
        )

class SteelSeriesDriver(BaseDriver):
    _cached_supported_devices = None

    @property
    def supported_devices(self) -> dict[tuple[int, int], str]:
        if SteelSeriesDriver._cached_supported_devices is None:
            devices = {
                (0x1038, 0x1852): "Aerox 5 Wireless",
            }
            try:
                devices.update(load_devices_from_db())
            except Exception:
                pass
            SteelSeriesDriver._cached_supported_devices = devices
        return SteelSeriesDriver._cached_supported_devices

    @property
    def dev_idx(self) -> int:
        return SS_DEVICE_IDX

    def find_devices(self, verbose: bool = False) -> list[dict]:
        vids = {0x1038}
        try:
            from ui.settings_manager import load_config
            cfg = load_config()
            for device in cfg.get("custom_hid_devices", []):
                if device.get("driver", "").lower() == "steelseries":
                    from drivers import _parse_id
                    vid = _parse_id(device.get("vid"))
                    if vid is not None:
                        vids.add(vid)
        except Exception:
            pass

        res = []
        for vid in vids:
            try:
                res.extend(find_dongle(vid=vid, verbose=verbose))
            except Exception:
                pass
        return res

    def open_device(self, info: dict) -> object:
        # SteelSeries responds once per open handle, so we store the info dict
        return info

    def probe_battery(self, handle, dev_idx: int):
        # 'handle' is the info dict
        fresh_handle = None
        try:
            fresh_handle = open_dongle(handle)
            pid = handle.get("product_id")
            # If the Product ID corresponds to an audio device (PIDs 0x12XX, 0x22XX, 0x23XX)
            if pid is not None and ((pid >> 8) in (0x12, 0x22, 0x23)):
                return ss_headset_battery_probe(fresh_handle, pid)
            else:
                return ss_battery_probe(fresh_handle, dev_idx)
        except OSError:
            return None
        finally:
            if fresh_handle is not None:
                try:
                    fresh_handle.close()
                except Exception:
                    pass

    def close_device(self, handle) -> None:
        pass
