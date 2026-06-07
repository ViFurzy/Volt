from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QFrame,
    QSlider
)

class ThresholdDialog(QDialog):
    """Custom frameless dialog for setting the warning threshold."""
    
    def __init__(self, current_val: int, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 170)
        self._drag_pos = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main container with border and rounded corners
        self.container = QFrame()
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QFrame#container {
                background-color: #202026;
                border: 1px solid #2a2a38;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(24, 20, 24, 20)
        container_layout.setSpacing(20)
        
        # Header
        title = QLabel("Set Warning Threshold")
        title.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold; font-family: 'Segoe UI';")
        container_layout.addWidget(title)
        
        # Subtext
        subtext = QLabel("Notify me when battery drops below:")
        subtext.setStyleSheet("color: #AAAACC; font-size: 12px; font-family: 'Segoe UI';")
        container_layout.addWidget(subtext)
        
        # Slider & Spinbox
        input_layout = QHBoxLayout()
        input_layout.setSpacing(16)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 99)
        self.slider.setValue(current_val)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border-radius: 2px;
                height: 4px;
                background: #2a2a38;
            }
            QSlider::handle:horizontal {
                background: #7B9FFF;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #92AEFF;
            }
            QSlider::sub-page:horizontal {
                background: #7B9FFF;
                border-radius: 2px;
            }
        """)
        
        self.spin = QSpinBox()
        self.spin.setRange(1, 99)
        self.spin.setValue(current_val)
        self.spin.setSuffix("%")
        self.spin.setFixedSize(60, 30)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setStyleSheet("""
            QSpinBox {
                background-color: #1a1a1f;
                color: #FFFFFF;
                border: 1px solid #2a2a38;
                border-radius: 4px;
                padding: 4px;
                font-family: 'Segoe UI';
                font-weight: bold;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px; /* Hide arrows */
            }
        """)
        
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        
        input_layout.addWidget(self.slider)
        input_layout.addWidget(self.spin)
        container_layout.addLayout(input_layout)
        
        container_layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 30)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #AAAACC;
                border: 1px solid #2a2a38;
                border-radius: 4px;
                font-family: 'Segoe UI';
            }
            QPushButton:hover {
                background-color: #2a2a38;
                color: #FFFFFF;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Save")
        save_btn.setFixedSize(80, 30)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #E89000;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }
            QPushButton:hover {
                background-color: #FFB347;
            }
        """)
        save_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        container_layout.addLayout(btn_layout)
        
        layout.addWidget(self.container)

    def value(self) -> int:
        """Return the chosen percentage."""
        return self.spin.value()

    # Allow dragging the dialog
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        event.accept()
