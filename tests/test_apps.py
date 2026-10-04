"""Matching Hyprland windows and pinned entries to desktop apps (utils/apps.py)."""

from types import SimpleNamespace

import pytest

from utils.apps import build_identifier_map, find_app, find_app_by_key, normalize_window_class


def _app(name=None, display_name=None, window_class=None, executable=None, command_line=None):
    return SimpleNamespace(name=name, display_name=display_name, window_class=window_class,
                           executable=executable, command_line=command_line)


FIREFOX = _app("firefox", "Firefox", "firefox", "/usr/lib/firefox/firefox",
               "/usr/lib/firefox/firefox %u")
CODE = _app("code-oss", "Code - OSS", "code-oss", "/usr/bin/code-oss", "code-oss --unity-launch %F")
FILES = _app("org.gnome.Nautilus", "Files", None, "nautilus", "nautilus --new-window %U")
APPS = [FIREFOX, CODE, FILES]


@pytest.fixture
def identifiers():
    return build_identifier_map(APPS)


class TestIdentifierMap:

    def test_every_identifier_is_lowercased(self, identifiers):
        assert identifiers["org.gnome.nautilus"] is FILES
        assert identifiers["files"] is FILES
        assert identifiers["code - oss"] is CODE

    def test_paths_reduce_to_basename(self, identifiers):
        assert identifiers["firefox"] is FIREFOX
        assert identifiers["nautilus"] is FILES
        assert "/usr/bin/code-oss" not in identifiers

    def test_command_line_arguments_dropped(self, identifiers):
        assert "nautilus --new-window %u" not in identifiers
        assert identifiers["code-oss"] is CODE

    def test_missing_fields_and_blank_command_skipped(self):
        bare = _app(name="bare", command_line="   ")
        assert build_identifier_map([bare]) == {"bare": bare}

    def test_later_app_wins_collision(self):
        first, second = _app(name="term"), _app(name="Term")
        assert build_identifier_map([first, second])["term"] is second


class TestNormalizeWindowClass:

    @pytest.mark.parametrize("raw, expected", [
        ("Firefox", "firefox"),
        ("steam.bin", "steam"),
        ("game.exe", "game"),
        ("libfoo.so", "libfoo"),
        ("blender-bin", "blender"),
        ("pavucontrol-gtk", "pavucontrol"),
        ("", ""),
        (None, ""),
    ])
    def test_normalize(self, raw, expected):
        assert normalize_window_class(raw) == expected


class TestFindApp:

    def test_exact_identifier_case_insensitive(self, identifiers):
        assert find_app_by_key("FIREFOX", identifiers, APPS) is FIREFOX

    def test_substring_fallback(self, identifiers):
        assert find_app_by_key("nautil", identifiers, APPS) is FILES

    def test_no_match(self, identifiers):
        assert find_app_by_key("gimp", identifiers, APPS) is None

    @pytest.mark.parametrize("empty", [None, "", {}])
    def test_empty_identifier(self, identifiers, empty):
        assert find_app(empty, identifiers, APPS) is None

    def test_pinned_dict_tries_window_class_first(self, identifiers):
        pinned = {"window_class": "code-oss", "name": "firefox"}
        assert find_app(pinned, identifiers, APPS) is CODE

    def test_pinned_dict_falls_back_to_later_fields(self, identifiers):
        pinned = {"window_class": "", "executable": "gimp", "name": "Files"}
        assert find_app(pinned, identifiers, APPS) is FILES

    def test_pinned_dict_without_match(self, identifiers):
        assert find_app({"name": "gimp"}, identifiers, APPS) is None

    def test_string_identifier(self, identifiers):
        assert find_app("code-oss", identifiers, APPS) is CODE
