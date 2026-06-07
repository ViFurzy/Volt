"""
DeviceState snapshot dataclass, DeviceStatus enum, and KNOWN_DEVICES registry.

These are the locked data-model contracts (D-01 through D-05) consumed by every
other module in this package. No config-file loading — KNOWN_DEVICES is a
hardcoded Python dict until multi-user customisation is required (deferred).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from drivers import get_known_devices


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


class KnownDevicesDict(dict):
    def _get_map(self) -> dict[tuple[int, int], str]:
        return get_known_devices()

    def __contains__(self, key: object) -> bool:
        return key in self._get_map()

    def __getitem__(self, key: tuple[int, int]) -> str:
        return self._get_map()[key]

    def get(self, key: tuple[int, int], default: str | None = None) -> str | None:  # type: ignore[override]
        return self._get_map().get(key, default)

    def keys(self):
        return self._get_map().keys()

    def values(self):
        return self._get_map().values()

    def items(self):
        return self._get_map().items()

    def __len__(self) -> int:
        return len(self._get_map())

    def __repr__(self) -> str:
        return repr(self._get_map())

    def __bool__(self) -> bool:
        return bool(self._get_map())


# Hardcoded/Configured VID/PID → human-readable name registry (D-04, D-05).
# device_name in DeviceState always comes from this lookup — never from
# hid.enumerate()'s product_string (which can change across firmware updates).
KNOWN_DEVICES: dict[tuple[int, int], str] = KnownDevicesDict()
