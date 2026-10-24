"""utils/stylesheet.py: the shipped CSS plus the user's colors and overrides."""

import pytest

import config.paths as paths
from utils.stylesheet import build_stylesheet


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    styles = tmp_path / "styles"
    styles.mkdir()
    monkeypatch.setattr(paths, "CSS_COLORS", styles / "colors.css")
    monkeypatch.setattr(paths, "USER_CSS", styles / "user.css")
    return styles


def test_imports_default_colors_until_matugen_ran(user_dir):
    first = build_stylesheet().splitlines()[0]
    assert first == f'@import url("{paths.DEFAULT_CSS_COLORS}");'


def test_imports_the_users_colors(user_dir):
    (user_dir / "colors.css").write_text(":vars {}")
    first = build_stylesheet().splitlines()[0]
    assert first == f'@import url("{user_dir / "colors.css"}");'


def test_contains_main_css_without_a_relative_colors_import(user_dir):
    css = build_stylesheet()
    assert paths.MAIN_CSS.read_text() in css
    assert "./styles/colors.css" not in css


def test_user_css_only_when_present(user_dir):
    assert "user.css" not in build_stylesheet()
    (user_dir / "user.css").write_text("#bar { color: red; }")
    last = build_stylesheet().splitlines()[-1]
    assert last == f'@import url("{user_dir / "user.css"}");'  # last, so it overrides


def test_default_colors_ship_with_the_code():
    text = paths.DEFAULT_CSS_COLORS.read_text()
    assert ":vars {" in text and "--primary:" in text
    assert "{{" not in text  # fully rendered template
