"""FlowLayout — wrapping card layout for the VOLT | POWER CENTER dashboard.

Items are placed left-to-right and wrap to the next row when the available
width is exhausted. Implements hasHeightForWidth so QScrollArea adjusts the
container height as cards wrap to additional rows.
"""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class FlowLayout(QLayout):
    """Wrapping flow layout. Add widgets with addWidget(); they wrap automatically."""

    def __init__(self, parent=None, h_spacing: int = 16, v_spacing: int = 16) -> None:
        super().__init__(parent)
        self._items: list = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    # ── QLayout interface ──────────────────────────────────────────

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    # ── Layout engine ─────────────────────────────────────────────

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = eff.x(), eff.y(), 0

        for item in self._items:
            w = item.widget()
            if w is not None and w.isHidden():
                continue
            item_w = item.sizeHint().width()
            item_h = item.sizeHint().height()
            next_x = x + item_w
            if next_x > eff.right() and line_h > 0:
                x = eff.x()
                y += line_h + self._v_spacing
                next_x = x + item_w
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x + self._h_spacing
            line_h = max(line_h, item_h)

        return y + line_h - rect.y() + m.bottom()
