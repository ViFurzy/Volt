"""Unit tests for the battery history recording and UI."""
import datetime
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from monitor.state import DeviceState, DeviceStatus, BtDeviceInfo
from ui.settings_manager import load_config, save_config
from ui.main_window import MainWindow
from ui.history_page import HistoryPage, HistoryGraph


@pytest.fixture
def clean_config(tmp_path, monkeypatch):
    """Fixture to reset settings_manager directories and clean config files."""
    import ui.settings_manager as sm
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", tmp_path / "config.json")
    save_config({
        "launch_at_startup": False,
        "thresholds": {},
        "close_behavior": None,
        "cooldown_hours": 4,
        "monitored_devices": [],
        "custom_hid_devices": [],
        "ignored_devices": [],
        "history": {}
    })
    return tmp_path


def test_record_history_basic(clean_config, qtbot):
    """Verify that _record_history appends entries to the configuration."""
    window = MainWindow()
    qtbot.addWidget(window)

    window._record_history("hid:1234:5678", "Test Device", 85)
    
    cfg = load_config()
    assert "history" in cfg
    assert "hid:1234:5678" in cfg["history"]
    assert len(cfg["history"]["hid:1234:5678"]) == 1
    assert cfg["history"]["hid:1234:5678"][0]["percent"] == 85


def test_record_history_debounce(clean_config, qtbot, mocker):
    """Verify that identical readings within 10 minutes are debounced."""
    window = MainWindow()
    qtbot.addWidget(window)

    # First entry
    window._record_history("hid:1234:5678", "Test Device", 85)

    # Fast follow entry with identical percentage (should be debounced/ignored)
    window._record_history("hid:1234:5678", "Test Device", 85)

    cfg = load_config()
    assert len(cfg["history"]["hid:1234:5678"]) == 1

    # Fake the clock to be 11 minutes in the future
    now = datetime.datetime.now()
    future_time = (now + datetime.timedelta(minutes=11)).isoformat()
    
    # Modify the timestamp of the first entry in config so that it appears old
    cfg["history"]["hid:1234:5678"][0]["timestamp"] = (now - datetime.timedelta(minutes=11)).isoformat()
    save_config(cfg)

    # Now write another identical value — it should be recorded since > 10m elapsed
    window._record_history("hid:1234:5678", "Test Device", 85)
    
    cfg = load_config()
    assert len(cfg["history"]["hid:1234:5678"]) == 2


def test_record_history_limit(clean_config, qtbot):
    """Verify that history list is capped at the last 200 items."""
    window = MainWindow()
    qtbot.addWidget(window)

    # Pre-populate history with 210 items
    cfg = load_config()
    cfg["history"] = {
        "hid:1234:5678": [{"timestamp": datetime.datetime.now().isoformat(), "percent": 50} for _ in range(210)]
    }
    save_config(cfg)

    # Record a new item
    window._record_history("hid:1234:5678", "Test Device", 55)

    cfg = load_config()
    assert len(cfg["history"]["hid:1234:5678"]) == 200
    assert cfg["history"]["hid:1234:5678"][-1]["percent"] == 55


def test_history_cleanup_on_device_removal(clean_config, qtbot):
    """Verify that history is cleaned up when a monitored device is removed."""
    window = MainWindow()
    qtbot.addWidget(window)

    # Add a device to monitored and record history
    cfg = load_config()
    cfg["monitored_devices"] = [{"id": "hid:1234:5678", "name": "Test Device", "type": "hid"}]
    cfg["history"] = {"hid:1234:5678": [{"timestamp": datetime.datetime.now().isoformat(), "percent": 80}]}
    save_config(cfg)

    # Remove the monitored device
    window._remove_monitored_device("hid:1234:5678")

    cfg = load_config()
    assert "hid:1234:5678" not in cfg.get("history", {})


def test_history_page_device_selection(clean_config, qtbot):
    """Verify that HistoryPage correctly updates its active device and header."""
    # Add monitored devices
    cfg = load_config()
    cfg["monitored_devices"] = [
        {"id": "hid:1111:2222", "name": "Device A", "type": "hid"},
        {"id": "hid:3333:4444", "name": "Device B", "type": "hid"}
    ]
    save_config(cfg)

    page = HistoryPage()
    qtbot.addWidget(page)
    page.refresh()

    # Default selection: should be first device
    assert page._device_id == "hid:1111:2222"
    assert page._device_name == "Device A"
    assert page._heading.text() == "Device A"

    # Set device programmatically
    page.set_device("hid:3333:4444", "Device B")
    assert page._device_id == "hid:3333:4444"
    assert page._device_name == "Device B"
    assert page._heading.text() == "Device B"


