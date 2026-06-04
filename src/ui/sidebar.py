"""Sidebar navigation — VOLT | POWER CENTER.

Header: "Volt" title + "POWER CENTER" subtitle.
Nav items: Dashboard, Devices (expandable with device sub-items), Settings.
Active state: left blue bar + #282366 bg + #7B9FFF text.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

SIDEBAR_WIDTH: int = 210

# (display label, stack page index)
_NAV_ITEMS: list[tuple[str, int]] = [
    ("Dashboard", 0),
    ("Devices",   0),
    ("Settings",  4),
]


class SidebarNav(QWidget):
    """Left navigation rail with Volt branding and device sub-items."""

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────
        root.addWidget(self._build_header())

        sep = QFrame()
        sep.setObjectName("sidebarSep")
        sep.setFixedHeight(1)
        root.addWidget(sep)
        root.addSpacing(8)

        # ── Nav buttons ───────────────────────────────────────────
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._devices_panel: QWidget | None = None
        self._devices_layout: QVBoxLayout | None = None
        self._device_buttons: dict[tuple, QPushButton] = {}

        for btn_id, (label, _page) in enumerate(_NAV_ITEMS):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("navButton")
            self._group.addButton(btn, btn_id)
            root.addWidget(btn)

            if label == "Devices":
                # Collapsible panel for connected device sub-items
                self._devices_panel = QWidget()
                self._devices_panel.setVisible(False)
                self._devices_layout = QVBoxLayout(self._devices_panel)
                self._devices_layout.setContentsMargins(0, 0, 0, 4)
                self._devices_layout.setSpacing(1)
                root.addWidget(self._devices_panel)

        root.addStretch()

        # ── Wire navigation ───────────────────────────────────────
        def _on_click(btn_id: int) -> None:
            stack.setCurrentIndex(_NAV_ITEMS[btn_id][1])
            # Toggle device sub-items panel when Devices is active
            if self._devices_panel is not None:
                self._devices_panel.setVisible(btn_id == 1)

        self._group.idClicked.connect(_on_click)

        # Default: Dashboard
        btn0 = self._group.button(0)
        if btn0 is not None:
            btn0.setChecked(True)

    # ── Header ────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("sidebarHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(2)

        title = QLabel("Volt")
        title.setObjectName("voltTitle")

        subtitle = QLabel("POWER CENTER")
        subtitle.setObjectName("voltSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    # ── Device sub-items API ──────────────────────────────────────

    def register_device(self, key: tuple, device_name: str) -> None:
        """Add a connected device as a sub-item under Devices."""
        if key in self._device_buttons or self._devices_layout is None:
            return
        btn = QPushButton(device_name)
        btn.setObjectName("deviceSubItem")
        btn.setCheckable(False)
        self._devices_layout.addWidget(btn)
        self._device_buttons[key] = btn

    def remove_device(self, key: tuple) -> None:
        """Remove a device sub-item (called when device goes permanently offline)."""
        btn = self._device_buttons.pop(key, None)
        if btn is not None and self._devices_layout is not None:
            self._devices_layout.removeWidget(btn)
            btn.deleteLater()

    # ── QSS background support ────────────────────────────────────

    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
