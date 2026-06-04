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
    """Settings tab content: heading + toggles.

    Checkboxes:
      - Launch at startup  (registry + config)
      - Minimize to tray on close  (config close_behavior)

    Signals are blocked during construction so handlers don't fire spuriously.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(heading)

        # ── Launch at startup ──────────────────────────────────────
        self._startup_cb = QCheckBox("Launch at startup")
        layout.addWidget(self._startup_cb)

        self._startup_cb.blockSignals(True)
        self._startup_cb.setChecked(is_startup_enabled())
        self._startup_cb.blockSignals(False)
        self._startup_cb.toggled.connect(self._on_startup_toggled)

        # ── Close behaviour ────────────────────────────────────────
        self._tray_close_cb = QCheckBox("Minimize to tray on close (don't ask)")
        layout.addWidget(self._tray_close_cb)

        cfg = load_config()
        self._tray_close_cb.blockSignals(True)
        self._tray_close_cb.setChecked(cfg.get("close_behavior") == "tray")
        self._tray_close_cb.blockSignals(False)
        self._tray_close_cb.toggled.connect(self._on_tray_close_toggled)

        layout.addStretch()

    def _on_startup_toggled(self, checked: bool) -> None:
        set_startup(checked)
        cfg = load_config()
        cfg["launch_at_startup"] = checked
        save_config(cfg)

    def _on_tray_close_toggled(self, checked: bool) -> None:
        """Save close_behavior: 'tray' when checked, None (ask) when unchecked."""
        cfg = load_config()
        cfg["close_behavior"] = "tray" if checked else None
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
