"""Unit tests for TrayManager.

Strategy (from RESEARCH Validation Architecture):
  - NEVER call tray.show() in headless tests — system tray requires a display session.
  - Test construction, signal wiring, and DoubleClick logic using mock windows.
  - pytest-qt's qapp fixture provides the QApplication singleton.
"""
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QSystemTrayIcon


def test_traymanager_constructs(qapp):
    """TrayManager constructs with a mock window and real qapp without raising."""
    from ui.tray import TrayManager
    window = MagicMock()
    tray = TrayManager(window, qapp)
    assert tray is not None


def test_double_click_calls_show_restore(qapp):
    """DoubleClick activation must call window.show_restore() exactly once (UI-03)."""
    from ui.tray import TrayManager
    window = MagicMock()
    tray = TrayManager(window, qapp)

    tray._on_activated(QSystemTrayIcon.ActivationReason.DoubleClick)

    window.show_restore.assert_called_once()


def test_trigger_does_not_call_show_restore(qapp):
    """Single-click (Trigger) must NOT call show_restore (only DoubleClick restores)."""
    from ui.tray import TrayManager
    window = MagicMock()
    tray = TrayManager(window, qapp)

    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)

    window.show_restore.assert_not_called()


def test_context_activation_does_not_call_show_restore(qapp):
    """Right-click (Context) must NOT call show_restore."""
    from ui.tray import TrayManager
    window = MagicMock()
    tray = TrayManager(window, qapp)

    tray._on_activated(QSystemTrayIcon.ActivationReason.Context)

    window.show_restore.assert_not_called()


def test_volt_icon_is_valid(qapp):
    """make_volt_icon() must return a non-null QIcon with at least one size."""
    from ui.icon import make_volt_icon
    icon = make_volt_icon()
    assert not icon.isNull(), "make_volt_icon() returned a null QIcon"
    assert icon.availableSizes(), "QIcon has no available sizes"
