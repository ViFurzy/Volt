"""WidgetWindow — compact always-on-top widget showing device name + battery level.

Layout:
    QFrame#widgetContainer
        header row: "VOLT" label | [⊡ expand] [✕ hide]
        divider
        per-device _DeviceRow: [● dot] [name] [⚡] [percent]

Toggled from MainWindow.enter_widget_mode() / exit_widget_mode().
Position is saved to config on drag-release and window hide.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

from ui.settings_manager import get_device_battery_color, load_config, save_config


class _DeviceRow(QFrame):
    """Sleek device row with custom layout configuration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("deviceRow")

        cfg = load_config()
        self._is_vertical = cfg.get("widget_vertical_layout", False)

        self._name = QLabel()
        self._name.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")

        self._charging = QLabel("⚡")
        self._charging.setStyleSheet("font-size: 11px; color: #4FC3F7;")
        self._charging.setVisible(False)

        self._percent = QLabel()
        self._percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._percent.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")

        self._bar = QProgressBar()
        self._bar.setTextVisible(False)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)

        if self._is_vertical:
            self.setFixedHeight(48)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(16, 8, 16, 8)
            layout.setSpacing(4)

            top_layout = QHBoxLayout()
            top_layout.setContentsMargins(0, 0, 0, 0)
            top_layout.setSpacing(8)

            top_layout.addWidget(self._name, 1)
            top_layout.addWidget(self._charging)
            top_layout.addWidget(self._percent)

            self._bar.setFixedHeight(4)

            layout.addLayout(top_layout)
            layout.addWidget(self._bar)
        else:
            self.setFixedHeight(36)
            layout = QHBoxLayout(self)
            layout.setContentsMargins(16, 0, 16, 0)
            layout.setSpacing(10)

            self._bar.setFixedSize(36, 12)

            layout.addWidget(self._name, 1)
            layout.addWidget(self._charging)
            layout.addWidget(self._percent)
            layout.addWidget(self._bar)

        from PySide6.QtCore import QTimer
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(30)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_val = 0.0
        self._percent_val = 0

    def _on_anim_tick(self) -> None:
        if self._percent_val > 0:
            step = max(1.0, self._percent_val / 40.0)
            self._anim_val += step
            if self._anim_val > self._percent_val:
                self._anim_val = 0.0
            self._bar.setValue(int(self._anim_val))

    def refresh(self, name: str, percent: int | None, charging: bool, offline: bool, threshold: int = 15) -> None:
        color = get_device_battery_color(percent, threshold, charging, offline)

        self._name.setText(name)
        self._name.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {'#555566' if offline else '#FFFFFF'};"
        )
        self._charging.setVisible(bool(charging and not offline))

        self._percent_val = percent if percent is not None else 0

        if percent is not None and not offline:
            self._percent.setText(f"{percent}%")
            self._percent.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {color};")
            
            if charging:
                if not self._anim_timer.isActive():
                    self._anim_val = 0.0
                    self._anim_timer.start()
            else:
                self._anim_timer.stop()
                self._bar.setValue(percent)
        else:
            self._percent.setText("--")
            self._percent.setStyleSheet("font-size: 12px; font-weight: bold; color: #555566;")
            self._anim_timer.stop()
            self._bar.setValue(0)

        if self._is_vertical:
            self._bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #2a2a38;
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 2px;
                }}
            """)
        else:
            self._bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #1a1a24;
                    border: 1px solid #3a3a4a;
                    border-radius: 4px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 3px;
                }}
            """)


