from .logitech import LogitechDriver
from .steelseries import SteelSeriesDriver
from .generic import GenericDriver

_DRIVERS = [
    LogitechDriver(),
    SteelSeriesDriver(),
    GenericDriver(),
]

def _parse_id(val) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val = val.strip()
        try:
            if val.lower().startswith("0x"):
                return int(val, 16)
            return int(val)
        except ValueError:
            return None
    return None

def get_all_drivers():
    return _DRIVERS

# ---------------------------------------------------------------------------
# Generation-aware cache for get_known_devices()
# ---------------------------------------------------------------------------
# Re-built only when settings_manager._config_generation changes, i.e. only
# after a save_config() call.  This prevents repeated disk I/O on the hot
# polling path (every 1-second _poll_loop tick calls KNOWN_DEVICES operations).
_known_devices_cache: dict[tuple[int, int], str] | None = None
_known_devices_generation: int = -1  # sentinel: -1 means "never built"


def _get_known_devices_generation() -> int:
    """Return the current config generation without importing the full module at module load."""
    try:
        from ui.settings_manager import get_config_generation
        return get_config_generation()
    except Exception:
        return 0


def get_known_devices() -> dict[tuple[int, int], str]:
    """Return the (vid, pid) → name registry, rebuilt only when config changes.

    First call always builds the cache.  Subsequent calls return the cached
    result unless save_config() has been called in between.
    """
    global _known_devices_cache, _known_devices_generation

    gen = _get_known_devices_generation()
    if _known_devices_cache is not None and gen == _known_devices_generation:
        return _known_devices_cache

    # ── Rebuild ────────────────────────────────────────────────────────
    res: dict[tuple[int, int], str] = {}

    # Static entries from each driver
    try:
        res.update(LogitechDriver().supported_devices)
        res.update(SteelSeriesDriver().supported_devices)
        res.update(GenericDriver().supported_devices)
    except Exception:
        pass

    # Dynamic entries from config (single load_config call covers both
    # custom_hid_devices and monitored_devices — fixes BUG-08)
    try:
        from ui.settings_manager import load_config
        cfg = load_config()

        for device in cfg.get("custom_hid_devices", []):
            vid = _parse_id(device.get("vid"))
            pid = _parse_id(device.get("pid"))
            name = device.get("name")
            if vid is not None and pid is not None and name:
                res[(vid, pid)] = name

        for device in cfg.get("monitored_devices", []):
            if device.get("type") == "hid":
                hid_id = device.get("id", "")
                parts = hid_id.split(":")
                if len(parts) == 3:
                    try:
                        vid = int(parts[1], 16)
                        pid = int(parts[2], 16)
                        name = device.get("name")
                        if vid is not None and pid is not None and name:
                            res[(vid, pid)] = name
                    except Exception:
                        pass
    except Exception:
        pass

    _known_devices_cache = res
    _known_devices_generation = gen
    return res


def get_driver_for_device(vid: int, pid: int):
    try:
        from ui.settings_manager import load_config
        cfg = load_config()
        for device in cfg.get("custom_hid_devices", []):
            d_vid = _parse_id(device.get("vid"))
            d_pid = _parse_id(device.get("pid"))
            if d_vid == vid and d_pid == pid:
                driver_name = device.get("driver", "").lower()
                for d in get_all_drivers():
                    if d.__class__.__name__.lower().startswith(driver_name):
                        return d
    except Exception:
        pass

    for d in get_all_drivers():
        if (vid, pid) in d.supported_devices:
            return d

    # Fallback to driver by VID if not explicitly matched
    if vid == 0x046D:
        from .logitech import LogitechDriver
        return LogitechDriver()
    elif vid == 0x1038:
        from .steelseries import SteelSeriesDriver
        return SteelSeriesDriver()
    elif vid == 0x258A:
        from .generic import GenericDriver
        return GenericDriver()

    from .generic import GenericDriver
    return GenericDriver()
