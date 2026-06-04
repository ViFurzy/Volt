"""VOLT app icon — generated via QPainter, no external asset required.

Draws the V+lightning bolt logo in chrome/silver gradient at multiple
resolutions and returns a QIcon suitable for window, taskbar, and tray.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)

_SIZES = (16, 24, 32, 48, 64, 128, 256)


def make_volt_icon() -> QIcon:
    """Return a multi-resolution QIcon with the VOLT V+bolt logo."""
    icon = QIcon()
    for sz in _SIZES:
        icon.addPixmap(_render(sz))
    return icon


def _render(size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    def s(v: float) -> float:
        """Scale a 256-unit coordinate to the target size."""
        return v * size / 256

    # Chrome/silver gradient — bright highlight at top, dark silver at bottom
    grad = QLinearGradient(s(0), s(0), s(0), s(256))
    grad.setColorAt(0.00, QColor("#DEDEDE"))
    grad.setColorAt(0.30, QColor("#FFFFFF"))
    grad.setColorAt(0.65, QColor("#BBBBBB"))
    grad.setColorAt(1.00, QColor("#808080"))

    # ── Left arm of V ─────────────────────────────────────────────
    left = QPainterPath()
    left.moveTo(s(28),  s(14))
    left.lineTo(s(82),  s(14))
    left.lineTo(s(128), s(196))
    left.lineTo(s(102), s(196))
    left.closeSubpath()
    p.fillPath(left, grad)

    # ── Right arm of V ────────────────────────────────────────────
    right = QPainterPath()
    right.moveTo(s(228), s(14))
    right.lineTo(s(174), s(14))
    right.lineTo(s(128), s(196))
    right.lineTo(s(154), s(196))
    right.closeSubpath()
    p.fillPath(right, grad)

    # ── Lightning bolt (center, pointing down-left) ───────────────
    bolt = QPainterPath()
    bolt.moveTo(s(152), s(14))   # top-right
    bolt.lineTo(s(114), s(120))  # mid-left step
    bolt.lineTo(s(136), s(120))  # mid-right indent
    bolt.lineTo(s(98),  s(242))  # bottom tip
    bolt.lineTo(s(166), s(112))  # lower-right step
    bolt.lineTo(s(144), s(112))  # lower indent
    bolt.closeSubpath()
    p.fillPath(bolt, grad)

    p.end()
    return px
