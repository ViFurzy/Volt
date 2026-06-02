"""DeviceCard — QFrame widget displaying a single device's battery state.

Uses QFrame (concrete QWidget subclass) deliberately so QSS background-color
applies without the paintEvent workaround required for raw QWidget subclasses
(Research Pitfall 1).

Layout (top to bottom):
    device name  (large title label)
    battery %    (large value label, threshold-colored)
    status line  (status text + charging indicator)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout

from monitor.state import DeviceStatus
from ui.settings_manager import battery_color

if TYPE_CHECKING:
    from monitor.state import DeviceState


class DeviceCard(QFrame):
    """Card widget for one monitored peripheral.

    Displays device name, battery percentage (threshold-colored), and status.
    OFFLINE state sets the 'offline' property to True so QSS can mute the card.
    """

    def __init__(
        self,
        state: DeviceState | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deviceCard")

        # ---------------------------------------------------------------
        # Build child widgets
        # ---------------------------------------------------------------
        # Device name — large title
        self._name = QLabel()
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setStyleSheet("font-size: 15px; font-weight: bold;")

        # Battery percentage — large prominent value
        self._percent = QLabel()
        self._percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._percent.setStyleSheet("font-size: 36px; font-weight: bold;")

        # Status text (ONLINE / OFFLINE / CHARGING)
        self._status = QLabel()
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("font-size: 12px;")

        # Charging indicator — shown only when charging is True
        self._charging_indicator = QLabel("⚡ Charging")
        self._charging_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._charging_indicator.setStyleSheet("font-size: 12px; color: #4FC3F7;")
        self._charging_indicator.setVisible(False)

        # ---------------------------------------------------------------
        # Layout: name, %, status row (status + charging)
        # ---------------------------------------------------------------
        status_row = QHBoxLayout()
        status_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.setSpacing(8)
        status_row.addWidget(self._status)
        status_row.addWidget(self._charging_indicator)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.addWidget(self._name)
        layout.addWidget(self._percent)
        layout.addLayout(status_row)

        # ---------------------------------------------------------------
        # Initialise with state (if provided)
        # ---------------------------------------------------------------
        if state is not None:
            self.update_state(state)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_state(self, state: DeviceState) -> None:
        """Refresh all labels and visual properties from a DeviceState snapshot."""
        # Name
        self._name.setText(state.device_name)

        # Battery percentage
        if state.percent is not None:
            self._percent.setText(f"{state.percent}%")
        else:
            self._percent.setText("--")
        color = battery_color(state.percent)
        self._percent.setStyleSheet(
            f"font-size: 36px; font-weight: bold; color: {color};"
        )

        # Status text
        self._status.setText(state.status.name)

        # Charging indicator
        self._charging_indicator.setVisible(state.charging)

        # Offline muting via Qt property (enables QSS [offline="true"] selector)
        # and QGraphicsOpacityEffect (QSS `opacity` is not a valid property — WR-04).
        is_offline = state.status == DeviceStatus.OFFLINE
        self.setProperty("offline", is_offline)
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(0.45 if is_offline else 1.0)
        self.setGraphicsEffect(effect)
        # Re-polish so QSS picks up the property change
        self.style().unpolish(self)
        self.style().polish(self)
