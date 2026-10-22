"""WidgetWindow — compact always-on-top widget showing device name + battery level.

Layout modes:
  - Stack (vertical stack of rows, identical to v0.5.0 layout)
  - Horizontal (device items displayed from left to right side-by-side)
  - iPhone-like (circular rings with vector icons inside, displayed side-by-side)
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

from ui import theme
from ui.settings_manager import get_device_battery_color, load_config, save_config


def get_device_category(name: str) -> str:
    """Classify the device type from its name to determine which icon to draw."""
    name_lower = name.lower()
    
    # Specific overrides
    if "pro x wireless" in name_lower and "superlight" not in name_lower:
        return "headset"
        
    if "keyboard" in name_lower or "key" in name_lower or "pro x tkl" in name_lower:
        return "keyboard"
    if "head" in name_lower or "sound" in name_lower or "ear" in name_lower or "phone" in name_lower:
        return "headset"
    if "mouse" in name_lower or "g502" in name_lower or "g pro" in name_lower or "aerox" in name_lower or "pop" in name_lower:
        return "mouse"
    if "controller" in name_lower or "game" in name_lower or "pad" in name_lower or "stadia" in name_lower:
        return "gamepad"
    return "generic"


def get_ring_color(percent: int | None, charging: bool, offline: bool) -> str:
    """Return the color used in the circular rings for consistency across layouts."""
    if offline: return theme.c("#555566")
    if charging: return theme.c("#4FC3F7")
    if percent is None: return theme.c("#555566")
    if percent <= 8: return theme.c("#EE6800")
    if percent <= 45: return theme.c("#F0BB66")
    return theme.c("#4CAF50")


def draw_device_icon(p: QPainter, category: str, cx: float, cy: float, sz: float, color: str) -> None:
    """Draw a vector icon for the given device category."""
    p.setBrush(Qt.BrushStyle.NoBrush)
    icon_pen = QPen(QColor(color))
    icon_pen.setWidthF(max(1.0, 1.5 * (sz / 48.0)))
    icon_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    icon_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(icon_pen)

    icon_scale = sz / 48.0
    def sc(val: float) -> float:
        return val * icon_scale

    if category == "mouse":
        p.drawRoundedRect(QRectF(cx - sc(5), cy - sc(8), sc(10), sc(16)), sc(4), sc(4))
        p.drawLine(cx, cy - int(sc(8)), cx, cy - int(sc(2)))
        p.drawEllipse(QRectF(cx - sc(1), cy - sc(6), sc(2), sc(3)))
    elif category == "keyboard":
        p.drawRoundedRect(QRectF(cx - sc(9), cy - sc(5), sc(18), sc(10)), sc(1.5), sc(1.5))
        p.drawPoint(cx - int(sc(5)), cy - int(sc(2)))
        p.drawPoint(cx - int(sc(2)), cy - int(sc(2)))
        p.drawPoint(cx + int(sc(2)), cy - int(sc(2)))
        p.drawPoint(cx + int(sc(5)), cy - int(sc(2)))
        p.drawPoint(cx - int(sc(5)), cy + int(sc(1)))
        p.drawLine(cx - int(sc(2)), cy + int(sc(1)), cx + int(sc(2)), cy + int(sc(1)))
        p.drawPoint(cx + int(sc(5)), cy + int(sc(1)))
    elif category == "headset":
        p.drawArc(QRectF(cx - sc(8), cy - sc(7), sc(16), sc(16)), 0, 180 * 16)
        p.drawRoundedRect(QRectF(cx - sc(9), cy - sc(1), sc(3), sc(5)), sc(1), sc(1))
        p.drawRoundedRect(QRectF(cx + sc(6), cy - sc(1), sc(3), sc(5)), sc(1), sc(1))
    elif category == "gamepad":
        p.drawRoundedRect(QRectF(cx - sc(9), cy - sc(5), sc(18), sc(10)), sc(3), sc(3))
        p.drawEllipse(QRectF(cx - sc(5), cy - sc(2), sc(3), sc(3)))
        p.drawPoint(cx + int(sc(4)), cy - int(sc(2)))
        p.drawPoint(cx + int(sc(2)), cy + int(sc(1)))
    else:
        p.drawLine(cx, cy - int(sc(7)), cx, cy + int(sc(7)))
        p.drawLine(cx, cy - int(sc(7)), cx + int(sc(4)), cy - int(sc(3)))
        p.drawLine(cx + int(sc(4)), cy - int(sc(3)), cx - int(sc(3)), cy + int(sc(3)))
        p.drawLine(cx - int(sc(3)), cy + int(sc(3)), cx + int(sc(4)), cy + int(sc(6)))
        p.drawLine(cx + int(sc(4)), cy + int(sc(6)), cx, cy + int(sc(2)))


def _num_font() -> str:
    """QSS snippet putting numerals in the Doto display face (dot-matrix style only)."""
    return f'font-family: "{theme.display_font()}"; ' if theme.is_dots() else ""


class DotBar(QWidget):
    """Row of dots standing in for QProgressBar in the dot-matrix style."""
    N = 10

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0
        self._color = "#FFFFFF"

    def setValue(self, v: int) -> None:
        self._value = v
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        step = self.width() / self.N
        r = min(step, self.height()) * 0.35
        on = round(self._value * self.N / 100)
        for i in range(self.N):
            if i < on:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(self._color))
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(theme.c("#2A2A3A")), 1))
            p.drawEllipse(QPointF(step * (i + 0.5), self.height() / 2.0), r, r)
        p.end()


class MiniBatteryRing(QWidget):
    """Mini circular battery ring gauge for iPhone-like widget mode.

    Draws a circular arc representing battery level, with a custom vector icon
    drawn in the center depending on the device category.
    """
    def __init__(self, size: int = 48, stroke: int = 4, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.size = size
        self.stroke = stroke
        self.setFixedSize(size, size)
        self._percent: int | None = None
        self._charging: bool = False
        self._offline: bool = False
        self._category: str = "generic"

    def apply_scale(self, size: int, stroke: int) -> None:
        self.size = size
        self.stroke = stroke
        self.setFixedSize(size, size)
        self.update()

    def set_state(self, percent: int | None, charging: bool, offline: bool, category: str) -> None:
        self._percent = percent
        self._charging = charging
        self._offline = offline
        self._category = category
        self.update()

    def _arc_color(self) -> str:
        return get_ring_color(self._percent, self._charging, self._offline)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        sz = self.size
        m = self.stroke // 2 + 2
        rect = QRectF(m, m, sz - 2 * m, sz - 2 * m)

        color = self._arc_color()
        pct = self._percent if self._percent is not None else 0

        if theme.is_dots():
            # Ring of 20 dots, filled clockwise from 12 o'clock
            n = 20
            on = 0 if self._offline else round(pct * n / 100)
            r = rect.width() / 2.0
            dot_r = max(1.0, self.stroke * 0.45)
            for i in range(n):
                a = 2 * math.pi * i / n - math.pi / 2
                pt = QPointF(rect.center().x() + r * math.cos(a), rect.center().y() + r * math.sin(a))
                if i < on:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(color))
                else:
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(theme.c("#2a2a3a")), 1))
                p.drawEllipse(pt, dot_r, dot_r)
        else:
            # Background track
            bg_pen = QPen(QColor(theme.c("#2a2a3a")))
            bg_pen.setWidth(self.stroke)
            bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(bg_pen)
            p.drawArc(rect, 0, 360 * 16)

            # Filled arc (battery level)
            fill_pen = QPen(QColor(color))
            fill_pen.setWidth(self.stroke)
            fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(fill_pen)

            fill_span = int(-360 * 16 * pct / 100)
            if fill_span != 0:
                p.drawArc(rect, 90 * 16, fill_span)

        # Center vector icon
        cx, cy = sz / 2.0, sz / 2.0
        draw_device_icon(p, self._category, cx, cy, sz, color)

        p.end()


class VerticalBlockRowUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale = 1.0
        self._name = ""
        self._percent = None
        self._charging = False
        self._offline = False
        self._category = "generic"
        self._color = "#555566"
        self._anim_val = 0.0

    def set_anim_val(self, val: float):
        self._anim_val = val
        self.update()

    def set_state(self, name, percent, charging, offline, category, color):
        self._name = name
        self._percent = percent
        self._charging = charging
        self._offline = offline
        self._category = category
        self._color = color
        self.update()

    def apply_scale(self, scale):
        self._scale = scale
        self.setFixedSize(int(84 * scale), int(88 * scale))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = self._scale
        color = self._color
        rect = self.rect()

        p.setPen(Qt.PenStyle.NoPen)
        dots = theme.is_dots()
        p.setBrush(QColor(theme.c("#1e1e28")))
        p.drawRoundedRect(rect, 0 if dots else 6 * scale, 0 if dots else 6 * scale)

        bar_w = 6 * scale
        bar_margin = 4 * scale
        bar_x = bar_margin
        bar_y = bar_margin
        bar_h = rect.height() - 2 * bar_margin
        
        fill_pct = self._anim_val if self._charging else (self._percent if self._percent is not None else 0)
        if dots:
            # Column of 10 dots, filled from the bottom
            n = 10
            on = 0 if self._offline else round(min(100.0, float(fill_pct)) * n / 100)
            step = bar_h / n
            dot_r = min(bar_w, step) * 0.42
            for i in range(n):
                pt = QPointF(bar_x + bar_w / 2.0, bar_y + bar_h - step * (i + 0.5))
                if i < on:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(color))
                else:
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(theme.c("#2a2a3a")), 1))
                p.drawEllipse(pt, dot_r, dot_r)
            p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QColor(theme.c("#14141d")))
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), bar_w/2.0, bar_w/2.0)
            if not self._offline and fill_pct > 0:
                fill_h = bar_h * (min(100.0, float(fill_pct)) / 100.0)
                fill_y = bar_y + bar_h - fill_h
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(bar_x, fill_y, bar_w, fill_h), bar_w/2.0, bar_w/2.0)

        icon_sz = 44 * scale if dots else 30 * scale  # Inspector: smaller icon, room for the %
        cx = bar_x + bar_w + (rect.width() - (bar_x + bar_w)) / 2.0
        cy = bar_y + icon_sz / 2.0 + 2 * scale
        live = not self._offline and self._percent is not None
        if dots:
            # Big Doto numerals take the place of the icon
            num_font = QFont(theme.display_font())
            num_font.setPixelSize(max(10, int(34 * scale)))
            num_font.setWeight(QFont.Weight.Black)
            num_font.setStyleStrategy(QFont.StyleStrategy.NoSubpixelAntialias)
            p.setFont(num_font)
            p.setPen(QColor(color if live else theme.c("#555566")))
            num_rect = QRectF(bar_x + bar_w, bar_y, rect.width() - (bar_x + bar_w), icon_sz + 4 * scale)
            p.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, f"{self._percent:02d}" if live else "--")
        else:
            draw_device_icon(p, self._category, cx, cy, icon_sz, color if live else theme.c("#555566"))
            pct_font = QFont(theme.family())
            pct_font.setPixelSize(max(9, int(18 * scale)))
            pct_font.setWeight(QFont.Weight.Bold)
            p.setFont(pct_font)
            p.setPen(QColor(color if live else theme.c("#555566")))
            pct_rect = QRectF(bar_x + bar_w, cy + icon_sz / 2.0 + 2 * scale, rect.width() - (bar_x + bar_w), 24 * scale)
            p.drawText(pct_rect, Qt.AlignmentFlag.AlignCenter, f"{self._percent}%" if live else "--")

        p.setPen(QColor(theme.c("#FFFFFF")) if not self._offline else QColor(theme.c("#555566")))
        font = QFont(theme.family())
        font.setPointSize(max(7, int(9 * scale)))
        p.setFont(font)

        display_name = self._name.upper() if dots else self._name
        if len(display_name) > 10:
            display_name = display_name[:8] + ".."
        
        name_y = cy + icon_sz / 2.0 + (4 if dots else 28) * scale
        text_rect = QRectF(bar_x + bar_w, name_y, rect.width() - (bar_x + bar_w), rect.height() - name_y)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, display_name)


class MinimalListRowUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self._name_lbl = QLabel()
        self._pct_lbl = QLabel()
        if theme.is_dots():
            self._bar = DotBar()
        else:
            self._bar = QProgressBar()
            self._bar.setTextVisible(False)
            self._bar.setRange(0, 100)
        
        layout.addWidget(self._name_lbl, 1)
        layout.addWidget(self._pct_lbl)
        layout.addSpacing(10)
        layout.addWidget(self._bar)

        self._scale = 1.0

    def set_anim_val(self, val: float):
        self._bar.setValue(int(val))

    def set_state(self, name, percent, charging, offline, category, color):
        scale = self._scale
        name_font_sz = max(6, int(9 * scale))
        pct_font_sz = max(6, int(9 * scale))

        display_name = name.upper() if theme.is_dots() else name
        limit = 13 if theme.is_dots() else 18  # wide mono caps need room for the % label
        if len(display_name) > limit:
            display_name = display_name[:limit - 2] + ".."

        if percent is not None and not offline:
            self._pct_lbl.setText(f"{percent}%")
            self._pct_lbl.setStyleSheet(f"{_num_font()}font-size: {pct_font_sz}pt; font-weight: bold; color: {color};")
            self._name_lbl.setText(display_name)
            self._name_lbl.setStyleSheet(f"font-size: {name_font_sz}pt; font-weight: bold; color: #FFFFFF;")
            if not charging:
                self._bar.setValue(percent)
        else:
            self._pct_lbl.setText("--")
            self._pct_lbl.setStyleSheet(f"font-size: {pct_font_sz}pt; font-weight: bold; color: #555566;")
            self._name_lbl.setText(display_name)
            self._name_lbl.setStyleSheet(f"font-size: {name_font_sz}pt; font-weight: bold; color: #555566;")
            self._bar.setValue(0)
            
        if theme.is_dots():
            self._bar.set_color(color if percent is not None and not offline else theme.c("#555566"))
        else:
            self._bar.setStyleSheet(f"""
                QProgressBar {{ background-color: #2a2a3a; border: none; border-radius: {max(2, int(4*scale))}px; }}
                QProgressBar::chunk {{ background-color: {color}; border-radius: {max(2, int(4*scale))}px; }}
            """)

    def apply_scale(self, scale):
        self._scale = scale
        self.setFixedHeight(int(28 * scale))
        self.layout().setContentsMargins(int(12 * scale), int(4 * scale), int(12 * scale), int(4 * scale))
        if theme.is_dots():
            self._bar.setFixedSize(int(60 * scale), int(10 * scale))
        else:
            self._bar.setFixedSize(int(32 * scale), int(12 * scale))


class HorizontalRingsRowUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._container = QFrame()
        radius = 0 if theme.is_dots() else 6
        self._container.setStyleSheet(f"background: #121218; border: 1px solid #2a2a3a; border-radius: {radius}px;")
        
        c_layout = QHBoxLayout(self._container)
        
        self._ring = MiniBatteryRing(size=40, stroke=4)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        self._name_lbl = QLabel()
        self._pct_lbl = QLabel()
        text_layout.addWidget(self._name_lbl)
        text_layout.addWidget(self._pct_lbl)
        text_layout.addStretch()
        
        c_layout.addWidget(self._ring)
        c_layout.addLayout(text_layout)
        
        layout.addWidget(self._container)
        self._scale = 1.0

    def set_anim_val(self, val: float):
        pass

    def set_state(self, name, percent, charging, offline, category, color):
        self._ring.set_state(percent, charging, offline, category)
        scale = self._scale
        name_font_sz = max(5, int(7 * scale))
        pct_font_sz = max(6, int(8 * scale))

        display_name = name.upper()
        limit = 12 if theme.is_dots() else 16
        if len(display_name) > limit:
            display_name = display_name[:limit - 2] + ".."

        if percent is not None and not offline:
            self._pct_lbl.setText(f"{percent}%")
            self._pct_lbl.setStyleSheet(f"{_num_font()}font-size: {pct_font_sz}pt; font-weight: bold; color: {color}; border: none; background: transparent;")
            self._name_lbl.setText(display_name)
            self._name_lbl.setStyleSheet(f"font-size: {name_font_sz}pt; color: #FFFFFF; border: none; background: transparent;")
        else:
            self._pct_lbl.setText("--")
            self._pct_lbl.setStyleSheet(f"font-size: {pct_font_sz}pt; font-weight: bold; color: #555566; border: none; background: transparent;")
            self._name_lbl.setText(display_name)
            self._name_lbl.setStyleSheet(f"font-size: {name_font_sz}pt; color: #555566; border: none; background: transparent;")

    def apply_scale(self, scale):
        self._scale = scale
        self.setFixedSize(int(145 * scale), int(54 * scale))
        self.layout().setContentsMargins(int(4*scale), int(4*scale), int(4*scale), int(4*scale))
        self._container.layout().setContentsMargins(int(8*scale), int(6*scale), int(8*scale), int(6*scale))
        self._container.layout().setSpacing(int(10*scale))
        self._ring.apply_scale(max(24, int(34 * scale)), max(2, int(4 * scale)))

        
class _DeviceRow(QFrame):
    """Device visualization block with dynamic layouts."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("deviceRow")
        cfg = load_config()
        self._layout_mode = cfg.get("widget_layout_mode", "stack")
        self._scale = cfg.get("widget_scale", 1.0)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self._layout_mode == "stack":
            self._ui = VerticalBlockRowUI()
        elif self._layout_mode == "horizontal":
            self._ui = MinimalListRowUI()
        elif self._layout_mode == "iphone":
            self._ui = HorizontalRingsRowUI()
        else:
            self._ui = VerticalBlockRowUI()
            
        layout.addWidget(self._ui)

        from PySide6.QtCore import QTimer
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(30)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_val = 0.0
        self._percent_val = 0
        self._last_refresh_args = None

    def apply_scale(self, scale: float) -> None:
        self._scale = scale
        self._ui.apply_scale(scale)
        if self._layout_mode == "horizontal":
            self.setFixedHeight(self._ui.height())
            self.setMinimumWidth(int(100 * scale))
            self.setMaximumWidth(16777215)
        else:
            self.setFixedSize(self._ui.size())

    def _on_anim_tick(self) -> None:
        if self._percent_val > 0:
            step = max(1.0, self._percent_val / 40.0)
            self._anim_val += step
            if self._anim_val > self._percent_val:
                self._anim_val = 0.0
            self._ui.set_anim_val(self._anim_val)

    def refresh(self, name: str, percent: int | None, charging: bool, offline: bool, threshold: int = 15) -> None:
        self._last_refresh_args = (name, percent, charging, offline, threshold)
        color = get_ring_color(percent, charging, offline)
        category = get_device_category(name)
        
        self._percent_val = percent if percent is not None else 0
        if charging and not offline:
            if not self._anim_timer.isActive():
                self._anim_val = 0.0
                self._anim_timer.start()
        else:
            self._anim_timer.stop()

        self._ui.set_state(name, percent, charging, offline, category, color)


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
        
        self.setStyleSheet("""
            WidgetWindow, QWidget#widgetHeader, QWidget#widgetRows, _DeviceRow {
                background: transparent;
            }
        """)

        # ── Outer container (border + rounded corners) ────────────────
        self._container = QFrame()
        self._container.setObjectName("widgetContainer")
        
        # Load scale config
        cfg = load_config()
        self._scale = cfg.get("widget_scale", 1.0)
        
        self._apply_opacity()

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, int(8 * self._scale))
        container_layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setObjectName("widgetHeader")
        self._header.setFixedHeight(int(38 * self._scale))
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(int(12 * self._scale), 0, int(8 * self._scale), 0)
        header_layout.setSpacing(int(4 * self._scale))

        self._title_lbl = QLabel()
        import os
        from PySide6.QtGui import QPixmap
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self._title_lbl.setPixmap(pixmap.scaledToHeight(int(16 * self._scale), Qt.TransformationMode.SmoothTransformation))
            else:
                self._title_lbl.setText("VOLT")
                self._title_lbl.setStyleSheet(f"font-size: {max(5, int(8 * self._scale))}pt; font-weight: bold; color: #444455;")
        else:
            self._title_lbl.setText("VOLT")
            self._title_lbl.setStyleSheet(f"font-size: {max(5, int(8 * self._scale))}pt; font-weight: bold; color: #444455;")

        self._expand_btn = QPushButton("⊡")
        self._expand_btn.setFixedSize(int(22 * self._scale), int(22 * self._scale))
        self._expand_btn.setToolTip("Expand to full window")
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: #555566; border: none;"
            f" font-size: {max(6, int(10 * self._scale))}pt; border-radius: {max(2, int(3 * self._scale))}px; }}"
            f"QPushButton:hover {{ color: #7B9FFF; background: #2a2a38; }}"
        )
        self._expand_btn.clicked.connect(self._exit_callback)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(int(22 * self._scale), int(22 * self._scale))
        self._close_btn.setToolTip("Hide to tray")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: #555566; border: none;"
            f" font-size: {max(5, int(8 * self._scale))}pt; border-radius: {max(2, int(3 * self._scale))}px; }}"
            f"QPushButton:hover {{ color: #FFFFFF; background: #C0392B; }}"
        )
        self._close_btn.clicked.connect(self.hide)

        header_layout.addWidget(self._title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self._expand_btn)
        header_layout.addWidget(self._close_btn)

        container_layout.addWidget(self._header)

        # Rebuild layout to initialize self._rows_widget and self._rows_layout
        self.rebuild_layout()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._container)

        self._apply_flags()
        self._restore_position()

    # ── Scaling API ───────────────────────────────────────────────────

    def apply_scale(self, scale: float) -> None:
        """Apply a new scale factor dynamically to the entire widget and its rows."""
        self._scale = scale
        self._container.layout().setContentsMargins(0, 0, 0, int(8 * scale))
        
        self._header.setFixedHeight(int(38 * scale))
        self._header.layout().setContentsMargins(int(12 * scale), 0, int(8 * scale), 0)
        self._header.layout().setSpacing(int(4 * scale))
        
        import os
        from PySide6.QtGui import QPixmap
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                self._title_lbl.setPixmap(pixmap.scaledToHeight(int(16 * scale), Qt.TransformationMode.SmoothTransformation))
            else:
                self._title_lbl.setStyleSheet(f"font-size: {max(5, int(8 * scale))}pt; font-weight: bold; color: #444455;")
        else:
            self._title_lbl.setStyleSheet(f"font-size: {max(5, int(8 * scale))}pt; font-weight: bold; color: #444455;")
        self._expand_btn.setFixedSize(int(22 * scale), int(22 * scale))
        self._expand_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: #555566; border: none;"
            f" font-size: {max(6, int(10 * scale))}pt; border-radius: {max(2, int(3 * scale))}px; }}"
            f"QPushButton:hover {{ color: #7B9FFF; background: #2a2a38; }}"
        )
        self._close_btn.setFixedSize(int(22 * scale), int(22 * scale))
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: #555566; border: none;"
            f" font-size: {max(5, int(8 * scale))}pt; border-radius: {max(2, int(3 * scale))}px; }}"
            f"QPushButton:hover {{ color: #FFFFFF; background: #C0392B; }}"
        )

        # Clear and rebuild layout structure
        self.rebuild_layout()

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
                background-color: {theme.rgba("#202026", opacity)};
                border: 1px solid #2a2a38;
                border-radius: {0 if theme.is_dots() else 10}px;
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
            if key in self._rows:
                self._rows[key].setVisible(False)
                self._update_empty_label()
                self.resize_to_fit()
            return

        if isinstance(key, tuple) and len(key) == 3:
            device_id = f"hid:{key[0]:04X}:{key[1]:04X}"
            if key[2] != 0xFF:
                device_id = f"{device_id}:{key[2]:02X}"
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
        self._rows[key]._scale = self._scale
        self._rows[key].apply_scale(self._scale)
        self._rows[key].refresh(name, percent, charging, offline, threshold=threshold)
        self._rows[key].setVisible(True)
        self._update_empty_label()
        self.resize_to_fit()

    def remove_device(self, key) -> None:
        """Remove the row for this device key."""
        row = self._rows.pop(key, None)
        if row:
            self._rows_layout.removeWidget(row)
            row.setParent(None)
        self._update_empty_label()
        self.resize_to_fit()

    def rebuild_layout(self) -> None:
        """Clear all rows and recreate self._rows_widget with the new layout mode."""
        # Save temporary list of device states
        current_devices = []
        for key, row in list(self._rows.items()):
            if getattr(row, "_last_refresh_args", None) is not None:
                current_devices.append((key, row._last_refresh_args, not row.isHidden()))

        for key in list(self._rows.keys()):
            row = self._rows.pop(key)
            row.setParent(None)
            row.deleteLater()
            
        if hasattr(self, "_rows_widget") and self._rows_widget is not None:
            self._container.layout().removeWidget(self._rows_widget)
            self._rows_widget.setParent(None)
            self._rows_widget.deleteLater()
            
        cfg = load_config()
        layout_mode = cfg.get("widget_layout_mode", "stack")
        scale = self._scale
        
        self._rows_widget = QWidget()
        self._rows_widget.setObjectName("widgetRows")
        self._rows_widget.setStyleSheet("background: transparent;")
        
        if layout_mode == "stack":
            self._rows_layout = QVBoxLayout(self._rows_widget)
            self._rows_layout.setContentsMargins(int(10*scale), int(4*scale), int(10*scale), int(8*scale))
            self._rows_layout.setSpacing(int(8*scale))
        elif layout_mode == "horizontal":
            self._rows_layout = QVBoxLayout(self._rows_widget)
            self._rows_layout.setContentsMargins(0, int(4*scale), 0, int(8*scale))
            self._rows_layout.setSpacing(0)
        elif layout_mode == "iphone":
            self._rows_layout = QHBoxLayout(self._rows_widget)
            self._rows_layout.setContentsMargins(int(8*scale), int(4*scale), int(8*scale), int(8*scale))
            self._rows_layout.setSpacing(0)
            
        self._empty_lbl = QLabel("No devices")
        self._empty_lbl.setStyleSheet(f"font-size: {max(6, int(9 * scale))}pt; color: #444455; padding: {int(6 * scale)}px {int(12 * scale)}px;")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rows_layout.addWidget(self._empty_lbl)
        
        self._container.layout().addWidget(self._rows_widget)

        # Re-add and scale all devices
        for key, last_args, was_visible in current_devices:
            name, percent, charging, offline, threshold = last_args
            self.update_device(key, name, percent, charging, offline)
            if not was_visible:
                self._rows[key].setVisible(False)

        self._update_empty_label()
        self.resize_to_fit()

    def _update_empty_label(self) -> None:
        any_visible = any(not r.isHidden() for r in self._rows.values())
        self._empty_lbl.setVisible(not any_visible)

    def resize_to_fit(self) -> None:
        """Dynamically set the window fixed size based on visible devices and layout mode."""
        old_geom = self.geometry()
        
        visible_rows = [r for r in self._rows.values() if r is not None and not r.isHidden()]
        visible_count = len(visible_rows)
        
        cfg = load_config()
        layout_mode = cfg.get("widget_layout_mode", "stack")
        scale = self._scale
        
        w, h = 0, 0
        if visible_count == 0:
            if layout_mode == "stack":
                w, h = int(84 * scale), int(78 * scale)
            elif layout_mode == "horizontal":
                w, h = int(220 * scale), int(78 * scale)
            elif layout_mode == "iphone":
                w, h = int(161 * scale), int(78 * scale)
        else:
            if layout_mode == "stack":
                w = int(104 * scale)
                h = 38 + 4 + 8 + visible_count * 88 + max(0, visible_count - 1) * 8
                h = int(h * scale)
            elif layout_mode == "horizontal":
                w = int(220 * scale)
                h = 38 + 4 + 8 + visible_count * 28
                h = int(h * scale)
            elif layout_mode == "iphone":
                w = 8 + 8 + visible_count * 145
                w = int(w * scale)
                h = int(104 * scale)
                
        # Enforce exact fixed dimensions matching the content scale
        self.setMinimumSize(w, h)
        self.setMaximumSize(w, h)
        
        if old_geom.width() > 0 and old_geom.height() > 0 and (old_geom.width() != w or old_geom.height() != h):
            screen = self.screen()
            if screen:
                screen_geom = screen.geometry()
                new_x = old_geom.x()
                new_y = old_geom.y()
                
                # If widget center is in the right half of the screen, keep right edge anchored
                if old_geom.center().x() > screen_geom.center().x():
                    new_x = old_geom.right() - w + 1
                    
                # If widget center is in the bottom half of the screen, keep bottom edge anchored
                if old_geom.center().y() > screen_geom.center().y():
                    new_y = old_geom.bottom() - h + 1
                    
                self.setGeometry(new_x, new_y, w, h)
                self._save_position()
            else:
                self.resize(w, h)
        else:
            self.resize(w, h)

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
