"""
DeviceState snapshot dataclass, DeviceStatus enum, and KNOWN_DEVICES registry.

These are the locked data-model contracts (D-01 through D-05) consumed by every
other module in this package. No config-file loading — KNOWN_DEVICES is a
hardcoded Python dict until multi-user customisation is required (deferred).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from hidpp.features import battery_probe_chain
from steelseries.driver import ss_battery_probe


class DeviceStatus(enum.Enum):
    """Three-state device status (D-03).

    ONLINE    — device reachable, discharging.
    OFFLINE   — device unreachable (turned off, disconnected, or poll failed).
    CHARGING  — device reachable and charging cable detected.
    """

    ONLINE = enum.auto()
    OFFLINE = enum.auto()
    CHARGING = enum.auto()


@dataclass(frozen=True)
class DeviceState:
    """Full snapshot of one peripheral's current state (D-01, D-02).

    Fields are in the locked order from D-01. Consumers MUST treat instances
    as immutable snapshots; use dataclasses.replace() to produce updated copies.

    percent is None when the device is OFFLINE (no battery reading available).
    """

    vid: int
    pid: int
    dev_idx: int
    device_name: str
    percent: int | None
    charging: bool
    status: DeviceStatus


@dataclass(frozen=True)
class BtDeviceInfo:
    """Snapshot of a discovered Bluetooth device (BT-01).

    bt_id is the WinRT DeviceInformation.id string (stable across reboots).
    ble_address is None for classic Bluetooth (BR/EDR) devices.
    battery is None when no tier resolved a value.
    """

    bt_id: str
    name: str
    battery: int | None
    ble_address: str | None
    status: DeviceStatus


@dataclass(frozen=True)
class BtScanResultEvent:
    """Event put on _ui_queue when a BT scan completes (BT-03).

    Consumed by MonitorApp.drain() -> DevicesPage.on_scan_result().
    devices contains both BT entries (type='bt') from winrt_enumerate_bt()
    and HID entries (type='hid') from hid.enumerate().
    """

    devices: list[dict]


# Hardcoded VID/PID → human-readable name registry (D-04, D-05).
# device_name in DeviceState always comes from this lookup — never from
# hid.enumerate()'s product_string (which can change across firmware updates).
KNOWN_DEVICES: dict[tuple[int, int], str] = {
    (0x046D, 0x0ABA): "G Pro X Wireless",
    (0x1038, 0x1852): "Aerox 5 Wireless",
}

# Probe function registry: (vid, pid) → (device_or_info, dev_idx) → BatteryResult | None.
# For Logitech, the first argument is an open hid.device handle.
# For SteelSeries, the first argument is the info dict (open_dongle is called
# per-poll inside poll_once — the dongle responds exactly once per device open).
DEVICE_PROBES: dict[tuple[int, int], callable] = {
    (0x046D, 0x0ABA): battery_probe_chain,
    (0x1038, 0x1852): ss_battery_probe,
}
