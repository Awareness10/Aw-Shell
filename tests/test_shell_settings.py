"""config.shell_settings against the module-level globals it replaced.

The oracle is the old config/data.py value logic copied verbatim (only the
config dict passed in instead of read at import time)."""

import json

import pytest

import config.shell_settings as shell_settings
from config.settings_constants import DEFAULTS
from config.shell_settings import BAR_COMPONENT_KEYS, Settings, get_default


def old_globals(config, default_terminal_command):
    """config/data.py before wave 3, as a dict of its globals."""

    def get_default(setting_str: str):
        return DEFAULTS[setting_str] if setting_str in DEFAULTS else ""

    def _get_config_var(setting_str: str):
        return config.get(setting_str, get_default(setting_str))

    WALLPAPERS_DIR = _get_config_var("wallpapers_dir")
    BAR_POSITION = _get_config_var("bar_position")
    VERTICAL = BAR_POSITION in ["Left", "Right"]
    CENTERED_BAR = _get_config_var("centered_bar")
    DATETIME_12H_FORMAT = _get_config_var("datetime_12h_format")
    GTK_THEMING = _get_config_var("gtk_theming")
    TERMINAL_COMMAND = (config["terminal_command"] if "terminal_command" in config
                        else default_terminal_command())
    DOCK_ENABLED = _get_config_var("dock_enabled")
    DOCK_ALWAYS_SHOW = _get_config_var("dock_always_show")
    DOCK_ICON_SIZE = _get_config_var("dock_icon_size")
    BAR_WORKSPACE_SHOW_NUMBER = _get_config_var("bar_workspace_show_number")
    BAR_WORKSPACE_USE_RUNES = _get_config_var("bar_workspace_use_runes")
    BAR_HIDE_SPECIAL_WORKSPACE = _get_config_var("bar_hide_special_workspace")
    BAR_THEME = _get_config_var("bar_theme")
    DOCK_THEME = _get_config_var("dock_theme")
    PANEL_THEME = _get_config_var("panel_theme")
    PANEL_POSITION = _get_config_var("panel_position")
    NOTIF_POS = _get_config_var("notif_pos")

    BAR_COMPONENTS_VISIBILITY = {
        "button_apps": _get_config_var("bar_button_apps_visible"),
        "systray": _get_config_var("bar_systray_visible"),
        "control": _get_config_var("bar_control_visible"),
        "network": _get_config_var("bar_network_visible"),
        "button_tools": _get_config_var("bar_button_tools_visible"),
        "sysprofiles": _get_config_var("bar_sysprofiles_visible"),
        "button_overview": _get_config_var("bar_button_overview_visible"),
        "ws_container": _get_config_var("bar_ws_container_visible"),
        "weather": _get_config_var("bar_weather_visible"),
        "battery": _get_config_var("bar_battery_visible"),
        "metrics": _get_config_var("bar_metrics_visible"),
        "language": _get_config_var("bar_language_visible"),
        "date_time": _get_config_var("bar_date_time_visible"),
        "button_power": _get_config_var("bar_button_power_visible"),
    }

    BAR_METRICS_DISKS = _get_config_var("bar_metrics_disks")
    METRICS_VISIBLE = _get_config_var("metrics_visible")
    METRICS_SMALL_VISIBLE = _get_config_var("metrics_small_visible")
    SELECTED_MONITORS = _get_config_var("selected_monitors")
    # main.py read these two from the config dict itself
    MAIN_SELECTED_MONITORS = config.get("selected_monitors", [])
    MAIN_CORNERS_VISIBLE = config.get("corners_visible", True)
    return {k: v for k, v in locals().items() if k.isupper()}


def new_globals(s: Settings) -> dict:
    """The same names read from a Settings object."""
    names = {
        name: getattr(s, name.lower())
        for name in old_globals({}, lambda: "")
        if not name.startswith("MAIN_")
    }
    names["MAIN_SELECTED_MONITORS"] = s.selected_monitors
    names["MAIN_CORNERS_VISIBLE"] = s.corners_visible
    return names


def _flipped(value):
    """A non-default value of the same kind."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 7
    if isinstance(value, str):
        return value + "-x"
    if isinstance(value, list):
        return [*value, "extra"]
    if isinstance(value, dict):
        return {k: not v if isinstance(v, bool) else v for k, v in value.items()}
    return value


CONFIGS = {
    "empty": {},
    "every-key-changed": {key: _flipped(value) for key, value in DEFAULTS.items()}
    | {"terminal_command": "foot -e"},
    "left-bar": {"bar_position": "Left", "panel_theme": "Panel"},
    "right-bar": {"bar_position": "Right"},
    "bottom-bar-12h": {"bar_position": "Bottom", "datetime_12h_format": True},
    "unknown-keys": {"no_such_setting": 1, "bar_battery_visible": False},
    "empty-terminal": {"terminal_command": ""},
    "monitors": {"selected_monitors": ["DP-3"], "corners_visible": False},
}


@pytest.mark.parametrize("name", list(CONFIGS))
def test_matches_old_globals(name, monkeypatch):
    config = CONFIGS[name]
    detect = lambda: "detected-term -e"  # noqa: E731
    monkeypatch.setattr(shell_settings, "default_terminal_command", detect)
    assert new_globals(Settings.from_config(config)) == old_globals(config, detect)


def test_vertical_follows_bar_position(monkeypatch):
    s = Settings.from_config({"bar_position": "Top"})
    assert not s.vertical
    monkeypatch.setattr(s, "bar_position", "Right")
    assert s.vertical


def test_every_bar_component_key_has_a_default():
    assert all(key in DEFAULTS for key in BAR_COMPONENT_KEYS.values())


def test_get_default_of_unknown_setting_is_empty_string():
    assert get_default("no_such_setting") == ""


def test_read_config_file(monkeypatch, tmp_path, logs):
    path = tmp_path / "config.json"
    monkeypatch.setattr(shell_settings, "CONFIG_FILE", path)
    assert shell_settings.read_config_file() == {}
    path.write_text(json.dumps({"bar_position": "Left"}))
    assert shell_settings.read_config_file() == {"bar_position": "Left"}
    path.write_text("{not json")
    assert shell_settings.read_config_file() == {}
    assert any("Error loading config" in m for m in logs)
