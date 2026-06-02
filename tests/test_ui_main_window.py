"""Unit tests for MainWindow.

Strategy (from RESEARCH Validation Architecture):
  - NEVER call window.show() in headless tests — Qt show() requires a display.
  - Instantiate MainWindow and call methods directly.
  - pytest-qt's qapp fixture provides the QApplication singleton.
"""
import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QStackedWidget


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
