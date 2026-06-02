"""
DeviceState snapshot dataclass, DeviceStatus enum, and KNOWN_DEVICES registry.

These are the locked data-model contracts (D-01 through D-05) consumed by every
other module in this package. No config-file loading — KNOWN_DEVICES is a
hardcoded Python dict until multi-user customisation is required (deferred).
"""

import enum
from dataclasses import dataclass


class DeviceStatus(enum.Enum):
    """Three-state device status (D-03).

    ONLINE    — device reachable, discharging.
    OFFLINE   — device unreachable (turned off, disconnected, or poll failed).
    CHARGING  — device reachable and charging cable detected.
    """

    ONLINE = enum.auto()
    OFFLINE = enum.auto()
    CHARGING = enum.auto()


@dataclass
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


# Hardcoded VID/PID → human-readable name registry (D-04, D-05).
# device_name in DeviceState always comes from this lookup — never from
# hid.enumerate()'s product_string (which can change across firmware updates).
# Phase 5 adds the SteelSeries Aerox 5 Wireless by appending an entry here.
KNOWN_DEVICES: dict[tuple[int, int], str] = {
    (0x046D, 0x0ABA): "G Pro X Wireless",
}
