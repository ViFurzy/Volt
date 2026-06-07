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

    def test_all_items_are_cards_after_insert(self, qapp):
        """FlowLayout has no trailing stretch — items are card widgets (DeviceCard or AddPlaceholder)."""
        from ui.main_window import MainWindow, _AddPlaceholder
        from ui.device_card import DeviceCard
        window = MainWindow()
        state = _make_state()
        window.on_device_update(state)
        count = window.dashboard_layout.count()
        assert count >= 2  # 1 device card + 1 placeholder card
        last_item = window.dashboard_layout.itemAt(count - 1)
        assert last_item.widget() is not None, "FlowLayout items must all be card widgets"
        assert isinstance(last_item.widget(), _AddPlaceholder)
        for idx in range(count - 1):
            item = window.dashboard_layout.itemAt(idx)
            assert isinstance(item.widget(), DeviceCard)

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


# ---------------------------------------------------------------------------
# Compact Mode and Beside Mode Visibility Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_window_config(tmp_path, monkeypatch):
    """Mock settings path and save config."""
    import ui.settings_manager as sm
    from ui.settings_manager import save_config
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", tmp_path / "config.json")
    save_config({
        "widget_show_beside": False,
        "widget_vertical_layout": False,
    })



def test_enter_widget_mode_hides_main_when_show_beside_false(qapp, mock_window_config, mocker):
    """If widget_show_beside is False, enter_widget_mode hides MainWindow and shows widget."""
    from ui.main_window import MainWindow
    from ui.settings_manager import save_config
    
    save_config({"widget_show_beside": False})
    window = MainWindow()
    
    # Mock window's explicit visibility state
    mocker.patch.object(window, "hide")
    mocker.patch.object(window._widget, "show")
    
    window.enter_widget_mode()
    
    window.hide.assert_called_once()
    window._widget.show.assert_called_once()


def test_enter_widget_mode_keeps_main_when_show_beside_true(qapp, mock_window_config, mocker):
    """If widget_show_beside is True, enter_widget_mode does not hide MainWindow and shows widget."""
    from ui.main_window import MainWindow
    from ui.settings_manager import save_config
    
    save_config({"widget_show_beside": True})
    window = MainWindow()
    
    mocker.patch.object(window, "hide")
    mocker.patch.object(window._widget, "show")
    
    window.enter_widget_mode()
    
    window.hide.assert_not_called()
    window._widget.show.assert_called_once()


def test_exit_widget_mode_restores_main_if_hidden(qapp, mock_window_config, mocker):
    """exit_widget_mode hides widget, and restores MainWindow if it was hidden."""
    from ui.main_window import MainWindow
    window = MainWindow()
    
    mocker.patch.object(window._widget, "hide")
    mocker.patch.object(window, "isVisible", return_value=False)
    mocker.patch.object(window, "show")
    mocker.patch.object(window, "raise_")
    mocker.patch.object(window, "activateWindow")
    
    window.exit_widget_mode()
    
    window._widget.hide.assert_called_once()
    window.show.assert_called_once()
    window.raise_.assert_called_once()
    window.activateWindow.assert_called_once()


def test_exit_widget_mode_does_not_call_show_if_already_visible(qapp, mock_window_config, mocker):
    """exit_widget_mode hides widget, and does not call show on MainWindow if it was already visible."""
    from ui.main_window import MainWindow
    window = MainWindow()
    
    mocker.patch.object(window._widget, "hide")
    mocker.patch.object(window, "isVisible", return_value=True)
    mocker.patch.object(window, "show")
    
    window.exit_widget_mode()
    
    window._widget.hide.assert_called_once()
    window.show.assert_not_called()


def test_show_restore_exits_widget_mode_when_show_beside_false(qapp, mock_window_config, mocker):
    """show_restore exits widget mode (restoring main, hiding widget) if widget is visible and show_beside is False."""
    from ui.main_window import MainWindow
    from ui.settings_manager import save_config
    
    save_config({"widget_show_beside": False})
    window = MainWindow()
    
    mocker.patch.object(window._widget, "isVisible", return_value=True)
    mocker.patch.object(window, "exit_widget_mode")
    mocker.patch.object(window, "show")
    
    window.show_restore()
    
    window.exit_widget_mode.assert_called_once()
    window.show.assert_not_called()


def test_show_restore_shows_main_when_show_beside_true(qapp, mock_window_config, mocker):
    """show_restore shows main window (leaving widget visible) if widget is visible and show_beside is True."""
    from ui.main_window import MainWindow
    from ui.settings_manager import save_config
    
    save_config({"widget_show_beside": True})
    window = MainWindow()
    
    mocker.patch.object(window._widget, "isVisible", return_value=True)
    mocker.patch.object(window, "exit_widget_mode")
    mocker.patch.object(window, "show")
    mocker.patch.object(window, "raise_")
    mocker.patch.object(window, "activateWindow")
    
    window.show_restore()
    
    window.exit_widget_mode.assert_not_called()
    window.show.assert_called_once()
    window.raise_.assert_called_once()
    window.activateWindow.assert_called_once()

