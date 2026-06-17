"""Unit tests for UpdaterWorker and auto-updating functionality."""
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import QCoreApplication

from ui.updater import UpdaterWorker, _is_newer


def test_naive_version_comparison():
    """Verify standard semver naive comparison behavior."""
    assert _is_newer("0.5.1", "0.5.0") is True
    assert _is_newer("1.0.0", "0.5.1") is True
    assert _is_newer("0.5.0", "0.5.0") is False
    assert _is_newer("0.4.9", "0.5.0") is False
    assert _is_newer("invalid", "0.5.0") is False
    assert _is_newer("0.5.0", "invalid") is True


def test_updater_emits_no_update_on_404(qapp, mocker):
    """Verify that a 404 response code from GitHub API is mapped to no_update signal."""
    # Mock requests.get to return a 404 status code
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get = mocker.patch("ui.updater.requests.get", return_value=mock_response)

    worker = UpdaterWorker()
    
    # Connect signals to spies
    no_update_spy = MagicMock()
    error_spy = MagicMock()
    update_available_spy = MagicMock()

    worker.no_update.connect(no_update_spy)
    worker.error.connect(error_spy)
    worker.update_available.connect(update_available_spy)

    # We mock threading.Thread to run synchronously inside check_for_updates
    def mock_thread_start(thread_self):
        thread_self._target()
    
    mocker.patch("threading.Thread.start", mock_thread_start)

    worker.check_for_updates()

    # Process events to allow Qt slots/signals to execute
    QCoreApplication.processEvents()

    mock_get.assert_called_once()
    no_update_spy.assert_called_once()
    error_spy.assert_not_called()
    update_available_spy.assert_not_called()


def test_updater_emits_error_on_non_200(qapp, mocker):
    """Verify that non-200 and non-404 responses trigger error signal."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get = mocker.patch("ui.updater.requests.get", return_value=mock_response)

    worker = UpdaterWorker()
    no_update_spy = MagicMock()
    error_spy = MagicMock()

    worker.no_update.connect(no_update_spy)
    worker.error.connect(error_spy)

    # Synchronous thread execution mock
    mocker.patch("threading.Thread.start", lambda t_self: t_self._target())

    worker.check_for_updates()
    QCoreApplication.processEvents()

    mock_get.assert_called_once()
    no_update_spy.assert_not_called()
    error_spy.assert_called_once()
    assert "HTTP 500" in error_spy.call_args[0][0]


def test_mainwindow_update_check_available(qapp, mocker, tmp_path, monkeypatch):
    """Verify MainWindow handles available updates on startup check."""
    import ui.settings_manager as sm
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", tmp_path / "config.json")
    save_config = mocker.patch("ui.settings_manager.save_config")
    mocker.patch("ui.settings_manager.load_config", return_value={"monitored_devices": []})

    # Mock requests.get
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tag_name": "v0.5.2",
        "assets": [{"name": "Volt_Installer.exe", "browser_download_url": "http://example.com/download"}]
    }
    mocker.patch("ui.updater.requests.get", return_value=mock_response)
    mocker.patch("threading.Thread.start", lambda t_self: t_self._target())

    # Build MainWindow
    from ui.main_window import MainWindow
    window = MainWindow()
    
    assert window._update_state == "idle"
    
    # Trigger check_for_updates using the window's startup_updater
    window._startup_updater = UpdaterWorker()
    window._startup_updater.update_available.connect(window._on_startup_update_available)
    window._startup_updater.no_update.connect(window._on_startup_no_update)
    window._startup_updater.error.connect(window._on_startup_update_error)
    
    window._startup_updater.check_for_updates()
    QCoreApplication.processEvents()

    assert window._update_state == "update_available"
    assert window._latest_version == "0.5.2"
    assert window._latest_url == "http://example.com/download"
    assert "Update Available" in window._sidebar._version_btn.text()


def test_mainwindow_update_check_no_update(qapp, mocker, tmp_path, monkeypatch):
    """Verify MainWindow handles no updates (or 404) gracefully."""
    import ui.settings_manager as sm
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", tmp_path / "config.json")
    mocker.patch("ui.settings_manager.load_config", return_value={"monitored_devices": []})

    # Mock 404 response
    mock_response = MagicMock()
    mock_response.status_code = 404
    mocker.patch("ui.updater.requests.get", return_value=mock_response)
    mocker.patch("threading.Thread.start", lambda t_self: t_self._target())

    from ui.main_window import MainWindow
    window = MainWindow()
    window._startup_updater = UpdaterWorker()
    window._startup_updater.update_available.connect(window._on_startup_update_available)
    window._startup_updater.no_update.connect(window._on_startup_no_update)
    window._startup_updater.error.connect(window._on_startup_update_error)
    
    window._startup_updater.check_for_updates()
    QCoreApplication.processEvents()

    assert window._update_state == "no_update"
    assert "Update Available" not in window._sidebar._version_btn.text()


def test_mainwindow_sidebar_version_click_flows(qapp, mocker, tmp_path, monkeypatch):
    """Verify version clicking flow for different update states."""
    import ui.settings_manager as sm
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", tmp_path / "config.json")
    mocker.patch("ui.settings_manager.load_config", return_value={"monitored_devices": []})

    from ui.main_window import MainWindow
    window = MainWindow()
    
    # 1. State: no_update -> should show up-to-date QMessageBox
    window._update_state = "no_update"
    mock_info = mocker.patch("PySide6.QtWidgets.QMessageBox.information")
    window._on_sidebar_version_clicked()
    mock_info.assert_called_once()
    assert "latest version" in mock_info.call_args[0][2]

    # 2. State: update_available -> should show question QMessageBox and run install if accepted
    window._update_state = "update_available"
    window._latest_version = "0.5.2"
    window._latest_url = "http://example.com/download"
    
    from PySide6.QtWidgets import QMessageBox
    mock_question = mocker.patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes)
    mock_install = mocker.patch.object(UpdaterWorker, "download_and_install")
    
    window._on_sidebar_version_clicked()
    mock_question.assert_called_once()
    mock_install.assert_called_once_with("http://example.com/download")


def test_mainwindow_sidebar_version_click_manual_run(qapp, mocker, tmp_path, monkeypatch):
    """Verify manual run check when state is idle or error."""
    import ui.settings_manager as sm
    monkeypatch.setattr(sm, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(sm, "CONFIG_FILE", tmp_path / "config.json")
    mocker.patch("ui.settings_manager.load_config", return_value={"monitored_devices": []})

    # Mock progress dialog
    mock_progress_class = mocker.patch("PySide6.QtWidgets.QProgressDialog")
    mock_progress_inst = MagicMock()
    mock_progress_class.return_value = mock_progress_inst

    # Mock updater request to get "no update" (404)
    mock_response = MagicMock()
    mock_response.status_code = 404
    mocker.patch("ui.updater.requests.get", return_value=mock_response)
    mocker.patch("threading.Thread.start", lambda t_self: t_self._target())

    from ui.main_window import MainWindow
    window = MainWindow()
    window._update_state = "error"  # Triggers manual check

    mock_info = mocker.patch("PySide6.QtWidgets.QMessageBox.information")
    window._on_sidebar_version_clicked()
    
    # Verify progress dialog was created and accepted
    mock_progress_class.assert_called_once()
    mock_progress_inst.accept.assert_called_once()
    # Verify QMessageBox up-to-date was shown
    mock_info.assert_called_once()
