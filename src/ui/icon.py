"""VOLT app icon — loaded from assets.
"""
from __future__ import annotations

import os
import sys
from PySide6.QtGui import QIcon

def get_asset_path(filename: str) -> str:
    """Get absolute path to asset, works for dev and for PyInstaller."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        # __file__ is src/ui/icon.py, so base is src/
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'assets', filename)

def make_volt_icon() -> QIcon:
    """Return a QIcon loaded from the physical .ico file."""
    icon_path = get_asset_path("icon.ico")
    return QIcon(icon_path)
