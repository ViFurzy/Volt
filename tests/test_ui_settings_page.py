"""Unit tests for SettingsPage.

Verifies that the SettingsPage toggles:
- Properly initialize from config.
- Update the config.json dictionary on toggling.
- Invoke the window callbacks (rebuilding and syncing layouts).
"""
import pytest
from PySide6.QtCore import Qt
from ui.settings_page import SettingsPage
from ui.settings_manager import load_config, save_config


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


def test_settings_page_initializes_from_config(qapp, mock_config):
    """Verify that checkboxes/toggles read correct defaults from mock config."""
    page = SettingsPage()
    assert page._widget_show_beside_cb.isChecked() is False
    assert page._widget_vertical_cb.isChecked() is False


def test_widget_show_beside_toggled(qapp, mock_config):
    """Verify that toggling the show beside switch updates the config value."""
    page = SettingsPage()
    assert page._widget_show_beside_cb.isChecked() is False
    
    # Simulate user click by setting value and emitting toggled signal
    page._widget_show_beside_cb.setChecked(True)
    page._widget_show_beside_cb.toggled.emit(True)
    cfg = load_config()
    assert cfg.get("widget_show_beside") is True

    page._widget_show_beside_cb.setChecked(False)
    page._widget_show_beside_cb.toggled.emit(False)
    cfg = load_config()
    assert cfg.get("widget_show_beside") is False


def test_widget_vertical_layout_toggled_no_window(qapp, mock_config):
    """Verify that toggling the vertical layout switch updates the config value (with no window)."""
    page = SettingsPage()
    assert page._widget_vertical_cb.isChecked() is False
    
    page._widget_vertical_cb.setChecked(True)
    page._widget_vertical_cb.toggled.emit(True)
    cfg = load_config()
    assert cfg.get("widget_vertical_layout") is True


def test_widget_vertical_layout_toggled_with_window(qapp, mock_config, mocker):
    """Verify that toggling vertical layout triggers rebuild_layout and sync on the window widget."""
    mock_window = mocker.MagicMock()
    mock_widget = mocker.MagicMock()
    # Mock self._window._widget
    mock_window._widget = mock_widget
    
    page = SettingsPage(window=mock_window)
    page._widget_vertical_cb.setChecked(True)
    page._widget_vertical_cb.toggled.emit(True)
    
    cfg = load_config()
    assert cfg.get("widget_vertical_layout") is True
    mock_widget.rebuild_layout.assert_called_once()
    mock_window.sync_widget.assert_called_once()

