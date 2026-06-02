"""
G-series headset battery protocol for G Pro X Wireless.

Protocol confirmed in 02-01 hardware probe: 0xFF43 interface, device_idx=0xFF.
This is NOT a standard HID++ 2.0 feature discovery chain — it is a direct
G-series headset command using feature 0x06, function 0x0D.
"""

from dataclasses import dataclass

from hidpp.protocol import send_and_recv, HIDppError

# (mV, percent) calibration points for G Pro X Wireless from HeadsetControl reference
_CALIB = [(3320, 0), (3670, 5), (3740, 20), (3780, 30), (3830, 50), (4150, 100)]


@dataclass
class BatteryResult:
    percent: int
    charging: bool
    feature_used: str


def voltage_to_percent(mv: int) -> int:
    """Convert raw voltage (mV) to battery percentage using G Pro X piecewise calibration."""
    if mv <= _CALIB[0][0]:
        return 0
    if mv >= _CALIB[-1][0]:
        return 100
    for i in range(len(_CALIB) - 1):
        mv_lo, pct_lo = _CALIB[i]
        mv_hi, pct_hi = _CALIB[i + 1]
        if mv_lo <= mv <= mv_hi:
            frac = (mv - mv_lo) / (mv_hi - mv_lo)
            return round(pct_lo + frac * (pct_hi - pct_lo))
    return 0


def battery_probe_chain(device, device_idx: int) -> "BatteryResult | None":
    """
    Read battery from G Pro X Wireless via direct G-series headset command
    (feature 0x06, function 0x0D). Returns None on timeout (device offline or off).
    device_idx should be 0xFF (receiver device index for G-series headsets).
    """
    cmd = [0x11, device_idx, 0x06, 0x0D] + [0x00] * 16
    try:
        result = send_and_recv(device, cmd, min_len=7)
    except HIDppError:
        return None
    if result is None:
        return None
    voltage_mv = (result[4] << 8) | result[5]
    charging = result[6] == 0x03
    return BatteryResult(
        percent=voltage_to_percent(voltage_mv),
        charging=charging,
        feature_used="0x06/0x0D",
    )
