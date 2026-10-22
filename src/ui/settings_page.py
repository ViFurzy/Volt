"""Settings page widget for Volt."""
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QMessageBox,
    QSlider,
    QTabWidget,
    QComboBox,
)

from ui import theme
from ui.settings_manager import is_startup_enabled, load_config, save_config, set_startup
from ui.styles import apply_style
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
        p.setBrush(QBrush(QColor(theme.c("#FFFFFF"))))
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
    """Label + slider row for settings."""
    valueChanged = Signal(int)

    def __init__(self, label: str = "", min_val: int = 0, max_val: int = 100, suffix: str = "%", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suffix = suffix
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
        self._slider.setRange(min_val, max_val)
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
        self._val_lbl.setText(f"{v}{self._suffix}")
        self.valueChanged.emit(v)

    def setValue(self, v: int) -> None:
        self._slider.setValue(v)
        self._val_lbl.setText(f"{v}{self._suffix}")

    def value(self) -> int:
        return self._slider.value()

    def blockSignals(self, block: bool) -> bool:
        ret = super().blockSignals(block)
        self._slider.blockSignals(block)
        return ret


class ComboRow(QWidget):
    """Label + dropdown row for selection settings."""
    currentIndexChanged = Signal(int)

    def __init__(self, label: str = "", items: list[str] = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 13px; color: #AAAACC; background: transparent;")
        row.addWidget(lbl)
        row.addStretch()

        self._combo = QComboBox()
        if items:
            self._combo.addItems(items)
        self._combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._combo.currentIndexChanged.connect(self.currentIndexChanged)
        row.addWidget(self._combo)

    def setCurrentIndex(self, index: int) -> None:
        self._combo.setCurrentIndex(index)

    def currentIndex(self) -> int:
        return self._combo.currentIndex()

    def blockSignals(self, block: bool) -> bool:
        ret = super().blockSignals(block)
        self._combo.blockSignals(block)
        return ret


class SettingsPage(QWidget):
    """Settings tab content: heading + QTabWidget with sub-tabs."""

    def __init__(self, service=None, window=None, devices_page=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._window = window
        self._devices_page = devices_page

        if self._devices_page is None:
            from ui.devices_page import DevicesPage
            self._devices_page = DevicesPage(service=service, loop=None)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel("Settings")
        heading.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(heading)

        # ── Tab Widget ───────────────────────────────────────────
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # ── 1. Global Tab ────────────────────────────────────────
        global_tab = QWidget()
        global_layout = QVBoxLayout(global_tab)
        global_layout.setContentsMargins(16, 16, 16, 16)
        global_layout.setSpacing(16)

        self._style_combo = ComboRow("Style", [t["name"] for t in theme.THEMES.values()])
        self._style_combo.setCurrentIndex(list(theme.THEMES).index(theme.current()))
        self._style_combo.currentIndexChanged.connect(self._on_style_changed)
        global_layout.addWidget(self._style_combo)

        self._startup_cb = ToggleSwitch("Launch at startup")
        global_layout.addWidget(self._startup_cb)

        self._startup_cb.blockSignals(True)
        self._startup_cb.setChecked(is_startup_enabled())
        self._startup_cb.blockSignals(False)
        self._startup_cb.toggled.connect(self._on_startup_toggled)

        self._tray_close_cb = ToggleSwitch("Minimize to tray on close (don't ask)")
        global_layout.addWidget(self._tray_close_cb)

        cfg = load_config()
        self._tray_close_cb.blockSignals(True)
        self._tray_close_cb.setChecked(cfg.get("close_behavior") == "tray")
        self._tray_close_cb.blockSignals(False)
        self._tray_close_cb.toggled.connect(self._on_tray_close_toggled)

        self._updater = UpdaterWorker()
        self._updater.update_available.connect(self._on_update_available)
        self._updater.no_update.connect(self._on_no_update)
        self._updater.error.connect(self._on_update_error)
        
        upd_row = QHBoxLayout()
        upd_lbl = QLabel(f"Version {__version__}")
        upd_lbl.setStyleSheet("font-size: 13px; color: #AAAACC;")
        self._upd_btn = QPushButton("Check for Updates")
        self._upd_btn.setObjectName("updBtn")
        self._upd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._upd_btn.clicked.connect(self._check_for_updates)
        upd_row.addWidget(upd_lbl)
        upd_row.addStretch()
        upd_row.addWidget(self._upd_btn)
        global_layout.addSpacing(10)
        global_layout.addLayout(upd_row)
        global_layout.addStretch()

        self._tabs.addTab(global_tab, "Global")

        # ── 2. Monitor Tab ───────────────────────────────────────
        monitor_tab = QWidget()
        monitor_layout = QVBoxLayout(monitor_tab)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        monitor_layout.addWidget(self._devices_page)

        self._tabs.addTab(monitor_tab, "Monitor")

        # ── 3. Compact Mode Tab ──────────────────────────────────
        compact_tab = QWidget()
        compact_layout = QVBoxLayout(compact_tab)
        compact_layout.setContentsMargins(16, 16, 16, 16)
        compact_layout.setSpacing(14)

        self._widget_top_cb = ToggleSwitch("Compact mode widget always on top")
        compact_layout.addWidget(self._widget_top_cb)

        self._widget_top_cb.blockSignals(True)
        self._widget_top_cb.setChecked(cfg.get("widget_always_on_top", True))
        self._widget_top_cb.blockSignals(False)
        self._widget_top_cb.toggled.connect(self._on_widget_top_toggled)
        
        self._widget_opacity_slider = SliderRow("Compact widget background opacity")
        compact_layout.addWidget(self._widget_opacity_slider)

        self._widget_opacity_slider.blockSignals(True)
        saved_opacity = cfg.get("widget_opacity", 0.95)
        opacity_pct = 0 if saved_opacity <= 0.01 else int(saved_opacity * 100)
        self._widget_opacity_slider.setValue(opacity_pct)
        self._widget_opacity_slider.blockSignals(False)
        self._widget_opacity_slider.valueChanged.connect(self._on_widget_opacity_changed)

        self._widget_scale_slider = SliderRow("Compact widget scale", 50, 150, "%")
        compact_layout.addWidget(self._widget_scale_slider)

        self._widget_scale_slider.blockSignals(True)
        saved_scale = cfg.get("widget_scale", 1.0)
        scale_pct = int(saved_scale * 100)
        self._widget_scale_slider.setValue(scale_pct)
        self._widget_scale_slider.blockSignals(False)
        self._widget_scale_slider.valueChanged.connect(self._on_widget_scale_changed)

        self._widget_show_beside_cb = ToggleSwitch("Show compact widget beside main window")
        compact_layout.addWidget(self._widget_show_beside_cb)

        self._widget_show_beside_cb.blockSignals(True)
        self._widget_show_beside_cb.setChecked(cfg.get("widget_show_beside", False))
        self._widget_show_beside_cb.blockSignals(False)
        self._widget_show_beside_cb.toggled.connect(self._on_widget_show_beside_toggled)

        # Layout Mode dropdown
        self._widget_layout_mode_combo = ComboRow("Compact widget layout mode", ["Vertical blocks", "Minimal list", "Rings"])
        compact_layout.addWidget(self._widget_layout_mode_combo)

        mode_str = cfg.get("widget_layout_mode", "stack")
        mode_idx = 0
        if mode_str == "horizontal": mode_idx = 1
        elif mode_str == "iphone": mode_idx = 2

        self._widget_layout_mode_combo.blockSignals(True)
        self._widget_layout_mode_combo.setCurrentIndex(mode_idx)
        self._widget_layout_mode_combo.blockSignals(False)
        self._widget_layout_mode_combo.currentIndexChanged.connect(self._on_widget_layout_mode_changed)

        compact_layout.addStretch()

        self._tabs.addTab(compact_tab, "Compact mode")

    # ── Qt event overrides ────────────────────────────────────────

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Re-sync toggles from config each time this page is displayed."""
        super().showEvent(event)
        
        # Sync update button with window state
        if self._window:
            state = getattr(self._window, "_update_state", "idle")
            if state == "update_available":
                self._upd_btn.setText("Update Available")
                self._upd_btn.setProperty("update_available", True)
                self._upd_btn.style().unpolish(self._upd_btn)
                self._upd_btn.style().polish(self._upd_btn)
            else:
                self._upd_btn.setText("Check for Updates")
                self._upd_btn.setProperty("update_available", False)
                self._upd_btn.style().unpolish(self._upd_btn)
                self._upd_btn.style().polish(self._upd_btn)

        cfg = load_config()
        self._tray_close_cb.blockSignals(True)
        self._tray_close_cb.setChecked(cfg.get("close_behavior") == "tray")
        self._tray_close_cb.blockSignals(False)
        self._widget_top_cb.blockSignals(True)
        self._widget_top_cb.setChecked(cfg.get("widget_always_on_top", True))
        self._widget_top_cb.blockSignals(False)
        
        self._widget_opacity_slider.blockSignals(True)
        saved_opacity = cfg.get("widget_opacity", 0.95)
        opacity_pct = 0 if saved_opacity <= 0.01 else int(saved_opacity * 100)
        self._widget_opacity_slider.setValue(opacity_pct)
        self._widget_opacity_slider.blockSignals(False)

        self._widget_scale_slider.blockSignals(True)
        saved_scale = cfg.get("widget_scale", 1.0)
        scale_pct = int(saved_scale * 100)
        self._widget_scale_slider.setValue(scale_pct)
        self._widget_scale_slider.blockSignals(False)

        self._widget_show_beside_cb.blockSignals(True)
        self._widget_show_beside_cb.setChecked(cfg.get("widget_show_beside", False))
        self._widget_show_beside_cb.blockSignals(False)

        mode_str = cfg.get("widget_layout_mode", "stack")
        mode_idx = 0
        if mode_str == "horizontal": mode_idx = 1
        elif mode_str == "iphone": mode_idx = 2

        self._widget_layout_mode_combo.blockSignals(True)
        self._widget_layout_mode_combo.setCurrentIndex(mode_idx)
        self._widget_layout_mode_combo.blockSignals(False)

    def _on_style_changed(self, index: int) -> None:
        name = theme.set_theme(list(theme.THEMES)[index])
        cfg = load_config()
        cfg["ui_style"] = name
        save_config(cfg)
        apply_style(QApplication.instance())
        if self._window and getattr(self._window, "_widget", None):
            self._window._widget.rebuild_layout()
            self._window._widget.set_opacity()
            self._window.sync_widget()
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
        cfg["widget_opacity"] = max(0.01, pct / 100.0)
        save_config(cfg)
        if self._window and getattr(self._window, "_widget", None):
            self._window._widget.set_opacity()

    def _on_widget_scale_changed(self, pct: int) -> None:
        cfg = load_config()
        scale_val = pct / 100.0
        cfg["widget_scale"] = scale_val
        save_config(cfg)
        if self._window and getattr(self._window, "_widget", None):
            self._window._widget.apply_scale(scale_val)

    def _on_widget_show_beside_toggled(self, checked: bool) -> None:
        cfg = load_config()
        cfg["widget_show_beside"] = checked
        save_config(cfg)

    def _on_widget_layout_mode_changed(self, index: int) -> None:
        cfg = load_config()
        modes = ["stack", "horizontal", "iphone"]
        mode = modes[index]
        cfg["widget_layout_mode"] = mode
        save_config(cfg)

        if self._window and getattr(self._window, "_widget", None):
            self._window._widget.rebuild_layout()
            self._window.sync_widget()

    def set_update_available(self, version: str, url: str) -> None:
        """Update the settings update button to show update available state."""
        self._upd_btn.setText("Update Available")
        self._upd_btn.setProperty("update_available", True)
        self._upd_btn.style().unpolish(self._upd_btn)
        self._upd_btn.style().polish(self._upd_btn)

    def _check_for_updates(self):
        # If the window already found an update, prompt directly!
        if self._window and getattr(self._window, "_update_state", "idle") == "update_available":
            self._on_update_available(self._window._latest_version, self._window._latest_url)
            return

        self._upd_btn.setEnabled(False)
        self._upd_btn.setText("Checking...")
        self._updater.check_for_updates()

    def _on_update_available(self, version: str, url: str):
        if self._window:
            self._window._update_state = "update_available"
            self._window._latest_version = version
            self._window._latest_url = url
            if hasattr(self._window, "_sidebar") and self._window._sidebar:
                self._window._sidebar.set_update_available(version)
        
        self.set_update_available(version, url)
        
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
        if self._window:
            self._window._update_state = "no_update"
        self._upd_btn.setEnabled(True)
        self._upd_btn.setText("Check for Updates")
        self._upd_btn.setProperty("update_available", False)
        self._upd_btn.style().unpolish(self._upd_btn)
        self._upd_btn.style().polish(self._upd_btn)
        QMessageBox.information(self, "Up to Date", f"You are running the latest version ({__version__}).")

    def _on_update_error(self, err: str):
        if self._window:
            self._window._update_state = "error"
        self._upd_btn.setEnabled(True)
        self._upd_btn.setText("Check for Updates")
        self._upd_btn.setProperty("update_available", False)
        self._upd_btn.style().unpolish(self._upd_btn)
        self._upd_btn.style().polish(self._upd_btn)
        QMessageBox.warning(self, "Update Error", f"Failed to check for updates:\n{err}")

    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)

