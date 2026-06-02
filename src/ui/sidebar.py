"""Sidebar navigation widget for PeriphWatcher.

SidebarNav drives a QStackedWidget via an exclusive QButtonGroup.
Button indices map 1:1 to stack page indices (D-03).
"""
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

_NAV_ITEMS: list[tuple[str, int]] = [
    ("Dashboard", 0),
    ("Devices",   1),
    ("History",   2),
    ("Profiles",  3),
    ("Settings",  4),
]

SIDEBAR_WIDTH: int = 160


class SidebarNav(QWidget):
    """Exclusive checkable QPushButtons connected to a QStackedWidget.

    Each button's id (set via QButtonGroup.addButton(btn, idx)) matches the
    corresponding QStackedWidget page index.  idClicked fires the integer id,
    which is forwarded directly to stack.setCurrentIndex (Pitfall 5).
    """

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(SIDEBAR_WIDTH)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        for label, idx in _NAV_ITEMS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            self._group.addButton(btn, idx)
            layout.addWidget(btn)

        layout.addStretch()

        # Wire button clicks -> page changes (idClicked requires explicit id — Pitfall 5)
        self._group.idClicked.connect(stack.setCurrentIndex)

        # Start on Dashboard (index 0)
        btn0 = self._group.button(0)
        if btn0 is not None:
            btn0.setChecked(True)

    # ------------------------------------------------------------------
    # paintEvent override required for QSS background-color to render on
    # direct QWidget subclasses (Research Pattern 3 / Pitfall 1).
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
