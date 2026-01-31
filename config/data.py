import json
import os
import sys
from pathlib import Path

from .settings_constants import DEFAULTS, APP_NAME

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib  # type: ignore # noqa: E402


CACHE_DIR = str(GLib.get_user_cache_dir()) + f"/{APP_NAME}"

USERNAME = os.getlogin()
HOSTNAME = os.uname().nodename

HOME_DIR = Path().home().resolve()
CONFIG_DIR = HOME_DIR / ".config" / f"{APP_NAME}" / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"

FACE_ICON = HOME_DIR / ".face.icon"
DEFAULT_FACE_ICON = HOME_DIR / ".config" / f"{APP_NAME}" / "assets" / "tanjiro-kamado-red.png"

sys.path.append(str(Path(CONFIG_DIR / "matugen")))

screen = Gdk.Screen.get_default()
CURRENT_WIDTH = screen.get_width()
CURRENT_HEIGHT = screen.get_height()

def load_config():
    """Load the configuration from config.json"""
    config = {}

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")

    return config

# Load configuration once and use throughout the module
""" config = {}
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config file: {e}") """


def get_default(setting_str: str):
    return DEFAULTS[setting_str] if setting_str in DEFAULTS else ""


def _get_config_var(setting_str: str):
    config = load_config()
    return config.get(setting_str, get_default(setting_str))


# Set configuration values using defaults from settings_constants
WALLPAPERS_DIR = _get_config_var("wallpapers_dir")
BAR_POSITION = _get_config_var("bar_position")
VERTICAL = BAR_POSITION in ["Left", "Right"]
CENTERED_BAR = _get_config_var("centered_bar")
DATETIME_12H_FORMAT = _get_config_var("datetime_12h_format")
TERMINAL_COMMAND = _get_config_var("terminal_command")
DOCK_ENABLED = _get_config_var("dock_enabled")
DOCK_ALWAYS_SHOW = _get_config_var("dock_always_show")
DOCK_ICON_SIZE = _get_config_var("dock_icon_size")
BAR_WORKSPACE_SHOW_NUMBER = _get_config_var("bar_workspace_show_number")
BAR_WORKSPACE_USE_CHINESE_NUMERALS = _get_config_var(
    "bar_workspace_use_chinese_numerals"
)
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
