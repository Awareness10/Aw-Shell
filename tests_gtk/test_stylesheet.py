"""The real stylesheet compiles with fabric and loads into GTK, whether the
colors come from the shipped defaults or the user's folder."""

import pytest
from fabric.utils.helpers import compile_css
from gi.repository import Gtk

import config.paths as paths
from utils.stylesheet import build_stylesheet


@pytest.fixture
def styles(tmp_path, monkeypatch):
    styles = tmp_path / "styles"
    styles.mkdir()
    monkeypatch.setattr(paths, "CSS_COLORS", styles / "colors.css")
    monkeypatch.setattr(paths, "USER_CSS", styles / "user.css")
    return styles


def _compile_and_load(css: str) -> tuple[str, list[str]]:
    compiled = compile_css(css, base_path=str(paths.APP_DIR))
    errors = []
    provider = Gtk.CssProvider()
    provider.connect("parsing-error", lambda _p, _section, err: errors.append(err.message))
    provider.load_from_data(compiled.encode())
    return compiled, errors


def test_loads_with_default_colors(styles):
    compiled, errors = _compile_and_load(build_stylesheet())
    assert "couldn't import" not in compiled
    assert "@define-color primary #" in compiled
    assert errors == []


def test_user_colors_and_user_css_win(styles):
    default = paths.DEFAULT_CSS_COLORS.read_text()
    custom = default.replace("--primary:", "--primary: #123456; --old-primary:", 1)
    (styles / "colors.css").write_text(custom)
    (styles / "user.css").write_text("#bar-inner { margin: 7px; }\n")
    compiled, errors = _compile_and_load(build_stylesheet())
    assert "@define-color primary #123456;" in compiled
    assert compiled.rstrip().endswith("#bar-inner { margin: 7px; }")
    assert errors == []
