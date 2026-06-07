"""Unit tests for WidgetWindow and _DeviceRow layout rendering."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QProgressBar
from ui.widget_window import WidgetWindow, _DeviceRow
from ui.settings_manager import save_config


@pytest.fixture
def mock_config(tmp_path, monkeypatch):
    """Mock out the settings manager config file path."""
    import ui.settings_manager as sm
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", tmp_path / "config.json")
    
    # Save a clean initial config
    save_config({
        "launch_at_startup": False,
        "widget_always_on_top": True,
        "widget_opacity": 0.95,
        "widget_show_beside": False,
        "widget_vertical_layout": False,
    })


def test_widget_window_initial_state(qapp, mock_config):
    """Verify that WidgetWindow starts with no devices and shows empty label."""
    win = WidgetWindow(exit_callback=lambda: None)
    assert len(win._rows) == 0
    assert win._empty_lbl.isHidden() is False


def test_widget_window_adds_horizontal_row(qapp, mock_config):
    """Verify that adding a device with widget_vertical_layout=False creates a horizontal row."""
    # Ensure vertical layout is False
    save_config({"widget_vertical_layout": False})
    
    win = WidgetWindow(exit_callback=lambda: None)
    win.update_device((0x046D, 0x0ABA, 0), "G Pro X Wireless", 85, False, False)
    
    assert len(win._rows) == 1
    assert win._empty_lbl.isHidden() is True
    
    row = win._rows[(0x046D, 0x0ABA, 0)]
    assert isinstance(row, _DeviceRow)
    assert row._is_vertical is False
    assert row.height() == 36
    
    # Horizontal layout uses QHBoxLayout for the row itself
    assert isinstance(row.layout(), QHBoxLayout)


def test_widget_window_adds_vertical_row(qapp, mock_config):
    """Verify that adding a device with widget_vertical_layout=True creates a vertical row."""
    # Ensure vertical layout is True
    save_config({"widget_vertical_layout": True})
    
    win = WidgetWindow(exit_callback=lambda: None)
    win.update_device((0x046D, 0x0ABA, 0), "G Pro X Wireless", 85, False, False)
    
    assert len(win._rows) == 1
    
    row = win._rows[(0x046D, 0x0ABA, 0)]
    assert isinstance(row, _DeviceRow)
    assert row._is_vertical is True
    assert row.height() == 48
    
    # Vertical layout uses QVBoxLayout for the row itself
    assert isinstance(row.layout(), QVBoxLayout)


def test_widget_window_rebuild_layout(qapp, mock_config):
    """Verify that rebuild_layout removes all rows and allows clean reconstruction."""
    win = WidgetWindow(exit_callback=lambda: None)
    win.update_device((0x046D, 0x0ABA, 0), "G Pro X Wireless", 85, False, False)
    assert len(win._rows) == 1
    
    win.rebuild_layout()
    assert len(win._rows) == 0
    assert win._empty_lbl.isHidden() is False


def test_widget_window_remove_device(qapp, mock_config):
    """Verify removing a device removes its row widget."""
    win = WidgetWindow(exit_callback=lambda: None)
    key = (0x046D, 0x0ABA, 0)
    win.update_device(key, "G Pro X Wireless", 85, False, False)
    assert len(win._rows) == 1
    
    win.remove_device(key)
    assert len(win._rows) == 0
    assert win._empty_lbl.isHidden() is False

