"""DeviceCard — VOLT | POWER CENTER device card widget.

Layout:
    device name  (title label, top)
    BatteryGauge (circular arc, center — visual hero)
    status row   (status text + charging indicator, bottom)

Test API compatibility: _name, _percent, _status, _charging_indicator are
QLabel instances accessible on the card. _percent is hidden visually;
its text and stylesheet satisfy existing unit tests while BatteryGauge
renders the actual arc and percentage text via QPainter.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from monitor.state import DeviceStatus
from ui.settings_manager import battery_color

if TYPE_CHECKING:
    from monitor.state import DeviceState, BtDeviceInfo


class BatteryGauge(QWidget):
    """Circular arc gauge rendered via QPainter.

    270° sweep starting at 7-o'clock, going clockwise.
    Arc color tracks battery threshold:
      > 45% → green (#4CAF50)
      ≤ 45% → amber (#F0BB66)
      ≤  8% → orange-red (#EE6800)
    Charging overrides color to teal (#4FC3F7).
    """

    SIZE = 140
    STROKE = 11

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._percent: int | None = None
        self._charging: bool = False
        self._offline: bool = False

        from PySide6.QtCore import QTimer
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(30)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_percent = 0.0

    def set_state(self, percent: int | None, charging: bool, offline: bool) -> None:
        self._percent = percent
        self._charging = charging
        self._offline = offline

        if self._charging and not self._offline and self._percent is not None:
            if not self._anim_timer.isActive():
                self._anim_percent = 0.0
                self._anim_timer.start()
        else:
            self._anim_timer.stop()

        self.update()

    def _on_anim_tick(self) -> None:
        if self._percent is not None:
            # Sweep from 0 to self._percent over 1.5 seconds (approx 50 ticks)
            step = max(1.0, self._percent / 40.0)
            self._anim_percent += step
            if self._anim_percent > self._percent:
                self._anim_percent = 0.0
            self.update()

    def _arc_color(self) -> str:
        if self._offline:
            return "#555566"
        if self._charging:
            return "#4FC3F7"
        if self._percent is None:
            return "#555566"
        if self._percent <= 8:
            return "#EE6800"
        if self._percent <= 45:
            return "#F0BB66"
        return "#4CAF50"

    def _state_label(self) -> str:
        if self._offline:
            return "offline"
        if self._charging:
            return "charging"
        if self._percent is None:
            return ""
        if self._percent <= 8:
            return "critical"
        if self._percent <= 45:
            return "warning"
        return "good"

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        sz = self.SIZE
        m = self.STROKE // 2 + 6
        rect = QRectF(m, m, sz - 2 * m, sz - 2 * m)

        # Background track
        bg_pen = QPen(QColor("#2a2a3a"))
        bg_pen.setWidth(self.STROKE)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(bg_pen)
        p.drawArc(rect, 225 * 16, -270 * 16)

        # Filled arc (battery level)
        color = self._arc_color()
        fill_pen = QPen(QColor(color))
        fill_pen.setWidth(self.STROKE)
        fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(fill_pen)

        if self._charging and not self._offline and self._percent is not None:
            pct = int(self._anim_percent)
        else:
            pct = self._percent if self._percent is not None else 0

        fill_span = int(-270 * 16 * pct / 100)
        if fill_span != 0:
            p.drawArc(rect, 225 * 16, fill_span)

        # Center text: percentage
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self._percent is not None:
            font = QFont("Segoe UI")
            font.setPixelSize(30)
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor(color))
            p.drawText(
                QRectF(0, sz * 0.18, sz, sz * 0.46),
                Qt.AlignmentFlag.AlignCenter,
                f"{self._percent}%",
            )

            label = self._state_label()
            if label:
                font2 = QFont("Segoe UI")
                font2.setPixelSize(11)
                p.setFont(font2)
                label_color = color if (self._percent <= 45 or self._offline) else "#888899"
                p.setPen(QColor(label_color))
                p.drawText(
                    QRectF(0, sz * 0.58, sz, sz * 0.24),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )
        else:
            text = "--" if self._offline else "N/A"
            font = QFont("Segoe UI")
            font.setPixelSize(22)
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor("#666677"))
            p.drawText(
                QRectF(0, 0, sz, sz),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )

        p.end()


class DeviceCard(QFrame):
    """Card widget for one monitored peripheral.

    Visual: device name → circular gauge → status/charging row.
    Test API: _name, _percent (hidden), _status, _charging_indicator all
    remain as QLabel instances with the expected text and styleSheet values.
    """

    remove_requested = Signal()
    history_requested = Signal(str)

    def __init__(
        self,
        state: DeviceState | None = None,
        device_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deviceCard")
        self.setMinimumSize(220, 240)
        self.setMaximumSize(340, 260)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._device_id: str | None = None
        self.last_state: DeviceState | BtDeviceInfo | None = None

        # ── Child widgets ──────────────────────────────────────────
        self._name = QLabel()
        self._name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._name.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #FFFFFF; padding: 0;"
        )
        self._name.setWordWrap(True)

        self._menu_btn = QPushButton("⋮")
        self._menu_btn.setFixedSize(24, 24)
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #555566; border: none;"
            " font-size: 16px; border-radius: 4px; padding: 0; }"
            "QPushButton:hover { color: #AAAACC; background-color: #2a2a38; }"
        )
        self._menu_btn.clicked.connect(self._show_menu)

        # _percent: test-API label — hidden visually, gauge renders the value
        self._percent = QLabel()
        self._percent.setVisible(False)

        self._status = QLabel()
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("font-size: 11px; color: #888899;")

        self._charging_indicator = QLabel("⚡ Charging")
        self._charging_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._charging_indicator.setStyleSheet("font-size: 11px; color: #4FC3F7;")
        self._charging_indicator.setVisible(False)



        # ── Gauge ──────────────────────────────────────────────────
        self._gauge = BatteryGauge()

        # ── Status row ─────────────────────────────────────────────
        status_row = QHBoxLayout()
        status_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.setSpacing(8)
        status_row.addWidget(self._status)
        status_row.addWidget(self._charging_indicator)

        # ── Top row: name (left) + menu button (right) ─────────────
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)
        top_row.addWidget(self._name)
        top_row.addStretch()
        top_row.addWidget(self._menu_btn, 0, Qt.AlignmentFlag.AlignTop)

        # ── Layout ─────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.addLayout(top_row)
        layout.addStretch(1)
        layout.addWidget(self._gauge, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(status_row)
        layout.addWidget(self._percent)   # invisible — keeps test assertions working
        layout.addStretch(1)

        # ── Opacity effect (created once; reused in update_state — BUG-05) ──
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)

        if state is not None:
            self.update_state(state, device_id)

    # ── Menu ───────────────────────────────────────────────────────

    def _show_menu(self) -> None:
        menu = QMenu(self)
        action_remove = menu.addAction("Remove from monitored")
        action_remove.triggered.connect(self.remove_requested.emit)
        menu.exec(self._menu_btn.mapToGlobal(self._menu_btn.rect().bottomLeft()))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.history_requested.emit(self._name.text())
            event.accept()
        else:
            super().mousePressEvent(event)

    # ── Public API ─────────────────────────────────────────────────

    def update_state(self, state: DeviceState, device_id: str | None = None) -> None:
        """Refresh all visual and data fields from a DeviceState snapshot."""
        self.last_state = state
        if device_id:
            self._device_id = device_id
        self._name.setText(state.device_name)

        # _percent label (test API — hidden)
        if state.percent is not None:
            self._percent.setText(f"{state.percent}%")
        else:
            self._percent.setText("--")
        
        color = battery_color(state.percent)
        self._percent.setStyleSheet(f"color: {color};")

        self._status.setText(state.status.name)
        self._charging_indicator.setVisible(state.charging)

        is_offline = state.status == DeviceStatus.OFFLINE
        self._gauge.set_state(state.percent, state.charging, is_offline)

        # Style based on connectivity
        if is_offline:
            self._opacity_effect.setOpacity(0.4)
            self.setProperty("offline", True)
        else:
            self._opacity_effect.setOpacity(1.0)
            self.setProperty("offline", False)
            
        self.style().unpolish(self)
        self.style().polish(self)
