"""
Integration test — queue end-to-end pipe: bg put → drain → consumer.

Tests the MonitorApp.drain() / consumer contract WITHOUT Qt, hardware, or
the asyncio bg thread. The bg-thread path is covered by test_service.py;
Win32 hot-plug debounce is covered by test_hotplug.py.

Strategy: inject DeviceState snapshots directly via app_obj.ui_queue.put(),
then call app_obj.drain() and assert the consumer received them in FIFO order.
"""

import queue

import pytest

from monitor.app import MonitorApp
from monitor.state import DeviceState, DeviceStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(
    device_name: str = "G Pro X Wireless",
    percent: int | None = 75,
    charging: bool = False,
    status: DeviceStatus = DeviceStatus.ONLINE,
) -> DeviceState:
    return DeviceState(
        vid=0x046D,
        pid=0x0ABA,
        dev_idx=0xFF,
        device_name=device_name,
        percent=percent,
        charging=charging,
        status=status,
    )


def _make_app() -> tuple[MonitorApp, list[DeviceState]]:
    """Return (app_obj, received) where received accumulates consumer calls."""
    received: list[DeviceState] = []
    app_obj = MonitorApp(consumer=received.append, poll_interval=60.0, drain_ms=500)
    return app_obj, received


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_drain_delivers_two_states_in_fifo_order():
    """Two snapshots put on the queue arrive at the consumer in insertion order."""
    app_obj, received = _make_app()

    state_a = _make_state(percent=80)
    state_b = _make_state(percent=60, status=DeviceStatus.CHARGING, charging=True)
    app_obj.ui_queue.put(state_a)
    app_obj.ui_queue.put(state_b)

    app_obj.drain()

    assert len(received) == 2
    assert received[0] is state_a
    assert received[1] is state_b


def test_drain_empties_the_queue():
    """After drain(), the queue must be empty."""
    app_obj, _ = _make_app()

    app_obj.ui_queue.put(_make_state())
    app_obj.drain()

    assert app_obj.ui_queue.empty()


def test_drain_on_empty_queue_does_not_raise():
    """Draining an empty queue must silently return — queue.Empty is handled."""
    app_obj, received = _make_app()

    app_obj.drain()  # must not raise

    assert received == []


def test_drain_delivers_offline_state():
    """An OFFLINE DeviceState (percent=None) is forwarded unchanged."""
    app_obj, received = _make_app()

    offline = _make_state(percent=None, status=DeviceStatus.OFFLINE)
    app_obj.ui_queue.put(offline)
    app_obj.drain()

    assert len(received) == 1
    assert received[0].status is DeviceStatus.OFFLINE
    assert received[0].percent is None


def test_drain_multiple_cycles():
    """Each drain() call delivers only the states that are in the queue at that moment."""
    app_obj, received = _make_app()

    # First batch
    app_obj.ui_queue.put(_make_state(percent=90))
    app_obj.drain()
    assert len(received) == 1

    # Second batch
    app_obj.ui_queue.put(_make_state(percent=50))
    app_obj.ui_queue.put(_make_state(percent=40))
    app_obj.drain()
    assert len(received) == 3  # 1 from first + 2 from second
