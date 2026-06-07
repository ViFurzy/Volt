"""History page showing battery history graphs for monitored devices."""
import datetime
from typing import Any
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath, QLinearGradient, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QButtonGroup, QPushButton, QFrame, QDialog
)

from ui.settings_manager import load_config, save_config
from ui.device_card import BatteryGauge
from ui.estimation import calculate_time_remaining
from ui.threshold_dialog import ThresholdDialog
from ui.settings_page import ToggleSwitch
from monitor.state import DeviceState, BtDeviceInfo, DeviceStatus


class HistoryGraph(QWidget):
    """Custom QPainter-based line chart showing battery history over time."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(350)
        self._history: list[dict] = []
        self._time_range: str = "all"

    def set_history(self, history: list[dict], time_range: str = "all") -> None:
        self._history = history
        self._time_range = time_range
        self.update()

    def _get_battery_color(self, percent: int | None) -> str:
        """Return the hex color for a given battery percentage (green -> yellow -> red)."""
        if percent is None:
            return "#888888"
        if percent <= 8:
            return "#EE6800"  # critical red-orange
        if percent <= 45:
            return "#F0BB66"  # warning yellow/amber
        return "#4CAF50"      # high green

    def paintEvent(self, event) -> None:  # type: ignore[override]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Margins
        margin_left = 50
        margin_right = 30
        margin_top = 40
        margin_bottom = 40

        graph_w = w - margin_left - margin_right
        graph_h = h - margin_top - margin_bottom

        # Grid lines (0%, 20%, 40%, 60%, 80%, 100%)
        grid_font = QFont("Segoe UI", 9)
        p.setFont(grid_font)
        for pct in (0, 20, 40, 60, 80, 100):
            y = margin_top + graph_h - (pct * graph_h // 100)
            
            # Grid line
            grid_pen = QPen(QColor("#2a2a38"))
            grid_pen.setStyle(Qt.PenStyle.DashLine)
            grid_pen.setWidth(1)
            p.setPen(grid_pen)
            p.drawLine(margin_left, y, w - margin_right, y)
            
            # Label
            p.setPen(QColor("#888899"))
            p.drawText(
                margin_left - 45, y - 8, 40, 16,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{pct}%"
            )

        # Determine time window bounds (t_min, t_max)
        now = datetime.datetime.now()
        if self._time_range == "1h":
            t_max = now.timestamp()
            t_min = (now - datetime.timedelta(hours=1)).timestamp()
        elif self._time_range == "4h":
            t_max = now.timestamp()
            t_min = (now - datetime.timedelta(hours=4)).timestamp()
        elif self._time_range == "24h":
            t_max = now.timestamp()
            t_min = (now - datetime.timedelta(hours=24)).timestamp()
        elif self._time_range == "7d":
            t_max = now.timestamp()
            t_min = (now - datetime.timedelta(days=7)).timestamp()
        else:  # "all"
            if self._history:
                parsed_times = []
                for entry in self._history:
                    try:
                        dt = datetime.datetime.fromisoformat(entry["timestamp"])
                        parsed_times.append(dt)
                    except Exception:
                        parsed_times.append(now)
                t_floats = [t.timestamp() for t in parsed_times]
                t_min = min(t_floats)
                t_max = max(t_floats)
                if t_min == t_max:
                    t_min -= 1800  # 30 minutes before
                    t_max += 1800  # 30 minutes after
            else:
                t_max = now.timestamp()
                t_min = (now - datetime.timedelta(hours=24)).timestamp()

        t_diff = t_max - t_min

        # Draw empty message if no history
        if not self._history:
            font = QFont("Segoe UI", 11)
            p.setFont(font)
            p.setPen(QColor("#666677"))
            p.drawText(
                QRectF(margin_left, margin_top, graph_w, graph_h),
                Qt.AlignmentFlag.AlignCenter,
                "No history data recorded in this period.",
            )

        # Parse timestamps and scale points (if we have history)
        points: list[QPointF] = []
        if self._history:
            parsed_times = []
            for entry in self._history:
                try:
                    dt = datetime.datetime.fromisoformat(entry["timestamp"])
                    parsed_times.append(dt)
                except Exception:
                    parsed_times.append(now)

            t_floats = [t.timestamp() for t in parsed_times]

            # Map to screen coordinates
            for i, entry in enumerate(self._history):
                pct = entry["percent"]
                t = t_floats[i]
                
                if t_diff > 0:
                    x = margin_left + (t - t_min) * graph_w / t_diff
                else:
                    x = margin_left + graph_w / 2
                x = max(margin_left, min(margin_left + graph_w, x))
                
                y = margin_top + graph_h - (pct * graph_h / 100)
                points.append(QPointF(x, y))

            # Sort points by x-coordinate to ensure correct left-to-right drawing
            sorted_indices = sorted(range(len(points)), key=lambda idx: points[idx].x())
            points = [points[idx] for idx in sorted_indices]
            history_sorted = [self._history[idx] for idx in sorted_indices]

            # Draw line chart and gradient fill using smooth bezier curves
            if len(points) >= 1:
                # ── Gradient Fill Area ──
                fill_path = QPainterPath()
                fill_path.moveTo(points[0].x(), margin_top + graph_h)
                fill_path.lineTo(points[0])
                for i in range(len(points) - 1):
                    p0 = points[i]
                    p1 = points[i+1]
                    cx = (p0.x() + p1.x()) / 2
                    fill_path.cubicTo(cx, p0.y(), cx, p1.y(), p1.x(), p1.y())
                fill_path.lineTo(points[-1].x(), margin_top + graph_h)
                fill_path.closeSubpath()
                
                # Fill with horizontal gradient (transitions colors based on battery levels)
                fill_grad = QLinearGradient(margin_left, 0, w - margin_right, 0)
                for i, pt in enumerate(points):
                    pct = history_sorted[i]["percent"]
                    color = self._get_battery_color(pct)
                    pos = (pt.x() - margin_left) / graph_w if graph_w > 0 else 0.5
                    pos = max(0.0, min(1.0, pos))
                    c = QColor(color)
                    c.setAlpha(120)  # semi-transparent
                    fill_grad.setColorAt(pos, c)
                p.fillPath(fill_path, fill_grad)

                # Mask/Overlay vertical gradient to fade to dark theme background (#202026 / RGB 32,32,38)
                fade_grad = QLinearGradient(0, margin_top, 0, margin_top + graph_h)
                fade_grad.setColorAt(0.0, QColor(32, 32, 38, 0))
                fade_grad.setColorAt(1.0, QColor(32, 32, 38, 255))
                p.fillPath(fill_path, fade_grad)
                
                # ── Curve Line ──
                line_path = QPainterPath()
                line_path.moveTo(points[0])
                for i in range(len(points) - 1):
                    p0 = points[i]
                    p1 = points[i+1]
                    cx = (p0.x() + p1.x()) / 2
                    line_path.cubicTo(cx, p0.y(), cx, p1.y(), p1.x(), p1.y())
                
                line_grad = QLinearGradient(margin_left, 0, w - margin_right, 0)
                for i, pt in enumerate(points):
                    pct = history_sorted[i]["percent"]
                    color = self._get_battery_color(pct)
                    pos = (pt.x() - margin_left) / graph_w if graph_w > 0 else 0.5
                    pos = max(0.0, min(1.0, pos))
                    line_grad.setColorAt(pos, QColor(color))

                line_pen = QPen(QBrush(line_grad), 3.0)
                line_pen.setWidthF(3.0)
                line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(line_pen)
                p.drawPath(line_path)

                # ── Dots at Data Points ──
                for i, pt in enumerate(points):
                    pct = history_sorted[i]["percent"]
                    color = self._get_battery_color(pct)
                    # Outer dot border (page bg color)
                    p.setBrush(QColor(32, 32, 38))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(pt, 5, 5)
                    # Inner dot (battery level color)
                    p.setBrush(QColor(color))
                    p.drawEllipse(pt, 3, 3)

        # Draw X-axis labels
        p.setPen(QColor("#888899"))
        p.setFont(QFont("Segoe UI", 9))
        
        dt_min = datetime.datetime.fromtimestamp(t_min)
        dt_max = datetime.datetime.fromtimestamp(t_max)
        
        start_str = dt_min.strftime("%H:%M")
        p.drawText(
            margin_left - 10, margin_top + graph_h + 10, 80, 20,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            start_str
        )
        end_str = dt_max.strftime("%H:%M")
        p.drawText(
            w - margin_right - 70, margin_top + graph_h + 10, 80, 20,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            end_str
        )
        day_diff = (dt_max.date() - dt_min.date()).days
        if day_diff > 0:
            date_str = f"{dt_min.strftime('%b %d')} - {dt_max.strftime('%b %d')}"
            date_font = QFont("Segoe UI", 8)
            p.setFont(date_font)
            p.drawText(
                margin_left, margin_top + graph_h + 24, graph_w, 20,
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop,
                date_str
            )
        
        if self._history:
            latest = self._history[-1]
            latest_pct = latest["percent"]
            latest_time = datetime.datetime.fromisoformat(latest["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            title_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            p.setFont(title_font)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(
                margin_left, 10, graph_w, 24,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                f"Latest: {latest_pct}%"
            )
            sub_font = QFont("Segoe UI", 9)
            p.setFont(sub_font)
            p.setPen(QColor("#888899"))
            p.drawText(
                margin_left, 10, graph_w, 24,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                f"Last updated: {latest_time}"
            )

        p.end()


class HistoryPage(QWidget):
    """Page displaying the battery history graph for the selected monitored device."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        self._heading = QLabel("Battery History")
        self._heading.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_row.addWidget(self._heading)
        header_row.addStretch()

        # Filter buttons row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(4)
        
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        
        self._filters = [("1h", "1h"), ("4h", "4h"), ("24h", "24h"), ("7d", "7d"), ("All", "all")]
        for btn_id, (label, val) in enumerate(self._filters):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedSize(50, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("filterButton")
            btn.setStyleSheet(
                "QPushButton#filterButton {"
                "  background-color: transparent; color: #888899; border: 1px solid #2a2a38;"
                "  border-radius: 4px; font-size: 11px; font-weight: bold;"
                "}"
                "QPushButton#filterButton:checked {"
                "  background-color: #282366; color: #7B9FFF; border: 1px solid #7B9FFF;"
                "}"
                "QPushButton#filterButton:hover:!checked {"
                "  background-color: #22222e; color: #AAAACC;"
                "}"
            )
            self._filter_group.addButton(btn, btn_id)
            filter_layout.addWidget(btn)
            
            if val == "all":
                btn.setChecked(True)
                self._active_filter = "all"

        self._filter_group.idClicked.connect(self._on_filter_clicked)
        header_row.addLayout(filter_layout)
        layout.addLayout(header_row)

        # ── Live Data Section ─────────────────────────────────────────
        self._live_container = QFrame()
        self._live_container.setObjectName("liveContainer")
        self._live_container.setStyleSheet("""
            QFrame#liveContainer {
                background-color: #202028;
                border: 1px solid #2a2a38;
                border-radius: 8px;
            }
        """)
        
        live_data_layout = QHBoxLayout(self._live_container)
        live_data_layout.setContentsMargins(20, 20, 30, 20)
        
        # 1. Gauge on the left
        self._gauge = BatteryGauge()
        live_data_layout.addWidget(self._gauge, 0, Qt.AlignmentFlag.AlignLeft)
        
        live_data_layout.addStretch(1)
        
        # 2. Time Remaining in the middle
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self._time_remaining_label = QLabel("Estimating...")
        self._time_remaining_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FFFFFF;")
        self._time_remaining_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        time_desc = QLabel("Time Remaining")
        time_desc.setStyleSheet("font-size: 13px; color: #888899; text-transform: uppercase; letter-spacing: 1px;")
        time_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        center_layout.addWidget(self._time_remaining_label)
        center_layout.addWidget(time_desc)
        live_data_layout.addLayout(center_layout)
        
        live_data_layout.addStretch(1)
        
        # 3. Threshold controls on the right
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Toggle switch for enabling/disabling
        self._enable_toggle = ToggleSwitch("Enable battery warning")
        self._enable_toggle.toggled.connect(self._on_enable_toggled)
        self._enable_toggle.setVisible(False)
        
        self._threshold_btn = QPushButton("Set threshold")
        self._threshold_btn.setFixedSize(140, 30)
        self._threshold_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._threshold_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #7B9FFF;
                border: 1px solid #2a2a38;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2a2a38;
                color: #92AEFF;
            }
            QPushButton:disabled {
                color: #555566;
                border: 1px solid #2a2a38;
            }
        """)
        self._threshold_btn.clicked.connect(self._on_threshold_clicked)
        self._threshold_btn.setVisible(False)
        
        right_layout.addWidget(self._enable_toggle, 0, Qt.AlignmentFlag.AlignRight)
        right_layout.addSpacing(8)
        right_layout.addWidget(self._threshold_btn, 0, Qt.AlignmentFlag.AlignRight)
        
        live_data_layout.addLayout(right_layout)
        
        self._live_container.setVisible(False)
        layout.addWidget(self._live_container)
        
        layout.addSpacing(16)

        self._graph = HistoryGraph()
        layout.addWidget(self._graph)

        self._empty_label = QLabel("No monitored devices. Go to Devices tab to add a device.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("font-size: 14px; color: #888899;")
        layout.addWidget(self._empty_label)

        self._device_id: str | None = None
        self._device_name: str | None = None

    def _on_filter_clicked(self, btn_id: int) -> None:
        self._active_filter = self._filters[btn_id][1]
        self.refresh()

    def set_device(self, device_id: str, device_name: str) -> None:
        """Configure the page to display history for a specific device."""
        self._device_id = device_id
        self._device_name = device_name
        self.refresh()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.refresh()

    def update_state(self, state: Any) -> None:
        """Update live view based on the current state if it matches the selected device."""
        if not self._device_id:
            return
            
        # Extract fields based on duck typing (handles DeviceState, BtDeviceInfo, _BtAdapter)
        percent = getattr(state, "percent", getattr(state, "battery", None))
        status = getattr(state, "status", DeviceStatus.OFFLINE)
        charging = getattr(state, "charging", False)

        is_offline = status == DeviceStatus.OFFLINE
        self._gauge.set_state(percent, charging, is_offline)
        
        # Time estimation
        if is_offline or charging or percent is None:
            self._time_remaining_label.setText("--")
        else:
            est = calculate_time_remaining(self._device_id, percent)
            self._time_remaining_label.setText(est if est else "Estimating...")

    def _on_enable_toggled(self, checked: bool) -> None:
        if not self._device_id:
            return
        
        cfg = load_config()
        if "thresholds" not in cfg:
            cfg["thresholds"] = {}
        if self._device_id not in cfg["thresholds"]:
            cfg["thresholds"][self._device_id] = {}
            
        if checked:
            # If turning on, set to 15% if it was None
            current = cfg["thresholds"][self._device_id].get("threshold_pct", 15)
            if current is None:
                current = 15
            cfg["thresholds"][self._device_id]["threshold_pct"] = current
        else:
            cfg["thresholds"][self._device_id]["threshold_pct"] = None
            
        save_config(cfg)
        self.refresh()

    def _on_threshold_clicked(self) -> None:
        if not self._device_id:
            return
        cfg = load_config()
        thresholds = cfg.get("thresholds", {})
        device_cfg = thresholds.get(self._device_id, {})
        current = device_cfg.get("threshold_pct", 15)
        if current is None:
            current = 15
        
        dialog = ThresholdDialog(current, self)
        if self.window():
            dialog.move(self.window().geometry().center() - dialog.rect().center())
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            val = dialog.value()
            if "thresholds" not in cfg:
                cfg["thresholds"] = {}
            if self._device_id not in cfg["thresholds"]:
                cfg["thresholds"][self._device_id] = {}
            cfg["thresholds"][self._device_id]["threshold_pct"] = val
            save_config(cfg)
            self.refresh()

    def refresh(self) -> None:
        """Re-sync history data from config for the selected device."""
        cfg = load_config()
        monitored = cfg.get("monitored_devices", [])
        
        if not monitored:
            self._heading.setText("Battery History")
            self._live_container.setVisible(False)
            self._graph.setVisible(False)
            self._empty_label.setVisible(True)
            self._device_id = None
            self._device_name = None
            return

        # If no device selected, default to the first monitored device
        if self._device_id is None or not any(d["id"] == self._device_id for d in monitored):
            self._device_id = monitored[0]["id"]
            self._device_name = monitored[0]["name"]

        self._graph.setVisible(True)
        self._live_container.setVisible(True)
        self._enable_toggle.setVisible(True)
        self._threshold_btn.setVisible(True)
        self._empty_label.setVisible(False)
        self._heading.setText(f"{self._device_name}")
        
        thresholds = cfg.get("thresholds", {})
        device_cfg = thresholds.get(self._device_id, {})
        current_thr = device_cfg.get("threshold_pct", 15)
        
        self._enable_toggle.blockSignals(True)
        if current_thr is not None:
            self._enable_toggle.setChecked(True)
            self._threshold_btn.setEnabled(True)
            self._threshold_btn.setText(f"Set threshold ({current_thr}%)")
        else:
            self._enable_toggle.setChecked(False)
            self._threshold_btn.setEnabled(False)
            self._threshold_btn.setText("Set threshold")
        self._enable_toggle.blockSignals(False)

        history_data = cfg.get("history", {})
        hist = history_data.get(self._device_id, [])

        # Filter hist by self._active_filter
        filtered_hist = []
        if self._active_filter == "all" or not hist:
            filtered_hist = hist
        else:
            now = datetime.datetime.now()
            hours_map = {
                "1h": 1,
                "4h": 4,
                "24h": 24,
                "7d": 168
            }
            limit_hours = hours_map.get(self._active_filter, 0)
            if limit_hours > 0:
                cutoff = now - datetime.timedelta(hours=limit_hours)
                for entry in hist:
                    try:
                        dt = datetime.datetime.fromisoformat(entry["timestamp"])
                        if dt >= cutoff:
                            filtered_hist.append(entry)
                    except Exception:
                        pass
            else:
                filtered_hist = hist

        self._graph.set_history(filtered_hist, self._active_filter)
