"""Device table: which (VID, PID) belongs to which driver.

The data lives in assets/devices.json so a new device is one line of data;
protocol code stays in the drivers.
"""
import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "assets" / "devices.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with _PATH.open(encoding="utf-8") as f:
        return json.load(f)


def devices_for(driver: str) -> dict[tuple[int, int], str]:
    """(VID, PID) -> name for every table entry handled by `driver`."""
    return {
        (int(d["vid"], 16), int(d["pid"], 16)): d["name"]
        for d in _load()["devices"]
        if d["driver"] == driver
    }


def vendor_ids(driver: str) -> set[int]:
    """USB vendor IDs whose unknown devices fall back to `driver`."""
    return {int(v, 16) for v, name in _load()["vendors"].items() if name == driver}


def driver_for_vendor(vid: int) -> str | None:
    """Driver name registered for this vendor ID, if any."""
    for v, name in _load()["vendors"].items():
        if int(v, 16) == vid:
            return name
    return None
