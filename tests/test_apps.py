"""Desktop-app matching for the dock and notch, and launcher search ranking (utils/apps.py)."""

from types import SimpleNamespace

import pytest

from utils.apps import (
    build_identifier_map,
    command_name,
    find_app,
    find_app_by_key,
    fuzzy_match,
    normalize_window_class,
    rank_apps,
    score_app,
)


def _app(name=None, display_name=None, window_class=None, executable=None, command_line=None,
         generic_name=None):
    return SimpleNamespace(name=name, display_name=display_name, window_class=window_class,
                           executable=executable, command_line=command_line,
                           generic_name=generic_name)


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


class TestCommandName:

    @pytest.mark.parametrize("line, expected", [
        ("/usr/bin/firefox %u", "firefox"),
        ("code-oss --unity-launch %F", "code-oss"),
        ("/bin/sh -c 'cd ~ && exec foo'", ""),  # wrapper says nothing about the app
        ("", ""),
        (None, ""),
        ("   ", ""),
    ])
    def test_command_name(self, line, expected):
        assert command_name(line) == expected


class TestFuzzyMatch:

    def test_characters_in_order(self):
        assert fuzzy_match("ffx", "firefox")

    def test_order_matters(self):
        assert not fuzzy_match("xff", "firefox")


class TestScoreApp:
    """Each tier must outrank the next, whatever the name lengths."""

    TERMINAL = _app("org.gnome.Console", "Console", executable="kgx", command_line="kgx",
                    generic_name="Terminal Emulator")

    @pytest.mark.parametrize("query, tier", [
        ("console", 10000),           # exact display name
        ("kgx", 9000),                # exact executable / command
        ("cons", 8000),               # display name prefix
        ("kg", 7000),                 # executable prefix
        ("gnome", 5000),              # word in app name
        ("sol", 4000),                # substring of display name
        ("emulator", 3000),           # substring of generic name
        ("cnsl", 1000),               # fuzzy
    ])
    def test_tier(self, query, tier):
        score = score_app(self.TERMINAL, query)
        assert tier - 1000 < score <= tier

    def test_word_in_display_name(self):
        app = _app(display_name="Image Viewer")
        assert 5000 < score_app(app, "view") <= 6000

    def test_earlier_word_ranks_higher(self):
        app = _app(display_name="Disk Usage Analyzer")
        assert score_app(app, "disk") > score_app(app, "usage") > score_app(app, "analyzer")

    def test_case_insensitive(self):
        assert score_app(self.TERMINAL, "CONSOLE") == 10000

    def test_no_match(self):
        assert score_app(self.TERMINAL, "zzz") == 0


class TestRankApps:

    def test_best_match_first(self):
        files = _app("org.gnome.Nautilus", "Files", executable="nautilus")
        filezilla = _app("filezilla", "FileZilla", executable="filezilla")
        assert rank_apps([filezilla, files], "files") == [files]
        assert rank_apps([filezilla, files], "file") == [files, filezilla]  # shorter first

    def test_ties_sorted_by_name(self):
        b, a = _app(display_name="Beta"), _app(display_name="Alpha")
        assert rank_apps([b, a], "") == [a, b]

    def test_empty_query_keeps_everything(self):
        apps = [_app(display_name=n) for n in ("C", "A", "B")]
        assert [a.display_name for a in rank_apps(apps, "")] == ["A", "B", "C"]

    def test_non_matches_dropped(self):
        assert rank_apps([_app(display_name="Firefox")], "zzz") == []
