"""Notification dispatch and cooldown tracking for PeriphWatcher.

No Qt imports — pure stdlib so tests run headlessly.
Instantiated in __main__.py; check() called from main-thread drain path.
"""
from __future__ import annotations

from datetime import datetime

from windows_toasts import Toast, WindowsToaster

from monitor.state import DeviceState, DeviceStatus


class NotificationManager:
    def __init__(self) -> None:
        self._toaster = WindowsToaster("PeriphWatcher")
        self._last_notified: dict[tuple[int, int, int], datetime] = {}

    def check(self, state: DeviceState, config: dict) -> None:
        key = (state.vid, state.pid, state.dev_idx)

        if state.status == DeviceStatus.OFFLINE:
            self._last_notified.pop(key, None)
            return

        if state.percent is None:
            return

        thresholds = config.get("thresholds", {})
        device_cfg = thresholds.get(f"{state.vid}:{state.pid}", {})
        threshold = max(1, min(99, int(device_cfg.get("threshold_pct", 15))))
        cooldown_hours = device_cfg.get("cooldown_hours", 4)

        if state.percent >= threshold:
            return

        last = self._last_notified.get(key)
        if last is not None:
            elapsed = (datetime.now() - last).total_seconds() / 3600
            if elapsed < cooldown_hours:
                return

        toast = Toast(text_fields=[
            f"{state.device_name} battery low",
            f"Battery at {state.percent}% — charge soon",
        ])
        self._toaster.show_toast(toast)
        self._last_notified[key] = datetime.now()
