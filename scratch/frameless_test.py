import sys
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton

class FramelessWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(400, 300)
        self.setStyleSheet("background: #222; color: white;")
        
        btn = QPushButton("Close")
        btn.clicked.connect(self.close)
        
        layout = QVBoxLayout()
        layout.addWidget(btn)
        
        w = QWidget()
        w.setLayout(layout)
        self.setCentralWidget(w)
        
        self._drag_pos = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        event.accept()

    def nativeEvent(self, eventType, message):
        retval, result = super().nativeEvent(eventType, message)
        if sys.platform != "win32":
            return retval, result
            
        import ctypes.wintypes
        msg = ctypes.wintypes.MSG.from_address(message.__int__())
        if msg.message == 0x0084: # WM_NCHITTEST
            x = msg.lParam & 0xffff
            if x > 32767: x -= 65536
            y = (msg.lParam >> 16) & 0xffff
            if y > 32767: y -= 65536
            
            pos = self.mapFromGlobal(QPoint(x, y))
            margin = 8
            w, h = self.width(), self.height()
            
            on_right = pos.x() > w - margin
            on_bottom = pos.y() > h - margin
            
            if on_bottom and on_right:
                return True, 17 # HTBOTTOMRIGHT
            if on_right:
                return True, 11 # HTRIGHT
            if on_bottom:
                return True, 15 # HTBOTTOM
                
        return retval, result

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FramelessWindow()
    w.show()
    sys.exit(app.exec())
