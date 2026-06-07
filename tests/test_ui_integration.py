"""Headless end-to-end integration test: queue → drain → on_device_update → DeviceCard.

Strategy (mirrors Phase 3 test_integration.py conventions):
  - Build a real MainWindow and a real MonitorApp wired together.
  - Inject DeviceState directly via app_obj.ui_queue.put().
  - Call app_obj.drain() on the main thread — no start(), no asyncio bg thread, no real HID.
  - Assert that window._cards and DeviceCard labels reflect what was put on the queue.

pytest-qt's qapp fixture provides the required QApplication singleton.
NEVER call window.show() or tray.show() in headless tests.
"""

import pytest

from monitor.app import MonitorApp
from monitor.state import DeviceState, DeviceStatus
from ui.main_window import MainWindow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(
    vid: int = 0x046D,
    pid: int = 0x0ABA,
    dev_idx: int = 0,
    device_name: str = "G Pro X Wireless",
    percent: int | None = 80,
    charging: bool = False,
    status: DeviceStatus = DeviceStatus.ONLINE,
) -> DeviceState:
    return DeviceState(
        vid=vid,
        pid=pid,
        dev_idx=dev_idx,
        device_name=device_name,
        percent=percent,
        charging=charging,
        status=status,
    )


def _make_wired(qapp) -> tuple[MonitorApp, MainWindow]:
    """Return (app_obj, window) with consumer wired — no start() called."""
    window = MainWindow()
    app_obj = MonitorApp(consumer=window.on_device_update, poll_interval=60.0, drain_ms=500)
    return app_obj, window


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestQueueDrainToCard:
    def test_drain_creates_card_for_online_device(self, qapp):
        """Draining an ONLINE DeviceState creates exactly one DeviceCard."""
        app_obj, window = _make_wired(qapp)
        state = _make_state(percent=80, status=DeviceStatus.ONLINE)

        app_obj.ui_queue.put(state)
        app_obj.drain()

        assert len(window._cards) == 1

    def test_drain_card_reflects_percent_online(self, qapp):
        """Card labels reflect the 80% ONLINE state after drain."""
        app_obj, window = _make_wired(qapp)
        state = _make_state(percent=80, status=DeviceStatus.ONLINE)

        app_obj.ui_queue.put(state)
        app_obj.drain()

        key = (0x046D, 0x0ABA, 0)
        card = window._cards[key]
        assert card._percent.text() == "80%"
        assert card._status.text() == "ONLINE"

    def test_drain_followup_updates_card_in_place(self, qapp):
        """Follow-up drain for the same device updates the existing card — no duplicate."""
        app_obj, window = _make_wired(qapp)
        state_online = _make_state(percent=80, status=DeviceStatus.ONLINE)
        state_offline = _make_state(percent=None, status=DeviceStatus.OFFLINE)

        app_obj.ui_queue.put(state_online)
        app_obj.drain()
        assert len(window._cards) == 1

        app_obj.ui_queue.put(state_offline)
        app_obj.drain()

        # Still exactly one card — updated in place, not duplicated
        assert len(window._cards) == 1

    def test_drain_followup_reflects_offline_state(self, qapp):
        """After OFFLINE follow-up, card shows '--' percent and OFFLINE status."""
        app_obj, window = _make_wired(qapp)
        state_online = _make_state(percent=80, status=DeviceStatus.ONLINE)
        state_offline = _make_state(percent=None, status=DeviceStatus.OFFLINE)

        app_obj.ui_queue.put(state_online)
        app_obj.drain()
        app_obj.ui_queue.put(state_offline)
        app_obj.drain()

        key = (0x046D, 0x0ABA, 0)
        card = window._cards[key]
        assert card._percent.text() == "--"
        assert card._status.text() == "OFFLINE"

    def test_drain_offline_card_has_offline_property(self, qapp):
        """OFFLINE card has Qt property 'offline' set to True for QSS muting."""
        app_obj, window = _make_wired(qapp)
        state_offline = _make_state(percent=None, status=DeviceStatus.OFFLINE)

        app_obj.ui_queue.put(state_offline)
        app_obj.drain()

        key = (0x046D, 0x0ABA, 0)
        card = window._cards[key]
        assert card.property("offline") is True

    def test_drain_second_device_creates_second_card(self, qapp):
        """DeviceState for a second (vid,pid,dev_idx) creates a second card."""
        app_obj, window = _make_wired(qapp)
        state_a = _make_state(vid=0x046D, pid=0x0ABA, dev_idx=0, percent=80)
        state_b = _make_state(vid=0x046D, pid=0x0ABA, dev_idx=1, percent=60)

        app_obj.ui_queue.put(state_a)
        app_obj.ui_queue.put(state_b)
        app_obj.drain()

        assert len(window._cards) == 2

    def test_drain_empty_queue_no_cards_created(self, qapp):
        """Draining an empty queue creates no cards and does not raise."""
        app_obj, window = _make_wired(qapp)

        app_obj.drain()  # must not raise

        assert len(window._cards) == 0

    def test_no_start_called_no_hid_thread(self, qapp):
        """MonitorApp.start() is never called — confirms test is hardware-free."""
        # If start() were called, MonitorService would spin up an asyncio thread
        # and attempt real HID enumeration. This test passing in CI confirms
        # that drain() works without start().
        app_obj, window = _make_wired(qapp)
        state = _make_state(percent=50)

        app_obj.ui_queue.put(state)
        app_obj.drain()

        assert len(window._cards) == 1
