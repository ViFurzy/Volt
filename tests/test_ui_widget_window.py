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


@pytest.mark.parametrize("style", ["inspector", "dotmatrix"])
@pytest.mark.parametrize("mode", ["stack", "horizontal", "iphone"])
def test_widget_renders_in_every_style_and_mode(qapp, mock_config, style, mode):
    """Each style x layout mode builds and paints without error."""
    from ui import theme
    prev = theme.current()
    theme.set_theme(style)
    try:
        save_config({"widget_layout_mode": mode})
        win = WidgetWindow(exit_callback=lambda: None)
        win.update_device((1,), "Aerox 5 Wireless", 75, False, False)
        win.update_device((2,), "Arctis Nova 7", 19, True, False)
        assert not win.grab().isNull()
    finally:
        theme.set_theme(prev)


def test_widget_window_adds_horizontal_row(qapp, mock_config):
    """Verify that adding a device in default stack mode creates a VerticalBlockRowUI."""
    win = WidgetWindow(exit_callback=lambda: None)
    win.update_device((0x046D, 0x0ABA, 0), "G Pro X Wireless", 85, False, False)

    assert len(win._rows) == 1
    assert win._empty_lbl.isHidden() is True

    row = win._rows[(0x046D, 0x0ABA, 0)]
    assert isinstance(row, _DeviceRow)
    assert row._layout_mode == "stack"
    from ui.widget_window import VerticalBlockRowUI
    assert isinstance(row._ui, VerticalBlockRowUI)


def test_widget_window_adds_vertical_row(qapp, mock_config):
    """Verify that adding a device in horizontal mode creates a MinimalListRowUI."""
    save_config({"widget_layout_mode": "horizontal"})

    win = WidgetWindow(exit_callback=lambda: None)
    win.update_device((0x046D, 0x0ABA, 0), "G Pro X Wireless", 85, False, False)

    assert len(win._rows) == 1

    row = win._rows[(0x046D, 0x0ABA, 0)]
    assert isinstance(row, _DeviceRow)
    assert row._layout_mode == "horizontal"
    from ui.widget_window import MinimalListRowUI
    assert isinstance(row._ui, MinimalListRowUI)


def test_widget_window_rebuild_layout(qapp, mock_config):
    """Verify that rebuild_layout preserves existing devices in the new layout."""
    win = WidgetWindow(exit_callback=lambda: None)
    win.update_device((0x046D, 0x0ABA, 0), "G Pro X Wireless", 85, False, False)
    assert len(win._rows) == 1

    win.rebuild_layout()
    # rebuild_layout re-creates rows from saved state — devices are preserved
    assert len(win._rows) == 1
    assert win._empty_lbl.isHidden() is True


def test_widget_window_remove_device(qapp, mock_config):
    """Verify removing a device removes its row widget."""
    win = WidgetWindow(exit_callback=lambda: None)
    key = (0x046D, 0x0ABA, 0)
    win.update_device(key, "G Pro X Wireless", 85, False, False)
    assert len(win._rows) == 1
    
    win.remove_device(key)
    assert len(win._rows) == 0
    assert win._empty_lbl.isHidden() is False


def test_widget_window_horizontal_mode(qapp, mock_config):
    """Verify horizontal layout mode creates a MinimalListRowUI with a progress bar."""
    save_config({"widget_layout_mode": "horizontal"})
    win = WidgetWindow(exit_callback=lambda: None)
    key = (0x046D, 0x0ABA, 0)
    win.update_device(key, "G Pro X Wireless", 85, False, False)

    row = win._rows[key]
    assert row._layout_mode == "horizontal"
    from ui.widget_window import MinimalListRowUI
    assert isinstance(row._ui, MinimalListRowUI)
    assert row._ui._bar is not None


def test_widget_window_iphone_mode(qapp, mock_config):
    """Verify iphone layout mode creates a HorizontalRingsRowUI with a MiniBatteryRing."""
    save_config({"widget_layout_mode": "iphone"})
    win = WidgetWindow(exit_callback=lambda: None)
    key = (0x046D, 0x0ABA, 0)
    win.update_device(key, "G Pro X Wireless", 85, False, False)

    row = win._rows[key]
    assert row._layout_mode == "iphone"
    from ui.widget_window import HorizontalRingsRowUI
    assert isinstance(row._ui, HorizontalRingsRowUI)
    assert row._ui._ring is not None
    assert row._ui._ring.size == 34  # apply_scale(1.0): max(24, int(34 * 1.0))


def test_widget_window_rescales_to_visible_devices(qapp, mock_config):
    """Verify that WidgetWindow rescales its width and height dynamically based on visible devices."""
    win = WidgetWindow(exit_callback=lambda: None)

    # 1. Iphone mode
    save_config({"widget_layout_mode": "iphone"})
    win.rebuild_layout()
    # 0 devices: w=int(161*1)=161, h=int(78*1)=78
    assert win.width() == 161
    assert win.height() == 78

    # 1 device: w=int((8+8+145)*1)=161, h=int(104*1)=104
    win.update_device((1, 2, 3), "Device 1", 50, False, False)
    assert win.width() == 161
    assert win.height() == 104

    # 2 devices: w=int((8+8+290)*1)=306, h=104
    win.update_device((4, 5, 6), "Device 2", 90, False, False)
    assert win.width() == 306
    assert win.height() == 104

    # 2. Horizontal mode — rebuild_layout carries over the 2 devices
    save_config({"widget_layout_mode": "horizontal"})
    win.rebuild_layout()
    # 2 devices: w=int(220*1)=220, h=int((38+4+8+2*28)*1)=int(106*1)=106
    assert win.width() == 220
    assert win.height() == 106



