"""Notification dispatch and cooldown tracking for Volt.

No Qt imports — pure stdlib so tests run headlessly.
Instantiated in __main__.py; check() called from main-thread drain path.
"""
from __future__ import annotations

from datetime import datetime

from windows_toasts import Toast, WindowsToaster

from monitor.state import DeviceState, BtDeviceInfo, DeviceStatus


class NotificationManager:
    def __init__(self) -> None:
        self._toaster = WindowsToaster("Volt")
        self._last_notified: dict[str, datetime] = {}

    def check(self, state: DeviceState | BtDeviceInfo, config: dict) -> None:
        if isinstance(state, BtDeviceInfo):
            device_id = state.bt_id
            name = state.name
            percent = state.battery
            status = state.status
        else:
            device_id = f"hid:{state.vid:04X}:{state.pid:04X}"
            name = state.device_name
            percent = state.percent
            status = state.status

        if status == DeviceStatus.OFFLINE:
            self._last_notified.pop(device_id, None)
            return

        if percent is None:
            return

        thresholds = config.get("thresholds", {})
        device_cfg = thresholds.get(device_id, {})
        
        # Fallback to old key format for existing configs
        if not device_cfg and not isinstance(state, BtDeviceInfo):
            old_key = f"{state.vid}:{state.pid}"
            device_cfg = thresholds.get(old_key, {})

        raw_threshold = device_cfg.get("threshold_pct", 15)
        if raw_threshold is None:
            return
            
        threshold = max(1, min(99, int(raw_threshold)))
        cooldown_hours = device_cfg.get("cooldown_hours", 4)

        if percent >= threshold:
            return

        last = self._last_notified.get(device_id)
        if last is not None:
            elapsed = (datetime.now() - last).total_seconds() / 3600
            if elapsed < cooldown_hours:
                return

        toast = Toast(text_fields=[
            f"{name} battery low",
            f"Battery at {percent}% — charge soon",
        ])
        self._toaster.show_toast(toast)
        self._last_notified[device_id] = datetime.now()
