"""Settings page widget for PeriphWatcher.

Contains the "Launch at startup" toggle wired to SettingsManager.
Keeps registry (set_startup) and JSON config (save_config) in sync (SYS-01, SYS-02).
"""
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from ui.settings_manager import is_startup_enabled, load_config, save_config, set_startup


class SettingsPage(QWidget):
    """Settings tab content: heading + startup toggle.

    The checkbox initial state is derived from is_startup_enabled() (registry source
    of truth).  While loading the initial state, signals are blocked so the toggled
    handler does not fire spuriously on construction.

    toggled handler keeps both the registry (set_startup) and the JSON file
    (save_config) in sync so SYS-01 and SYS-02 stay consistent.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(heading)

        self._startup_cb = QCheckBox("Launch at startup")
        layout.addWidget(self._startup_cb)
        layout.addStretch()

        # ------------------------------------------------------------------
        # Set initial state from the registry without triggering the handler.
        # ------------------------------------------------------------------
        self._startup_cb.blockSignals(True)
        self._startup_cb.setChecked(is_startup_enabled())
        self._startup_cb.blockSignals(False)

        # Wire toggle -> registry + config in sync
        self._startup_cb.toggled.connect(self._on_startup_toggled)

    def _on_startup_toggled(self, checked: bool) -> None:
        """Keep HKCU Run key and JSON config in sync when the user flips the toggle."""
        set_startup(checked)
        cfg = load_config()
        cfg["launch_at_startup"] = checked
        save_config(cfg)

    # ------------------------------------------------------------------
    # paintEvent override — required for QSS background-color on QWidget
    # subclasses (Research Pattern 3 / Pitfall 1).
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
