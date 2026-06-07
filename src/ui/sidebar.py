"""Sidebar navigation — VOLT | POWER CENTER.

Header: "Volt" title + "POWER CENTER" subtitle.
Nav items: Dashboard, Devices (expandable with device sub-items), Settings.
Active state: left blue bar + #282366 bg + #7B9FFF text.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from ui.icon import make_volt_icon

SIDEBAR_WIDTH: int = 210

# (display label, stack page index)
_NAV_ITEMS: list[tuple[str, int]] = [
    ("Dashboard", 0),
    ("Devices",   1),
    ("Settings",  4),
]


class SidebarNav(QWidget):
    """Left navigation rail with Volt branding and device sub-items."""

    device_selected = Signal(object, str)

    def __init__(self, stack: QStackedWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self._stack = stack

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
        self._device_buttons: dict[tuple | str, QPushButton] = {}

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

        # ── About ─────────────────────────────────────────────────
        about_sep = QFrame()
        about_sep.setObjectName("sidebarSep")
        about_sep.setFixedHeight(1)
        root.addWidget(about_sep)

        _about_style = "font-size: 11px; color: #555566; padding: 0; background: transparent;"
        root.addSpacing(10)
        for text in ("v1.0", "ViFurzy | vi-design.pro", "MIT License"):
            lbl = QLabel(text)
            lbl.setStyleSheet(_about_style)
            lbl.setContentsMargins(16, 0, 16, 0)
            root.addWidget(lbl)
        root.addSpacing(14)

        # ── Wire navigation ───────────────────────────────────────
        def _on_click(btn_id: int) -> None:
            self._clear_device_selections()
            self._stack.setCurrentIndex(_NAV_ITEMS[btn_id][1])
            # Toggle device sub-items panel when Devices is active OR when history is shown (index 2)
            if self._devices_panel is not None:
                self._devices_panel.setVisible(btn_id == 1 or self._stack.currentIndex() == 2)

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
        layout.setContentsMargins(16, 32, 16, 24)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel()
        icon_label.setPixmap(make_volt_icon().pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("Volt")
        title.setObjectName("voltTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("POWER CENTER")
        subtitle.setObjectName("voltSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        
        return header

    def navigate_to(self, btn_id: int) -> None:
        """Programmatically activate a nav button (equivalent to clicking it)."""
        btn = self._group.button(btn_id)
        if btn is not None:
            btn.click()

    # ── Device sub-items API ──────────────────────────────────────

    def _clear_device_selections(self) -> None:
        for btn in self._device_buttons.values():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)

    def _on_device_click(self, key: tuple | str, device_name: str) -> None:
        # Uncheck main nav buttons
        self._group.blockSignals(True)
        checked_btn = self._group.checkedButton()
        if checked_btn:
            self._group.setExclusive(False)
            checked_btn.setChecked(False)
            self._group.setExclusive(True)
        self._group.blockSignals(False)

        # Toggle state for device buttons
        for k, btn in self._device_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(k == key)
            btn.blockSignals(False)

        self._stack.setCurrentIndex(2)
        self.device_selected.emit(key, device_name)

    def register_device(self, key: tuple | str, device_name: str) -> None:
        """Add a connected device as a sub-item under Devices."""
        if key in self._device_buttons or self._devices_layout is None:
            return
        btn = QPushButton(device_name)
        btn.setObjectName("deviceSubItem")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._on_device_click(key, device_name))
        self._devices_layout.addWidget(btn)
        self._device_buttons[key] = btn

    def remove_device(self, key: tuple | str) -> None:
        """Remove a device sub-item (called when device goes permanently offline)."""
        btn = self._device_buttons.pop(key, None)
        if btn is not None and self._devices_layout is not None:
            self._devices_layout.removeWidget(btn)
            btn.deleteLater()

    def select_device_by_key(self, key: tuple | str) -> None:
        """Programmatically select a device sub-item and switch to its history."""
        matched_key = None
        matched_name = None
        if isinstance(key, str) and key.startswith("hid:"):
            parts = key.split(":")
            if len(parts) == 3:
                try:
                    vid = int(parts[1], 16)
                    pid = int(parts[2], 16)
                    for k, btn in self._device_buttons.items():
                        if isinstance(k, tuple) and len(k) == 3 and k[0] == vid and k[1] == pid:
                            matched_key = k
                            matched_name = btn.text()
                            break
                except Exception:
                    pass
        if matched_key is None and key in self._device_buttons:
            matched_key = key
            matched_name = self._device_buttons[key].text()
            
        if matched_key is not None and matched_name is not None:
            if self._devices_panel is not None:
                self._devices_panel.setVisible(True)
            self._on_device_click(matched_key, matched_name)

    # ── QSS background support ────────────────────────────────────

    def paintEvent(self, event) -> None:  # type: ignore[override]
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
