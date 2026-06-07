"""Settings page widget for Volt."""
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStyle, QStyleOption, QVBoxLayout, QWidget, QPushButton, QMessageBox, QSlider

from ui.settings_manager import is_startup_enabled, load_config, save_config, set_startup
from ui.updater import UpdaterWorker
from __version__ import __version__

# Track color endpoints for interpolation
_OFF_RGB = (37, 37, 58)    # #25253a
_ON_RGB  = (232, 144, 0)   # #E89000


class _TogglePill(QWidget):
    """Painted pill-shaped on/off toggle with animated thumb."""
    toggled = Signal(bool)
    _W, _H, _MARGIN = 44, 24, 3

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        r = self._H // 2 - self._MARGIN
        self._off_cx = float(self._MARGIN + r)
        self._on_cx  = float(self._W - self._MARGIN - r)
        self._cx = self._on_cx if checked else self._off_cx

        self._anim = QPropertyAnimation(self, b"thumb_x", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # Qt property so QPropertyAnimation can drive it
    @Property(float)
    def thumb_x(self) -> float:
        return self._cx

    @thumb_x.setter  # type: ignore[no-redef]
    def thumb_x(self, val: float) -> None:
        self._cx = val
        self.update()

    def setChecked(self, v: bool) -> None:
        self._checked = v
        self._cx = self._on_cx if v else self._off_cx
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._checked = not self._checked
        self._anim.stop()
        self._anim.setStartValue(self._cx)
        self._anim.setEndValue(self._on_cx if self._checked else self._off_cx)
        self._anim.start()
        self.toggled.emit(self._checked)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Interpolate track color based on thumb position (0.0 → off, 1.0 → on)
        t = max(0.0, min(1.0, (self._cx - self._off_cx) / (self._on_cx - self._off_cx)))
        ro, go, bo = _OFF_RGB
        rn, gn, bn = _ON_RGB
        track = QColor(int(ro + t * (rn - ro)), int(go + t * (gn - go)), int(bo + t * (bn - bo)))

        p.setBrush(QBrush(track))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, self._W, self._H, self._H // 2, self._H // 2)

        r = self._H // 2 - self._MARGIN
        cy = self._H // 2
        cx = int(self._cx)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)


