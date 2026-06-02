"""
Unit tests for HotPlugWatcher debounce logic (03-03).

Tests drive _Debouncer directly (no QWidget, no Win32 messages, no hardware).
A real asyncio.new_event_loop() is used to run timers so timing semantics are exact.

Coverage:
  - Five rapid schedule() calls → exactly 1 rescan (D-08 cancel+reschedule)
  - Each repeat call cancels the previous pending handle
  - One schedule() + elapsed debounce → exactly 1 rescan
  - Two calls separated by a full debounce window → 2 rescans
"""

import asyncio
import pytest
from unittest.mock import MagicMock

from monitor.hotplug import _Debouncer

DEBOUNCE = 0.05  # short debounce for fast tests (50ms)


@pytest.fixture
def event_loop():
    """Provide a fresh event loop for each test; close after."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_callback():
    return MagicMock()


# ---------------------------------------------------------------------------
# Helper: run the loop long enough for timers to fire
# ---------------------------------------------------------------------------

def _advance(loop: asyncio.AbstractEventLoop, seconds: float) -> None:
    """Run the loop for `seconds` of real time (enough for call_later timers to fire)."""
    loop.run_until_complete(asyncio.sleep(seconds))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDebouncerCollapse:
    """Five rapid schedule() calls within the window → one callback."""

    def test_five_rapid_calls_produce_one_callback(self, event_loop, mock_callback):
        debouncer = _Debouncer(event_loop, DEBOUNCE, mock_callback)

        # Schedule 5 times back-to-back (all within the debounce window)
        for _ in range(5):
            event_loop.call_soon(debouncer.schedule)

        # Let scheduled callbacks run, then advance past the debounce window
        _advance(event_loop, DEBOUNCE * 3)

        assert mock_callback.call_count == 1

    def test_repeated_calls_cancel_previous_handle(self, event_loop, mock_callback):
        """After 3 rapid schedules the pending handle should still be a single timer."""
        debouncer = _Debouncer(event_loop, DEBOUNCE, mock_callback)

        for _ in range(3):
            event_loop.call_soon(debouncer.schedule)

        # Before advancing: handle exists (timer not yet fired)
        event_loop.run_until_complete(asyncio.sleep(0))  # drain call_soon queue

        # Exactly one pending handle (others were cancelled)
        # We can't inspect the handle count directly, but firing should give exactly 1 call
        _advance(event_loop, DEBOUNCE * 3)
        assert mock_callback.call_count == 1


class TestDebouncerSingleSchedule:
    """One schedule() → one callback after the window."""

    def test_single_schedule_fires_once(self, event_loop, mock_callback):
        debouncer = _Debouncer(event_loop, DEBOUNCE, mock_callback)

        event_loop.call_soon(debouncer.schedule)
        _advance(event_loop, DEBOUNCE * 3)

        assert mock_callback.call_count == 1


class TestDebouncerSeparateWindows:
    """Two calls separated by a full debounce window → two callbacks."""

    def test_two_windows_produce_two_callbacks(self, event_loop, mock_callback):
        debouncer = _Debouncer(event_loop, DEBOUNCE, mock_callback)

        # First schedule — let it fire
        event_loop.call_soon(debouncer.schedule)
        _advance(event_loop, DEBOUNCE * 3)
        assert mock_callback.call_count == 1

        # Second schedule — let it fire independently
        event_loop.call_soon(debouncer.schedule)
        _advance(event_loop, DEBOUNCE * 3)
        assert mock_callback.call_count == 2


class TestDebouncerNoEarlyFire:
    """Callback must NOT fire before the debounce window elapses."""

    def test_no_early_fire(self, event_loop, mock_callback):
        debouncer = _Debouncer(event_loop, DEBOUNCE, mock_callback)

        event_loop.call_soon(debouncer.schedule)
        # Advance only to 20% of the window — should not have fired yet
        _advance(event_loop, DEBOUNCE * 0.2)
        assert mock_callback.call_count == 0

        # Now advance past the window — should fire
        _advance(event_loop, DEBOUNCE * 3)
        assert mock_callback.call_count == 1
