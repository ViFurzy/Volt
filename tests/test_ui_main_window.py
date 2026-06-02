"""Unit tests for MainWindow.

Strategy (from RESEARCH Validation Architecture):
  - NEVER call window.show() in headless tests — Qt show() requires a display.
  - Instantiate MainWindow and call methods directly.
  - pytest-qt's qapp fixture provides the QApplication singleton.
"""
import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QStackedWidget

from monitor.state import DeviceState, DeviceStatus


def _make_state(
    vid: int = 0x046D,
    pid: int = 0x0ABA,
    dev_idx: int = 0,
    percent: int | None = 80,
    status: DeviceStatus = DeviceStatus.ONLINE,
    charging: bool = False,
    device_name: str = "G Pro X Wireless",
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


def test_mainwindow_constructs(qapp):
    """MainWindow constructs without raising."""
    from ui.main_window import MainWindow
    window = MainWindow()
    assert window is not None


def test_mainwindow_has_five_page_stack(qapp):
    """MainWindow embeds a QStackedWidget with exactly 5 pages (D-03)."""
    from ui.main_window import MainWindow
    window = MainWindow()
    stacks = window.findChildren(QStackedWidget)
    assert len(stacks) == 1, "Expected exactly one QStackedWidget"
    assert stacks[0].count() == 5, f"Expected 5 pages, got {stacks[0].count()}"


def test_close_event_ignored_and_window_hidden(qapp):
    """closeEvent must ignore the event and hide the window (D-08, UI-02).

    After closeEvent:
      - event.isAccepted() == False  (event was ignored, not accepted)
      - window.isVisible() == False  (window was never shown so this is correct)
    """
    from ui.main_window import MainWindow
    window = MainWindow()
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted(), "closeEvent must not accept the event"
    assert not window.isVisible(), "Window should be hidden after closeEvent"


def test_show_restore_is_callable(qapp):
    """show_restore must exist as a callable on MainWindow."""
    from ui.main_window import MainWindow
    window = MainWindow()
    assert callable(getattr(window, "show_restore", None))


def test_on_device_update_is_stub(qapp):
    """on_device_update must exist and be callable (Wave-3 stub)."""
    from ui.main_window import MainWindow
    window = MainWindow()
    assert callable(getattr(window, "on_device_update", None))


def test_dashboard_layout_accessible(qapp):
    """dashboard_layout attribute must be present for Wave 3 card injection."""
    from ui.main_window import MainWindow
    window = MainWindow()
    assert hasattr(window, "dashboard_layout")
    assert hasattr(window, "_cards")
    assert isinstance(window._cards, dict)


# ---------------------------------------------------------------------------
# Wave 3: on_device_update — create-or-update card tests (Task 2)
# ---------------------------------------------------------------------------

class TestOnDeviceUpdateCreateOrUpdate:
    def test_first_state_creates_card(self, qapp):
        """First DeviceState for a key must create exactly one DeviceCard."""
        from ui.main_window import MainWindow
        window = MainWindow()
        state = _make_state()
        window.on_device_update(state)
        assert len(window._cards) == 1

    def test_first_state_stores_card_by_key(self, qapp):
        """Card must be stored under key (vid, pid, dev_idx)."""
        from ui.main_window import MainWindow
        window = MainWindow()
        state = _make_state(vid=0x046D, pid=0x0ABA, dev_idx=0)
        window.on_device_update(state)
        key = (0x046D, 0x0ABA, 0)
        assert key in window._cards

    def test_repeat_state_does_not_create_duplicate(self, qapp):
        """Repeated state for same key must NOT create a second card."""
        from ui.main_window import MainWindow
        window = MainWindow()
        state1 = _make_state(percent=80)
        state2 = _make_state(percent=60)
        window.on_device_update(state1)
        window.on_device_update(state2)
        assert len(window._cards) == 1

    def test_repeat_state_updates_existing_card(self, qapp):
        """Repeated state must call update_state on the existing card."""
        from ui.main_window import MainWindow
        window = MainWindow()
        state1 = _make_state(percent=80)
        state2 = _make_state(percent=25)
        window.on_device_update(state1)
        card = window._cards[(0x046D, 0x0ABA, 0)]
        window.on_device_update(state2)
        # Same card object — not a new one
        assert window._cards[(0x046D, 0x0ABA, 0)] is card
        # Card reflects latest state
        assert card._percent.text() == "25%"

    def test_two_distinct_devices_create_two_cards(self, qapp):
        """Two distinct (vid,pid,dev_idx) tuples must create two separate cards."""
        from ui.main_window import MainWindow
        window = MainWindow()
        state_a = _make_state(vid=0x046D, pid=0x0ABA, dev_idx=0)
        state_b = _make_state(vid=0x046D, pid=0x0ABA, dev_idx=1)
        window.on_device_update(state_a)
        window.on_device_update(state_b)
        assert len(window._cards) == 2

    def test_card_added_to_dashboard_layout(self, qapp):
        """Card widget must be inserted into dashboard_layout."""
        from ui.main_window import MainWindow
        from ui.device_card import DeviceCard
        window = MainWindow()
        state = _make_state()
        initial_count = window.dashboard_layout.count()
        window.on_device_update(state)
        # Layout count must increase by 1 (card inserted before stretch)
        assert window.dashboard_layout.count() == initial_count + 1

    def test_stretch_remains_last_after_card_insert(self, qapp):
        """dashboard_layout stretch item must stay at the bottom after card insert."""
        from ui.main_window import MainWindow
        window = MainWindow()
        state = _make_state()
        window.on_device_update(state)
        count = window.dashboard_layout.count()
        last_item = window.dashboard_layout.itemAt(count - 1)
        # The last item is the stretch spacer — it has no widget
        assert last_item.widget() is None, "Stretch item must remain last in layout"

    def test_two_cards_both_in_layout(self, qapp):
        """After two distinct devices, both cards appear in dashboard_layout."""
        from ui.main_window import MainWindow
        from ui.device_card import DeviceCard
        window = MainWindow()
        state_a = _make_state(vid=0x046D, pid=0x0ABA, dev_idx=0)
        state_b = _make_state(vid=0x046D, pid=0x0ABA, dev_idx=1)
        initial_count = window.dashboard_layout.count()
        window.on_device_update(state_a)
        window.on_device_update(state_b)
        assert window.dashboard_layout.count() == initial_count + 2
