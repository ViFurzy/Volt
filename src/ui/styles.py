"""Global QSS dark stylesheet for PeriphWatcher.

VOLT | POWER CENTER dark theme tokens:
  background:  #202535
  elevated:    #262355
  text:        #FFFFFF
  accent:      #4FC3F7  (teal highlight for active sidebar item)
  hover:       #2a2d45
  scrollbar:   #3a3d55
"""

DARK_QSS: str = """
QWidget {
    background-color: #202535;
    color: #FFFFFF;
}
QMainWindow {
    background-color: #202535;
}
QPushButton {
    background-color: transparent;
    color: #FFFFFF;
    border: none;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
}
QPushButton:checked {
    background-color: #262355;
    border-left: 3px solid #4FC3F7;
}
QPushButton:hover:!checked {
    background-color: #2a2d45;
}
QScrollBar:vertical {
    background-color: #202535;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #3a3d55;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: #202535;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #3a3d55;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}
QLabel {
    background-color: transparent;
    color: #FFFFFF;
}
QCheckBox {
    color: #FFFFFF;
    spacing: 8px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a3d55;
    border-radius: 3px;
    background-color: #202535;
}
QCheckBox::indicator:checked {
    background-color: #4FC3F7;
    border-color: #4FC3F7;
}
QMenu {
    background-color: #262355;
    color: #FFFFFF;
    border: 1px solid #3a3d55;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 20px;
}
QMenu::item:selected {
    background-color: #2a2d45;
}
QMenu::separator {
    height: 1px;
    background-color: #3a3d55;
    margin: 4px 0;
}
QScrollArea {
    border: none;
    background-color: #202535;
}
QFrame#deviceCard {
    background-color: #262355;
    border-radius: 8px;
    border: 1px solid #3a3d55;
}
QFrame#deviceCard[offline="true"] {
    background-color: #1e2030;
    border-color: #2a2d45;
    /* opacity is not a valid QSS property — dimming applied via QGraphicsOpacityEffect in device_card.py */
}
"""
