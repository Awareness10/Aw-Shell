"""GTK apps follow aw-shell's matugen colors through ~/.config/gtk-*/gtk.css."""

import json
import os

import pytest

from config import gtk_theme

COLORS = {
    "primary": "#bdc2ff", "on_primary": "#262b60",
    "error": "#ffb4ab", "on_error": "#690005",
    "on_surface": "#e4e1e9", "outline_variant": "#46464f",
    "surface_container_lowest": "#0e0e13", "surface_container_low": "#1b1b21",
    "surface_container": "#1f1f25",
    "green": "#9ad48f", "yellow": "#e3c46d",
}


@pytest.fixture
def home(tmp_path):
    (tmp_path / "colors.json").write_text(json.dumps(COLORS))
    return tmp_path


def _sync(home, enabled=True):
    return gtk_theme.sync_gtk_theme(enabled, home / "colors.json", home / "config")


def _css(home, version):
    return (home / "config" / f"gtk-{version}.0" / "gtk.css")


def test_dark_mode_is_oled_black_with_matugen_accents():
    palette = gtk_theme.gtk_palette(COLORS)
    assert palette["window_bg_color"] == "#000000"
    assert palette["view_bg_color"] == "#000000"
    assert palette["accent_bg_color"] == "#bdc2ff"
    assert palette["accent_fg_color"] == "#262b60"
    assert palette["card_bg_color"] == "#1b1b21"
    assert palette["success_bg_color"] == "#9ad48f"


def test_missing_custom_colors_fall_back_to_libadwaita():
    colors = {k: v for k, v in COLORS.items() if k not in ("green", "yellow")}
    palette = gtk_theme.gtk_palette(colors)
    assert palette["success_bg_color"].startswith("#")
    assert palette["warning_bg_color"].startswith("#")


def test_gtk3_css_only_uses_named_colors():
    # GTK 3 has no CSS variables: a :root rule would warn in every app
    css = gtk_theme.render_gtk3_css(COLORS)
    assert "@define-color window_bg_color #000000;" in css
    assert ":root" not in css and "var(" not in css


def test_gtk4_css_sets_libadwaita_variables_too():
    css = gtk_theme.render_gtk4_css(COLORS)
    assert "--window-bg-color: #000000;" in css
    assert "@define-color window_bg_color #000000;" in css


def test_writes_both_files(home):
    assert _sync(home) is True
    assert _css(home, 3).read_text().startswith(gtk_theme.MARKER)
    assert "--accent-bg-color" in _css(home, 4).read_text()


def test_unchanged_colors_report_no_change(home):
    _sync(home)
    assert _sync(home) is False


def test_backs_up_a_user_file_and_restores_it_when_disabled(home):
    css = _css(home, 3)
    css.parent.mkdir(parents=True)
    css.write_text("/* mine */")
    _sync(home)
    assert css.read_text().startswith(gtk_theme.MARKER)
    assert _sync(home, enabled=False) is True
    assert css.read_text() == "/* mine */"
    assert not css.with_name(css.name + gtk_theme.BACKUP_SUFFIX).exists()


def test_replaces_a_symlink_without_writing_through_it(home, tmp_path):
    target = tmp_path / "theme.css"
    target.write_text("theme")
    css = _css(home, 4)
    css.parent.mkdir(parents=True)
    css.symlink_to(target)
    _sync(home)
    assert target.read_text() == "theme"
    assert not css.is_symlink()
    _sync(home, enabled=False)
    assert css.is_symlink() and os.readlink(css) == str(target)


def test_leaves_a_user_file_alone_when_a_backup_already_exists(home):
    css = _css(home, 3)
    css.parent.mkdir(parents=True)
    css.write_text("/* new */")
    css.with_name(css.name + gtk_theme.BACKUP_SUFFIX).write_text("/* old */")
    _sync(home)
    assert css.read_text() == "/* new */"


def test_disabled_without_our_files_changes_nothing(home):
    assert _sync(home, enabled=False) is False
    assert not (home / "config" / "gtk-3.0").exists()


def test_no_colors_yet_writes_nothing(tmp_path):
    assert gtk_theme.sync_gtk_theme(True, tmp_path / "none.json", tmp_path) is False
    assert not (tmp_path / "gtk-3.0").exists()
