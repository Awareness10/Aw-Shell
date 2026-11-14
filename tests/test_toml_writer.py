"""config/toml_writer.py: what it writes, tomllib reads back unchanged."""

import datetime
import math
import tomllib

import pytest

from config.toml_writer import dumps

# The shape ensure_matugen_config writes (config/settings_utils.py)
MATUGEN = {
    "config": {
        "reload_apps": True,
        "wallpaper": {
            "command": "awww",
            "arguments": ["img", "-t", "fade", "--transition-duration", "0.5", "-f", "Nearest"],
            "set": True,
        },
        "custom_colors": {
            "red": {"color": "#FF0000", "blend": True},
            "white": {"color": "#FFFFFF", "blend": False},
        },
    },
    "templates": {
        "hyprland-lua": {
            "input_path": "/usr/share/aw-shell/templates/hyprland-colors.lua",
            "output_path": "/home/user/.config/aw-shell/config/hypr/colors.lua",
            "post_hook": "hyprctl eval 'aw_shell_apply_colors()' &",
        },
        "aw-shell": {
            "input_path": "/opt/aw shell/aw-shell.css",
            "output_path": "/home/user/.config/aw-shell/styles/colors.css",
            "post_hook": "fabric-cli exec aw-shell 'app.set_css()' &",
        },
    },
}


def round_trip(data):
    return tomllib.loads(dumps(data))


def test_matugen_config_round_trips():
    assert round_trip(MATUGEN) == MATUGEN


def test_matugen_config_layout():
    text = dumps(MATUGEN)
    assert text.startswith("[config]\nreload_apps = true\n")
    assert "\n[config.wallpaper]\n" in text
    assert "\n[config.custom_colors.red]\ncolor = \"#FF0000\"\nblend = true\n" in text
    assert "[config.custom_colors]\n" not in text  # only sub-tables: no empty header
    assert "\n[templates.hyprland-lua]\n" in text
    assert text.endswith("\n") and not text.endswith("\n\n")


@pytest.mark.parametrize("text", [
    'say "hi"', "back\\slash", "C:\\path\\", "line\nbreak\r\n", "tab\there",
    "bell\x07 esc\x1b del\x7f nul\x00", "unicode ✓ 😀 ø", "'single' quotes", "", "#not a comment",
    "trailing \\",
])
def test_strings_are_escaped(text):
    assert round_trip({"s": text, "t": {"s": text}}) == {"s": text, "t": {"s": text}}


@pytest.mark.parametrize("key", [
    "plain_key", "with-dash", "123", "has space", "dotted.key", 'quo"te', "ø", "",
])
def test_keys_are_quoted_when_needed(key):
    data = {key: "v", "table": {key: {key: True}}}
    assert round_trip(data) == data


def test_bare_keys_stay_bare():
    assert dumps({"a-b_1": {"c": 1}}) == "[a-b_1]\nc = 1\n"


def test_values_a_user_file_may_hold():
    """Whatever tomllib read from the user's file is written back."""
    data = {
        "title": "mine",
        "count": 3,
        "negative": -7,
        "big": 2**62,
        "ratio": 0.5,
        "tiny": 1e-300,
        "huge": 1.5e300,
        "off": False,
        "empty_list": [],
        "numbers": [1, 2, 3],
        "nested": [[1, 2], ["a", "b"]],
        "mixed": [1, "two", 3.0, True],
        "inline": [{"name": "a", "deep": {"x": 1}}, 4],
        "when": datetime.datetime(1979, 5, 27, 7, 32, tzinfo=datetime.timezone.utc),
        "local": datetime.datetime(1979, 5, 27, 7, 32, 0, 999000),
        "day": datetime.date(1979, 5, 27),
        "time": datetime.time(7, 32),
        "empty_table": {},
        "server": {"alpha": {"ip": "10.0.0.1"}, "beta": {}},
        "products": [
            {"name": "Hammer", "sku": 738594937},
            {},
            {"name": "Nail", "color": {"value": "gray"}, "parts": [{"n": 1}, {"n": 2}]},
        ],
    }
    assert round_trip(data) == data


def test_special_floats():
    result = round_trip({"inf": math.inf, "ninf": -math.inf, "nan": math.nan})
    assert result["inf"] == math.inf and result["ninf"] == -math.inf
    assert math.isnan(result["nan"])


def test_float_stays_a_float():
    assert round_trip({"x": 1.0, "y": 1e20}) == {"x": 1.0, "y": 1e20}
    assert isinstance(round_trip({"x": 1.0})["x"], float)


def test_empty_document():
    assert dumps({}) == ""


def test_unknown_types_raise():
    with pytest.raises(TypeError):
        dumps({"x": object()})
    with pytest.raises(TypeError):
        dumps({"x": None})


def test_user_file_survives_read_merge_write():
    """A file in the toml package's old output style reads, and writes back
    with its own keys intact."""
    old_style = (
        '[config]\nreload_apps = true\n\n[config.wallpaper]\ncommand = "awww"\n'
        'arguments = [ "img", "-t", "fade",]\nset = true\n\n'
        '[templates.mine]\ninput_path = "~/in"\noutput_path = "~/out"\n\n'
        '[config.custom_colors.red]\ncolor = "#FF0000"\nblend = true\n'
    )
    data = tomllib.loads(old_style)
    assert round_trip(data) == data
