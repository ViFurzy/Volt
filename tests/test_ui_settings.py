"""Unit tests for SettingsManager: JSON config persistence and winreg startup helpers."""
import json
import winreg

import pytest

from ui.settings_manager import (
    load_config,
    save_config,
    battery_color,
    set_startup,
    is_startup_enabled,
)


# ---------------------------------------------------------------------------
# Task 2: JSON config persistence
# ---------------------------------------------------------------------------

def test_load_config_returns_defaults_when_file_absent(tmp_path, monkeypatch):
    """load_config returns defaults dict when config file does not exist."""
    import ui.settings_manager as sm
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", tmp_path / "config.json")

    result = load_config()
    assert result == {"launch_at_startup": False}


def test_load_config_returns_defaults_on_malformed_json(tmp_path, monkeypatch):
    """load_config returns defaults when the file contains malformed JSON."""
    import ui.settings_manager as sm
    config_file = tmp_path / "config.json"
    config_file.write_text("{ not valid json }", encoding="utf-8")
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", config_file)

    result = load_config()
    assert result == {"launch_at_startup": False}


def test_save_and_load_config_roundtrip(tmp_path, monkeypatch):
    """save_config then load_config recovers the written value unchanged."""
    import ui.settings_manager as sm
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", config_file)

    save_config({"launch_at_startup": True})
    result = load_config()
    assert result == {"launch_at_startup": True}


def test_save_config_creates_directory(tmp_path, monkeypatch):
    """save_config creates the config directory if it does not exist."""
    import ui.settings_manager as sm
    nested_dir = tmp_path / "PeriphWatcher"
    config_file = nested_dir / "config.json"
    monkeypatch.setattr(sm, "CONFIG_DIR", nested_dir)
    monkeypatch.setattr(sm, "CONFIG_FILE", config_file)

    assert not nested_dir.exists()
    save_config({"launch_at_startup": False})
    assert config_file.exists()


def test_load_config_merges_unknown_keys(tmp_path, monkeypatch):
    """load_config merges loaded JSON over defaults, preserving unknown future keys."""
    import ui.settings_manager as sm
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"launch_at_startup": True, "devices": {"custom": True}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", config_file)

    result = load_config()
    assert result["launch_at_startup"] is True
    assert result["devices"] == {"custom": True}


# ---------------------------------------------------------------------------
# Task 2: battery_color thresholds
# ---------------------------------------------------------------------------

def test_battery_color_none_is_grey():
    assert battery_color(None) == "#888888"


def test_battery_color_5_is_critical():
    assert battery_color(5) == "#E50000"


def test_battery_color_8_is_critical():
    assert battery_color(8) == "#E50000"


def test_battery_color_45_is_warning():
    assert battery_color(45) == "#E5A300"


def test_battery_color_46_is_normal():
    assert battery_color(46) == "#4FC3F7"


def test_battery_color_100_is_normal():
    assert battery_color(100) == "#4FC3F7"


# ---------------------------------------------------------------------------
# Task 3: winreg startup registration
# ---------------------------------------------------------------------------

def test_set_startup_enabled_calls_setvalueex(mocker):
    """set_startup(True) calls SetValueEx with quoted path and REG_SZ."""
    mock_key = mocker.MagicMock()
    mock_open = mocker.patch("ui.settings_manager.winreg.OpenKey")
    mock_open.return_value.__enter__ = mocker.MagicMock(return_value=mock_key)
    mock_open.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mock_set = mocker.patch("ui.settings_manager.winreg.SetValueEx")

    import sys
    import ui.settings_manager as sm

    set_startup(True)

    mock_open.assert_called_once_with(
        winreg.HKEY_CURRENT_USER,
        sm.RUN_KEY,
        access=winreg.KEY_WRITE,
    )
    mock_set.assert_called_once()
    args = mock_set.call_args[0]
    assert args[1] == "PeriphWatcher"
    assert args[3] == winreg.REG_SZ
    # Value must start with a double-quoted exe path
    # Dev mode: '"python.exe" -m src'; packaged: '"app.exe"'
    exe_value = args[4]
    assert exe_value.startswith('"')


def test_set_startup_disabled_calls_deletevalue(mocker):
    """set_startup(False) calls DeleteValue with the app name."""
    mock_key = mocker.MagicMock()
    mock_open = mocker.patch("ui.settings_manager.winreg.OpenKey")
    mock_open.return_value.__enter__ = mocker.MagicMock(return_value=mock_key)
    mock_open.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mock_del = mocker.patch("ui.settings_manager.winreg.DeleteValue")

    import ui.settings_manager as sm

    set_startup(False)

    mock_del.assert_called_once_with(mock_key, sm.APP_NAME)


def test_set_startup_disabled_swallows_filenotfounderror(mocker):
    """set_startup(False) does not raise when the value does not exist."""
    mock_key = mocker.MagicMock()
    mock_open = mocker.patch("ui.settings_manager.winreg.OpenKey")
    mock_open.return_value.__enter__ = mocker.MagicMock(return_value=mock_key)
    mock_open.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("ui.settings_manager.winreg.DeleteValue", side_effect=FileNotFoundError)

    # Must not raise
    set_startup(False)


def test_is_startup_enabled_returns_true_when_key_exists(mocker):
    """is_startup_enabled returns True when QueryValueEx finds the value."""
    mock_key = mocker.MagicMock()
    mock_open = mocker.patch("ui.settings_manager.winreg.OpenKey")
    mock_open.return_value.__enter__ = mocker.MagicMock(return_value=mock_key)
    mock_open.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch(
        "ui.settings_manager.winreg.QueryValueEx",
        return_value=('"C:\\path\\app.exe"', winreg.REG_SZ),
    )

    assert is_startup_enabled() is True


def test_is_startup_enabled_returns_false_when_key_missing(mocker):
    """is_startup_enabled returns False on FileNotFoundError."""
    mock_key = mocker.MagicMock()
    mock_open = mocker.patch("ui.settings_manager.winreg.OpenKey")
    mock_open.return_value.__enter__ = mocker.MagicMock(return_value=mock_key)
    mock_open.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch(
        "ui.settings_manager.winreg.QueryValueEx",
        side_effect=FileNotFoundError,
    )

    assert is_startup_enabled() is False