class ToggleSwitch(QWidget):
    """Label + pill toggle row. API mirrors QCheckBox (toggled signal, setChecked, isChecked)."""
    toggled = Signal(bool)

    def __init__(self, label: str = "", checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 13px; color: #AAAACC; background: transparent;")
        row.addWidget(lbl)
        row.addStretch()

        self._pill = _TogglePill(checked)
        self._pill.toggled.connect(self.toggled)
        row.addWidget(self._pill)

    def setChecked(self, v: bool) -> None:
        self._pill.setChecked(v)

    def isChecked(self) -> bool:
        return self._pill.isChecked()

    def blockSignals(self, block: bool) -> bool:
        ret = super().blockSignals(block)
        self._pill.blockSignals(block)
        return ret


class SliderRow(QWidget):
    """Label + slider row for percentage settings."""
    valueChanged = Signal(int)

    def __init__(self, label: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 13px; color: #AAAACC; background: transparent;")
        row.addWidget(lbl)
        
        row.addStretch()

        self._val_lbl = QLabel()
        self._val_lbl.setFixedWidth(40)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._val_lbl.setStyleSheet("font-size: 13px; color: #FFFFFF;")
        
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setFixedWidth(120)
        self._slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border-radius: 2px;
                height: 4px;
                background: #2a2a38;
            }
            QSlider::handle:horizontal {
                background: #7B9FFF;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #92AEFF;
            }
            QSlider::sub-page:horizontal {
                background: #7B9FFF;
                border-radius: 2px;
            }
        """)
        self._slider.valueChanged.connect(self._on_value_changed)
        
        row.addWidget(self._slider)
        row.addWidget(self._val_lbl)

    def _on_value_changed(self, v: int) -> None:
        self._val_lbl.setText(f"{v}%")
        self.valueChanged.emit(v)

    def setValue(self, v: int) -> None:
        self._slider.setValue(v)
        self._val_lbl.setText(f"{v}%")

    def value(self) -> int:
        return self._slider.value()

    def blockSignals(self, block: bool) -> bool:
        ret = super().blockSignals(block)
        self._slider.blockSignals(block)
        return ret


class SettingsPage(QWidget):
    """Settings tab content: heading + toggle rows."""

    def __init__(self, service=None, window=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._window = window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(heading)

        # ── Launch at startup ──────────────────────────────────────
        self._startup_cb = ToggleSwitch("Launch at startup")
        layout.addWidget(self._startup_cb)

        self._startup_cb.blockSignals(True)
        self._startup_cb.setChecked(is_startup_enabled())
        self._startup_cb.blockSignals(False)
        self._startup_cb.toggled.connect(self._on_startup_toggled)

        # ── Close behaviour ────────────────────────────────────────
        self._tray_close_cb = ToggleSwitch("Minimize to tray on close (don't ask)")
        layout.addWidget(self._tray_close_cb)

        # ── Widget (compact mode) ──────────────────────────────────
        self._widget_top_cb = ToggleSwitch("Compact mode widget always on top")
        cfg2 = load_config()
        self._widget_top_cb.blockSignals(True)
        self._widget_top_cb.setChecked(cfg2.get("widget_always_on_top", True))
        self._widget_top_cb.blockSignals(False)
        self._widget_top_cb.toggled.connect(self._on_widget_top_toggled)
        layout.addWidget(self._widget_top_cb)
        
        self._widget_opacity_slider = SliderRow("Compact widget background opacity")
        self._widget_opacity_slider.blockSignals(True)
        opacity_pct = int(cfg2.get("widget_opacity", 0.95) * 100)
        self._widget_opacity_slider.setValue(opacity_pct)
        self._widget_opacity_slider.blockSignals(False)
        self._widget_opacity_slider.valueChanged.connect(self._on_widget_opacity_changed)
        layout.addWidget(self._widget_opacity_slider)

        self._widget_show_beside_cb = ToggleSwitch("Show compact widget beside main window")
        self._widget_show_beside_cb.blockSignals(True)
        self._widget_show_beside_cb.setChecked(cfg2.get("widget_show_beside", False))
        self._widget_show_beside_cb.blockSignals(False)
        self._widget_show_beside_cb.toggled.connect(self._on_widget_show_beside_toggled)
        layout.addWidget(self._widget_show_beside_cb)

        self._widget_vertical_cb = ToggleSwitch("Compact widget vertical layout")
        self._widget_vertical_cb.blockSignals(True)
        self._widget_vertical_cb.setChecked(cfg2.get("widget_vertical_layout", False))
        self._widget_vertical_cb.blockSignals(False)
        self._widget_vertical_cb.toggled.connect(self._on_widget_vertical_toggled)
        layout.addWidget(self._widget_vertical_cb)

        cfg = load_config()
        self._tray_close_cb.blockSignals(True)
        self._tray_close_cb.setChecked(cfg.get("close_behavior") == "tray")
        self._tray_close_cb.blockSignals(False)
        self._tray_close_cb.toggled.connect(self._on_tray_close_toggled)

        # ── Updates ────────────────────────────────────────────────
        self._updater = UpdaterWorker()
        self._updater.update_available.connect(self._on_update_available)
        self._updater.no_update.connect(self._on_no_update)
        self._updater.error.connect(self._on_update_error)
        
        upd_row = QHBoxLayout()
        upd_lbl = QLabel(f"Version {__version__}")
        upd_lbl.setStyleSheet("font-size: 13px; color: #AAAACC;")
        self._upd_btn = QPushButton("Check for Updates")
        self._upd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upd_btn.clicked.connect(self._check_for_updates)
        upd_row.addWidget(upd_lbl)
        upd_row.addStretch()
        upd_row.addWidget(self._upd_btn)
        layout.addLayout(upd_row)

        layout.addStretch()

    # ── Qt event overrides ────────────────────────────────────────

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Re-sync toggles from config each time this page is displayed."""
        super().showEvent(event)
        cfg = load_config()
        self._tray_close_cb.blockSignals(True)
        self._tray_close_cb.setChecked(cfg.get("close_behavior") == "tray")
        self._tray_close_cb.blockSignals(False)
        self._widget_top_cb.blockSignals(True)
        self._widget_top_cb.setChecked(cfg.get("widget_always_on_top", True))
        self._widget_top_cb.blockSignals(False)
        
        self._widget_opacity_slider.blockSignals(True)
        self._widget_opacity_slider.setValue(int(cfg.get("widget_opacity", 0.95) * 100))
        self._widget_opacity_slider.blockSignals(False)

        self._widget_show_beside_cb.blockSignals(True)
        self._widget_show_beside_cb.setChecked(cfg.get("widget_show_beside", False))
        self._widget_show_beside_cb.blockSignals(False)

        self._widget_vertical_cb.blockSignals(True)
        self._widget_vertical_cb.setChecked(cfg.get("widget_vertical_layout", False))
        self._widget_vertical_cb.blockSignals(False)

    def _on_startup_toggled(self, checked: bool) -> None:
        set_startup(checked)
        cfg = load_config()
        cfg["launch_at_startup"] = checked
        save_config(cfg)

    def _on_tray_close_toggled(self, checked: bool) -> None:
        cfg = load_config()
        cfg["close_behavior"] = "tray" if checked else None
        save_config(cfg)

    def _on_widget_top_toggled(self, checked: bool) -> None:
        cfg = load_config()
        cfg["widget_always_on_top"] = checked
        save_config(cfg)
        if self._window and getattr(self._window, "_widget", None):
            self._window._widget.set_always_on_top(checked)
            
    def _on_widget_opacity_changed(self, pct: int) -> None:
        cfg = load_config()
        cfg["widget_opacity"] = pct / 100.0
        save_config(cfg)
        if self._window and getattr(self._window, "_widget", None):
            self._window._widget.set_opacity()

    def _on_widget_show_beside_toggled(self, checked: bool) -> None:
        cfg = load_config()
        cfg["widget_show_beside"] = checked
        save_config(cfg)

    def _on_widget_vertical_toggled(self, checked: bool) -> None:
        cfg = load_config()
        cfg["widget_vertical_layout"] = checked
        save_config(cfg)
        if self._window and getattr(self._window, "_widget", None):
            self._window._widget.rebuild_layout()
            self._window.sync_widget()

    def _check_for_updates(self):
        self._upd_btn.setEnabled(False)
        self._upd_btn.setText("Checking...")
        self._updater.check_for_updates()

    def _on_update_available(self, version: str, url: str):
        reply = QMessageBox.question(
            self, "Update Available",
            f"Version {version} is available.\nDo you want to download and install it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._upd_btn.setText("Downloading...")
            self._updater.download_and_install(url)
        else:
            self._upd_btn.setEnabled(True)
            self._upd_btn.setText("Check for Updates")

    def _on_no_update(self):
        self._upd_btn.setEnabled(True)
        self._upd_btn.setText("Check for Updates")
        QMessageBox.information(self, "Up to Date", f"You are running the latest version ({__version__}).")

    def _on_update_error(self, err: str):
        self._upd_btn.setEnabled(True)
        self._upd_btn.setText("Check for Updates")
        QMessageBox.warning(self, "Update Error", f"Failed to check for updates:\n{err}")

    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
