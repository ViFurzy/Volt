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
    font-size: 17pt;
    font-weight: bold;
    background-color: transparent;
}
#voltSubtitle {
    color: #888899;
    font-size: 7pt;
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
    font-size: 10pt;
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
    font-size: 9pt;
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

QPushButton#sidebarVersionBtn {
    font-size: 8pt;
    color: #555566;
    padding-left: 16px;
    padding-right: 16px;
    padding-top: 0px;
    padding-bottom: 0px;
    margin: 0;
    background: transparent;
    text-align: left;
    border: none;
}
QPushButton#sidebarVersionBtn:hover {
    color: #7B9FFF;
    text-decoration: underline;
}
QPushButton#sidebarVersionBtn[update_available="true"] {
    color: #E89000;
    font-weight: bold;
}
QPushButton#sidebarVersionBtn[update_available="true"]:hover {
    color: #FFB033;
}

QPushButton#updBtn {
    background-color: #202026;
    border: 1px solid #3a3a55;
    border-radius: 4px;
    padding: 6px 12px;
    color: #FFFFFF;
    font-size: 10pt;
}
QPushButton#updBtn:hover {
    border-color: #7B9FFF;
    background-color: #25253a;
}
QPushButton#updBtn:disabled {
    color: #888899;
    border-color: #25252f;
    background-color: #1c1c22;
}
QPushButton#updBtn[update_available="true"] {
    background-color: #E89000;
    border-color: #E89000;
    color: #FFFFFF;
    font-weight: bold;
}
QPushButton#updBtn[update_available="true"]:hover {
    background-color: #FFB033;
    border-color: #FFB033;
}

/* ── Dashboard ───────────────────────────────────────────── */
#dashboardHeader {
    color: #FFFFFF;
    font-size: 14pt;
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
    font-size: 10pt;
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
    font-size: 9pt;
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

/* ── QTabWidget & QTabBar ────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #2a2a38;
    background-color: #202026;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #1a1a1f;
    border: 1px solid #2a2a38;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    color: #888899;
    font-size: 10pt;
    font-weight: bold;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background-color: #202026;
    color: #7B9FFF;
    border-color: #2a2a38;
    border-top: 2px solid #7B9FFF;
}
QTabBar::tab:hover:!selected {
    background-color: #25252f;
    color: #CCCCDD;
}

/* ── QComboBox ───────────────────────────────────────────── */
QComboBox {
    background-color: #202026;
    border: 1px solid #3a3a55;
    border-radius: 4px;
    padding: 4px 10px;
    color: #FFFFFF;
    font-size: 10pt;
    min-width: 120px;
}
QComboBox:hover {
    border-color: #7B9FFF;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: none;
}
QComboBox QAbstractItemView {
    background-color: #202026;
    border: 1px solid #3a3a55;
    selection-background-color: #282366;
    selection-color: #7B9FFF;
    color: #FFFFFF;
    outline: none;
}
"""


def build_qss() -> str:
    """DARK_QSS remapped to the active UI style (see ui.theme)."""
    from ui import theme
    return theme.themed(DARK_QSS).replace('"Segoe UI", "Inter", sans-serif', theme.font())


_patched = False


def _load_fonts() -> None:
    """Register the bundled Geist / Doto / Space Mono fonts (src/assets/fonts)."""
    from pathlib import Path
    from PySide6.QtGui import QFontDatabase
    for f in (Path(__file__).resolve().parent.parent / "assets" / "fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


def apply_style(app) -> None:
    """Apply the active UI style to `app` and every widget with an inline stylesheet.

    Inline setStyleSheet() calls hardcode legacy colours, so QWidget.setStyleSheet is
    wrapped once: it keeps the raw text and re-themes it, which lets a style switch
    re-apply all of them without touching each call site.
    """
    global _patched
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QWidget
    from ui import theme
    if not _patched:
        orig = QWidget.setStyleSheet

        def set_style_sheet(self, qss):
            self._raw_qss = qss
            orig(self, theme.themed(qss))

        QWidget.setStyleSheet = set_style_sheet
        _patched = True
        _load_fonts()
    # Subpixel AA leaves coloured fringes on dot glyphs over the translucent widget
    f = app.font()
    f.setStyleStrategy(QFont.StyleStrategy.NoSubpixelAntialias)
    app.setFont(f)
    app.setStyleSheet(build_qss())
    for w in app.allWidgets():
        raw = getattr(w, "_raw_qss", None)
        if raw is not None:
            w.setStyleSheet(raw)
        w.update()  # custom paintEvents read theme colours

