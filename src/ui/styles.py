"""Global QSS stylesheet — VOLT | POWER CENTER dark theme.

Color tokens:
  root bg:      #1a1a1f
  surface:      #202026  (sidebar, cards)
  elevated:     #282366  (active nav, panels)
  accent blue:  #7B9FFF  (active nav text, Volt title, left bar)
  accent amber: #E89000  (primary buttons, toggle on)
  batt warn:    #F0BB66  (≤45%)
  batt crit:    #EE6800  (≤8%)
  text primary: #FFFFFF
  text muted:   #888899
"""

DARK_QSS: str = """
QMainWindow, QWidget {
    background-color: #1a1a1f;
    color: #FFFFFF;
    font-family: "Segoe UI", "Inter", sans-serif;
}

/* ── Sidebar ─────────────────────────────────────────────── */
#sidebar {
    background-color: #202026;
    border-right: 1px solid #25252f;
}
#sidebarHeader {
    background-color: #202026;
}
#voltTitle {
    color: #7B9FFF;
    font-size: 22px;
    font-weight: bold;
    background-color: transparent;
}
#voltSubtitle {
    color: #888899;
    font-size: 9px;
    letter-spacing: 3px;
    background-color: transparent;
}
QPushButton#navButton {
    background-color: transparent;
    color: #AAAACC;
    border: none;
    border-left: 3px solid transparent;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    border-radius: 0px;
}
QPushButton#navButton:checked {
    background-color: #282366;
    color: #7B9FFF;
    border-left: 3px solid #7B9FFF;
    font-weight: bold;
}
QPushButton#navButton:hover:!checked {
    background-color: #25253a;
    color: #DDDDFF;
}
QPushButton#deviceSubItem {
    background-color: transparent;
    color: #888899;
    border: none;
    border-left: 3px solid transparent;
    padding: 5px 16px 5px 40px;
    text-align: left;
    font-size: 12px;
    border-radius: 0px;
}
QPushButton#deviceSubItem:checked {
    background-color: #282366;
    color: #7B9FFF;
    border-left: 3px solid #7B9FFF;
    font-weight: bold;
}
QPushButton#deviceSubItem:hover:!checked {
    color: #AAAACC;
    background-color: #22222e;
}
#sidebarSep {
    background-color: #25252f;
    max-height: 1px;
    border: none;
}

/* ── Dashboard ───────────────────────────────────────────── */
#dashboardHeader {
    color: #FFFFFF;
    font-size: 18px;
    font-weight: bold;
    background-color: transparent;
    padding: 4px 0;
}

/* ── Device card ─────────────────────────────────────────── */
QFrame#deviceCard {
    background-color: #202026;
    border-radius: 14px;
    border: 1px solid #2a2a38;
}
QFrame#deviceCard[offline="true"] {
    border-color: #202026;
}

/* ── Scroll bars ─────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #1a1a1f;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #3a3a55;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background-color: #1a1a1f;
    height: 6px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #3a3a55;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollArea { border: none; background-color: transparent; }

/* ── Generic widgets ─────────────────────────────────────── */
QLabel { background-color: transparent; color: #FFFFFF; }

QCheckBox {
    color: #AAAACC;
    spacing: 8px;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a3a55;
    border-radius: 3px;
    background-color: #202026;
}
QCheckBox::indicator:checked {
    background-color: #E89000;
    border-color: #E89000;
}

QMenu {
    background-color: #202026;
    color: #FFFFFF;
    border: 1px solid #2a2a38;
    padding: 4px 0;
}
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background-color: #282366; }
QMenu::separator { height: 1px; background-color: #2a2a38; margin: 4px 0; }

/* ── Devices page panels ─────────────────────────────────── */
#devicePanel {
    background-color: #202026;
    border: 1px solid #25252f;
    border-radius: 8px;
}

QListWidget {
    background-color: #1a1a1f;
    border: 1px solid #25252f;
    border-radius: 4px;
    color: #CCCCDD;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 3px;
}
QListWidget::item:selected {
    background-color: #282366;
    color: #7B9FFF;
}
QListWidget::item:hover:!selected {
    background-color: #22222e;
}
"""
