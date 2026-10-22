"""UI style selection (Inspector / Dot matrix).

The app's QSS and inline styles were written against one palette (the keys of
each theme's "map"). A theme is a remap of those colours plus a font stack, so
existing stylesheet text stays readable and a style switch is one substitution.

No Qt imports so it can be tested headlessly.
"""
from __future__ import annotations

import re

INSPECTOR = {
    "name": "Inspector",
    "font": '"Geist", "Segoe UI", "Inter", sans-serif',
    "map": {
        "#1A1A1F": "#0E0F12",  # window bg
        "#202026": "#15171B",  # surface (sidebar, cards)
        "#25252F": "#23262D",  # soft border
        "#2A2A38": "#2A2D35",  # border
        "#3A3A55": "#3A3E48",  # strong border
        "#282366": "#222B0A",  # active nav / selection bg
        "#25253A": "#1B1D22",  # hover bg
        "#22222E": "#1B1D22",
        "#7B9FFF": "#C8FF2E",  # primary accent
        "#92AEFF": "#DAFF6B",
        "#E89000": "#C8FF2E",  # primary button
        "#FFB033": "#DAFF6B",
        "#AAAACC": "#A7ADB8",  # secondary text
        "#CCCCDD": "#C9CDD5",
        "#DDDDFF": "#E8EAEE",
        "#888899": "#8A909B",  # muted text
        "#555566": "#5F6671",  # dim text / offline
        "#444455": "#454A54",
        "#4CAF50": "#C8FF2E",  # battery good
        "#F0BB66": "#FFA31A",  # battery warning
        "#EE6800": "#FF5A3C",  # battery critical
        "#4FC3F7": "#5FD0FF",  # charging
        "#1E1E28": "#1B1D22",  # widget tile bg
        "#14141D": "#0E0F12",  # widget bar track
        "#121218": "#0E0F12",  # widget list row bg
        "#2A2A3A": "#2A2D35",  # widget track / border
        "#666677": "#6B717C",
    },
}

DOTMATRIX = {
    "name": "Dot matrix",
    "font": '"Space Mono", "Consolas", monospace',
    "display_font": "Doto",
    "map": {
        "#1A1A1F": "#000000",
        "#202026": "#0A0A0A",
        "#25252F": "#2A2A2A",
        "#2A2A38": "#2A2A2A",
        "#3A3A55": "#444444",
        "#282366": "#1C0F0A",
        "#25253A": "#111111",
        "#22222E": "#111111",
        "#7B9FFF": "#FF5A1F",
        "#92AEFF": "#FF7A45",
        "#E89000": "#FF5A1F",
        "#FFB033": "#FF7A45",
        "#AAAACC": "#AAAAAA",
        "#CCCCDD": "#CCCCCC",
        "#DDDDFF": "#F2F2F2",
        "#888899": "#8A8A8A",
        "#555566": "#666666",
        "#444455": "#555555",
        "#4CAF50": "#F2F2F2",  # good battery is white; orange is reserved for low
        "#F0BB66": "#FF5A1F",
        "#EE6800": "#FF5A1F",
        "#4FC3F7": "#F2F2F2",
        "#1E1E28": "#0A0A0A",
        "#14141D": "#1F1F1F",
        "#121218": "#000000",
        "#2A2A3A": "#2A2A2A",
        "#666677": "#666666",
    },
}

THEMES = {"inspector": INSPECTOR, "dotmatrix": DOTMATRIX}
DEFAULT_THEME = "inspector"

_current = DEFAULT_THEME
_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def current() -> str:
    return _current


def set_theme(name: str) -> str:
    """Select a theme; unknown names fall back to the default. Returns the name used."""
    global _current
    _current = name if name in THEMES else DEFAULT_THEME
    return _current


def themed(text: str) -> str:
    """Remap every known legacy colour in `text` to the current theme."""
    m = THEMES[_current]["map"]
    return _HEX.sub(lambda h: m.get(h.group(0).upper(), h.group(0)), text)


def c(legacy_hex: str) -> str:
    """Themed equivalent of one legacy colour, for inline styles and QColor()."""
    return THEMES[_current]["map"].get(legacy_hex.upper(), legacy_hex)


def font() -> str:
    return THEMES[_current]["font"]


def family() -> str:
    """First family of the body font stack, unquoted (for QFont)."""
    return THEMES[_current]["font"].split(",")[0].strip('" ')


def is_dots() -> bool:
    """True for the dot-matrix style: square corners, dots instead of bars, Doto numerals."""
    return _current == "dotmatrix"


def display_font() -> str:
    """Family for big numerals."""
    return THEMES[_current].get("display_font", "Geist")


def rgba(legacy_hex: str, alpha: float) -> str:
    """QSS rgba() string for a themed legacy colour."""
    h = c(legacy_hex).lstrip("#")
    return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {alpha})"
