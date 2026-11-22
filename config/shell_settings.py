"""The shell's settings: config.json over the defaults in settings_constants.

Read once, when this is first imported. Applying settings restarts the shell,
so a running shell never sees them change.

    from config.shell_settings import settings
    if settings.vertical: ...

Tests change one with monkeypatch.setattr(settings, "bar_position", "Left");
`vertical` follows bar_position.

No GTK imports here: the PySide6 updater uses this too.
"""

import json
from dataclasses import dataclass, fields
from typing import Any

from loguru import logger

from .paths import CONFIG_FILE
from .settings_constants import DEFAULTS
from .terminal import default_terminal_command

# Bar component name -> its config.json key
BAR_COMPONENT_KEYS = {
    "button_apps": "bar_button_apps_visible",
    "systray": "bar_systray_visible",
    "control": "bar_control_visible",
    "network": "bar_network_visible",
    "button_tools": "bar_button_tools_visible",
    "sysprofiles": "bar_sysprofiles_visible",
    "button_overview": "bar_button_overview_visible",
    "ws_container": "bar_ws_container_visible",
    "weather": "bar_weather_visible",
    "battery": "bar_battery_visible",
    "metrics": "bar_metrics_visible",
    "language": "bar_language_visible",
    "date_time": "bar_date_time_visible",
    "button_power": "bar_button_power_visible",
}


def read_config_file() -> dict:
    """config.json as a dict; empty when it's missing or unreadable."""
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    return config


def get_default(key: str) -> Any:
    """The default for a setting; "" for one without a default."""
    return DEFAULTS[key] if key in DEFAULTS else ""


@dataclass
class Settings:
    """Typed settings; each field is the config.json key of the same name."""

    wallpapers_dir: str
    bar_position: str
    centered_bar: bool
    datetime_12h_format: bool
    gtk_theming: bool
    terminal_command: str
    dock_enabled: bool
    dock_always_show: bool
    dock_icon_size: int
    bar_workspace_show_number: bool
    bar_workspace_use_runes: bool
    bar_hide_special_workspace: bool
    bar_theme: str
    dock_theme: str
    panel_theme: str
    panel_position: str
    notif_pos: str
    bar_metrics_disks: list
    metrics_visible: dict
    metrics_small_visible: dict
    selected_monitors: list
    corners_visible: bool
    # Bar component name (BAR_COMPONENT_KEYS) -> shown at startup
    bar_components_visibility: dict

    @property
    def vertical(self) -> bool:
        """The bar runs down a side of the screen."""
        return self.bar_position in ["Left", "Right"]

    @classmethod
    def from_config(cls, config: dict) -> "Settings":
        """Settings from a config.json dict, with defaults for missing keys."""

        def value(key):
            return config.get(key, get_default(key))

        plain = {
            f.name: value(f.name) for f in fields(cls)
            if f.name not in ("terminal_command", "bar_components_visibility")
        }
        return cls(
            **plain,
            # Not saved yet (first run): the terminal found on this system
            terminal_command=(config["terminal_command"] if "terminal_command" in config
                              else default_terminal_command()),
            bar_components_visibility={
                name: value(key) for name, key in BAR_COMPONENT_KEYS.items()
            },
        )


settings = Settings.from_config(read_config_file())
