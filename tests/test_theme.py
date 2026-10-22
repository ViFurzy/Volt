"""Tests for ui.theme and styles.build_qss."""
import pytest

from ui import theme
from ui.styles import DARK_QSS, build_qss


@pytest.fixture(autouse=True)
def _restore_theme():
    prev = theme.current()
    yield
    theme.set_theme(prev)


def test_unknown_theme_falls_back_to_default():
    assert theme.set_theme("nope") == theme.DEFAULT_THEME


def test_themed_remaps_known_colours_only():
    theme.set_theme("dotmatrix")
    assert theme.themed("color: #7B9FFF; x: #123456") == "color: #FF5A1F; x: #123456"


def test_build_qss_has_no_legacy_accent_in_either_theme():
    for name in theme.THEMES:
        theme.set_theme(name)
        assert "#7B9FFF" not in build_qss().upper()
    assert "#7B9FFF" in DARK_QSS.upper()


def test_build_qss_uses_theme_font():
    theme.set_theme("dotmatrix")
    assert "Space Mono" in build_qss()
