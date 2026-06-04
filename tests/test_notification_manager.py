"""Unit tests for NotificationManager — no real WinRT calls."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from monitor.state import DeviceState, DeviceStatus
from ui.notification_manager import NotificationManager


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def _make_state(percent=10, status=DeviceStatus.ONLINE, charging=False):
    return DeviceState(
        vid=0x046D,
        pid=0x0ABA,
        dev_idx=0xFF,
        device_name="G Pro X Wireless",
        percent=percent,
        charging=charging,
        status=status,
    )


# ---------------------------------------------------------------------------
# NOTIF-01: Threshold crossing
# ---------------------------------------------------------------------------

def test_fires_on_threshold_crossing():
    """Toast fires when percent is below threshold and device is ONLINE."""
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        mgr.check(_make_state(percent=10), {"thresholds": {}})

        mock_toaster.show_toast.assert_called_once()


def test_no_fire_above_threshold():
    """Toast does NOT fire when percent is above default threshold (15%)."""
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        mgr.check(_make_state(percent=20), {"thresholds": {}})

        mock_toaster.show_toast.assert_not_called()


def test_no_fire_when_percent_none():
    """Toast does NOT fire when percent is None (charging or transitional)."""
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        mgr.check(_make_state(percent=None, status=DeviceStatus.ONLINE), {"thresholds": {}})

        mock_toaster.show_toast.assert_not_called()


def test_default_threshold():
    """Default threshold is 15%: percent=14 (just below 15) fires; this tests the default."""
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        # No per-device config entry — defaults apply
        mgr.check(_make_state(percent=14), {"thresholds": {}})

        mock_toaster.show_toast.assert_called_once()


# ---------------------------------------------------------------------------
# NOTIF-02: Cooldown suppression and reset
# ---------------------------------------------------------------------------

def test_cooldown_suppresses():
    """Second check() call within cooldown window does NOT fire a second toast."""
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        config = {"thresholds": {}}

        # First call — should fire
        mgr.check(_make_state(percent=10), config)
        # Second call immediately — should be suppressed by cooldown
        mgr.check(_make_state(percent=10), config)

        mock_toaster.show_toast.assert_called_once()


def test_fires_after_cooldown():
    """Toast fires again after the cooldown period has expired (time-travel test)."""
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        key = (0x046D, 0x0ABA, 0xFF)
        # Plant an expired timestamp (5 hours ago; default cooldown is 4h)
        mgr._last_notified[key] = datetime.now() - timedelta(hours=5)

        mgr.check(_make_state(percent=10), {"thresholds": {}})

        mock_toaster.show_toast.assert_called_once()


def test_cooldown_resets_on_offline():
    """Cooldown entry is cleared when device goes OFFLINE."""
    with patch("ui.notification_manager.WindowsToaster") as MockToaster:
        mock_toaster = MagicMock()
        MockToaster.return_value = mock_toaster

        mgr = NotificationManager()
        config = {"thresholds": {}}
        key = (0x046D, 0x0ABA, 0xFF)

        # First call — fires and plants cooldown entry
        mgr.check(_make_state(percent=10, status=DeviceStatus.ONLINE), config)
        assert key in mgr._last_notified

        # OFFLINE call — should clear the cooldown entry
        mgr.check(_make_state(percent=None, status=DeviceStatus.OFFLINE), config)
        assert key not in mgr._last_notified