def test_history_graph_paint(qtbot):
    """Verify that HistoryGraph paintEvent runs without error."""
    graph = HistoryGraph()
    qtbot.addWidget(graph)

    # Empty graph
    graph.set_history([])
    graph.repaint()

    # 1 point graph
    graph.set_history([
        {"timestamp": datetime.datetime.now().isoformat(), "percent": 80}
    ])
    graph.repaint()

    # 2 points graph
    graph.set_history([
        {"timestamp": (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat(), "percent": 85},
        {"timestamp": datetime.datetime.now().isoformat(), "percent": 80}
    ])
    graph.repaint()

    # 3 points graph
    history = [
        {"timestamp": (datetime.datetime.now() - datetime.timedelta(hours=2)).isoformat(), "percent": 90},
        {"timestamp": (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat(), "percent": 85},
        {"timestamp": datetime.datetime.now().isoformat(), "percent": 80}
    ]
    graph.set_history(history)
    graph.repaint()


def test_record_history_stabilization(clean_config, qtbot):
    """Verify that _record_history ignores updates within 180 seconds of device going online."""
    import time
    window = MainWindow()
    qtbot.addWidget(window)

    did = "hid:1234:5678"
    
    # 1. Device online time is very recent (stabilizing)
    window._device_online_time[did] = time.time() - 30  # 30 seconds ago
    window._record_history(did, "Test Device", 85)
    
    cfg = load_config()
    assert did not in cfg.get("history", {})

    # 2. Device online time is in the past (stabilized)
    window._device_online_time[did] = time.time() - 190  # 190 seconds ago
    window._record_history(did, "Test Device", 85)

    cfg = load_config()
    assert did in cfg.get("history", {})
    assert len(cfg["history"][did]) == 1
    assert cfg["history"][did][0]["percent"] == 85


def test_history_page_filtering(clean_config, qtbot):
    """Verify that HistoryPage correctly filters entries according to selected time range."""
    # Pre-populate monitored devices
    cfg = load_config()
    cfg["monitored_devices"] = [
        {"id": "hid:1111:2222", "name": "Device A", "type": "hid"}
    ]
    
    now = datetime.datetime.now()
    
    # Create history points:
    # 1. 30 mins ago (should show in 1h, 4h, 24h, 7d, All)
    # 2. 3 hours ago (should show in 4h, 24h, 7d, All)
    # 3. 12 hours ago (should show in 24h, 7d, All)
    # 4. 2 days ago (should show in 7d, All)
    # 5. 10 days ago (should show in All only)
    h_data = [
        {"timestamp": (now - datetime.timedelta(minutes=30)).isoformat(), "percent": 95},
        {"timestamp": (now - datetime.timedelta(hours=3)).isoformat(), "percent": 85},
        {"timestamp": (now - datetime.timedelta(hours=12)).isoformat(), "percent": 75},
        {"timestamp": (now - datetime.timedelta(days=2)).isoformat(), "percent": 65},
        {"timestamp": (now - datetime.timedelta(days=10)).isoformat(), "percent": 55},
    ]
    cfg["history"] = {"hid:1111:2222": h_data}
    save_config(cfg)

    page = HistoryPage()
    qtbot.addWidget(page)
    page.refresh()

    # Default filter is 'all'
    assert len(page._graph._history) == 5
    assert page._graph._time_range == "all"

    # Switch to '7d' (btn_id 3)
    page._filter_group.button(3).setChecked(True)
    page._on_filter_clicked(3)
    assert len(page._graph._history) == 4
    assert page._graph._history[-1]["percent"] == 65  # 10 days ago is filtered out
    assert page._graph._time_range == "7d"

    # Switch to '24h' (btn_id 2)
    page._filter_group.button(2).setChecked(True)
    page._on_filter_clicked(2)
    assert len(page._graph._history) == 3
    assert page._graph._time_range == "24h"

    # Switch to '4h' (btn_id 1)
    page._filter_group.button(1).setChecked(True)
    page._on_filter_clicked(1)
    assert len(page._graph._history) == 2
    assert page._graph._time_range == "4h"

    # Switch to '1h' (btn_id 0)
    page._filter_group.button(0).setChecked(True)
    page._on_filter_clicked(0)
    assert len(page._graph._history) == 1
    assert page._graph._history[0]["percent"] == 95
    assert page._graph._time_range == "1h"

