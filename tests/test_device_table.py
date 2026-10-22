"""Tests for drivers.table (assets/devices.json) and its use by the drivers."""
import json

from drivers import get_all_drivers, get_driver_for_device
from drivers.table import _PATH, devices_for, driver_for_vendor, vendor_ids

DRIVER_NAMES = {"logitech", "steelseries", "generic"}


def test_table_entries_are_well_formed_and_unique():
    data = json.loads(_PATH.read_text(encoding="utf-8"))
    keys = [(d["vid"].upper(), d["pid"].upper()) for d in data["devices"]]
    assert len(keys) == len(set(keys))
    assert {d["driver"] for d in data["devices"]} <= DRIVER_NAMES
    assert set(data["vendors"].values()) <= DRIVER_NAMES


def test_table_matches_devices_that_used_to_be_hardcoded():
    assert devices_for("logitech") == {
        (0x046D, 0x0ABA): "G Pro X Wireless",
        (0x046D, 0xC548): "Logitech Bolt Receiver",
        (0x046D, 0xC52B): "Logitech Unifying Receiver",
        (0x046D, 0xC53F): "Logitech Lightspeed Receiver",
        (0x046D, 0xC534): "Logitech Nano Receiver",
        (0x046D, 0xC52F): "Logitech Nano Receiver",
    }
    assert devices_for("steelseries") == {(0x1038, 0x1852): "Aerox 5 Wireless"}
    assert devices_for("generic") == {(0x258A, 0x0150): "SinoWealth Gaming KB"}


def test_vendor_lookup():
    assert vendor_ids("logitech") == {0x046D}
    assert driver_for_vendor(0x1038) == "steelseries"
    assert driver_for_vendor(0x9999) is None


def test_every_table_device_is_served_by_its_driver():
    by_name = {d.__class__.__name__.lower().removesuffix("driver"): d for d in get_all_drivers()}
    for name in DRIVER_NAMES:
        for key, dev_name in devices_for(name).items():
            assert by_name[name].supported_devices[key] == dev_name
            assert get_driver_for_device(*key) is by_name[name]