class WidgetWindow(QWidget):
    """Compact floating widget. Call show() / hide() to toggle visibility.

    Args:
        exit_callback: called when the user clicks ⊡ to restore the full window.
    """

    def __init__(self, exit_callback, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._exit_callback = exit_callback
        self._drag_pos = None
        self._rows: dict = {}  # device key → _DeviceRow

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("widgetWindow")
        
        # Override the global dark theme's QWidget { background: #1a1a1f } 
        # so our layout containers don't draw opaque black rectangles.
        self.setStyleSheet("""
            WidgetWindow, QWidget#widgetHeader, QWidget#widgetRows, _DeviceRow {
                background: transparent;
            }
        """)

        self._apply_flags()
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Outer container (border + rounded corners) ────────────────
        self._container = QFrame()
        self._container.setObjectName("widgetContainer")
        self._apply_opacity()

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 8)
        container_layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("widgetHeader")
        header.setFixedHeight(38)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 8, 0)
        header_layout.setSpacing(4)

        title = QLabel("VOLT")
        title.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #444455; letter-spacing: 2px;"
        )

        expand_btn = QPushButton("⊡")
        expand_btn.setFixedSize(22, 22)
        expand_btn.setToolTip("Expand to full window")
        expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        expand_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #555566; border: none;"
            " font-size: 14px; border-radius: 3px; }"
            "QPushButton:hover { color: #7B9FFF; background: #2a2a38; }"
        )
        expand_btn.clicked.connect(self._exit_callback)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setToolTip("Hide to tray")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #555566; border: none;"
            " font-size: 11px; border-radius: 3px; }"
            "QPushButton:hover { color: #FFFFFF; background: #C0392B; }"
        )
        close_btn.clicked.connect(self.hide)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(expand_btn)
        header_layout.addWidget(close_btn)

        # ── Device rows ───────────────────────────────────────────────
        self._rows_widget = QWidget()
        self._rows_widget.setObjectName("widgetRows")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 4, 0, 0)
        self._rows_layout.setSpacing(2)

        self._empty_lbl = QLabel("No devices monitored")
        self._empty_lbl.setStyleSheet(
            "font-size: 12px; color: #444455; padding: 6px 12px;"
        )
        self._rows_layout.addWidget(self._empty_lbl)

        container_layout.addWidget(header)
        container_layout.addWidget(self._rows_widget)

        outer.addWidget(self._container)

        self._restore_position()

    # ── Always-on-top ─────────────────────────────────────────────────

    def _apply_flags(self) -> None:
        cfg = load_config()
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if cfg.get("widget_always_on_top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    def set_always_on_top(self, enabled: bool) -> None:
        """Re-apply window flags when the setting changes."""
        self._apply_flags()

    def _apply_opacity(self) -> None:
        cfg = load_config()
        opacity = cfg.get("widget_opacity", 0.95)
        self._container.setStyleSheet(f"""
            QFrame#widgetContainer {{
                background-color: rgba(20, 20, 28, {opacity});
                border: 1px solid rgba(123, 159, 255, 0.2);
                border-radius: 12px;
            }}
        """)

    def set_opacity(self) -> None:
        """Re-apply opacity from config."""
        self._apply_opacity()

    # ── Position persistence ──────────────────────────────────────────

    def _restore_position(self) -> None:
        cfg = load_config()
        pos = cfg.get("widget_position")
        if isinstance(pos, dict):
            self.move(pos.get("x", 100), pos.get("y", 100))

    def _save_position(self) -> None:
        cfg = load_config()
        cfg["widget_position"] = {"x": self.x(), "y": self.y()}
        save_config(cfg)

    # ── Device update API ─────────────────────────────────────────────

    def update_device(
        self,
        key,
        name: str,
        percent: int | None,
        charging: bool,
        offline: bool,
    ) -> None:
        """Create or update the row for this device key. Offline devices are hidden."""
        if offline:
            # Hide existing row; don't create one for an offline device
            if key in self._rows:
                self._rows[key].setVisible(False)
                self._update_empty_label()
                self.adjustSize()
            return

        if isinstance(key, tuple) and len(key) == 3:
            device_id = f"hid:{key[0]:04X}:{key[1]:04X}"
        else:
            device_id = str(key)

        cfg = load_config()
        thresholds = cfg.get("thresholds", {})
        device_cfg = thresholds.get(device_id, {})
        threshold = device_cfg.get("threshold_pct", 15)
        if threshold is None:
            threshold = 15

        if key not in self._rows:
            row = _DeviceRow()
            self._rows[key] = row
            self._rows_layout.addWidget(row)
        self._rows[key].refresh(name, percent, charging, offline, threshold=threshold)
        self._rows[key].setVisible(True)
        self._update_empty_label()
        self.adjustSize()

    def remove_device(self, key) -> None:
        """Remove the row for this device key."""
        row = self._rows.pop(key, None)
        if row:
            self._rows_layout.removeWidget(row)
            row.setParent(None)
        self._update_empty_label()
        self.adjustSize()

    def rebuild_layout(self) -> None:
        """Clear all rows so they are fully reconstructed with the new orientation."""
        for key in list(self._rows.keys()):
            row = self._rows.pop(key)
            self._rows_layout.removeWidget(row)
            row.setParent(None)
        self._update_empty_label()
        self.adjustSize()

    def _update_empty_label(self) -> None:
        any_visible = any(not r.isHidden() for r in self._rows.values())
        self._empty_lbl.setVisible(not any_visible)

    # ── Qt event overrides ────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_pos is not None:
            self._save_position()
        self._drag_pos = None
        event.accept()

    def hideEvent(self, event) -> None:
        self._save_position()
        super().hideEvent(event)
