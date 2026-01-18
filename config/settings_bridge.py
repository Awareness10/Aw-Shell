"""
Settings Bridge for Aw-Shell

Loads and saves settings from ~/.config/aw-shell/config/config.json
Provides integration with Aw-Shell's settings_utils module.
"""

import json
import os
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

APP_NAME = "aw-shell"
APP_NAME_CAP = "Aw-Shell"
HOME_DIR = str(Path.home())
USER = os.environ.get("USER")

DEFAULTS = {
    "prefix_restart": "SUPER ALT",
    "suffix_restart": "B",
    "prefix_axmsg": "SUPER",
    "suffix_axmsg": "A",
    "prefix_dash": "SUPER",
    "suffix_dash": "D",
    "prefix_bluetooth": "SUPER",
    "suffix_bluetooth": "B",
    "prefix_pins": "SUPER",
    "suffix_pins": "Q",
    "prefix_kanban": "SUPER",
    "suffix_kanban": "N",
    "prefix_launcher": "SUPER",
    "suffix_launcher": "R",
    "prefix_tmux": "SUPER",
    "suffix_tmux": "T",
    "prefix_cliphist": "SUPER",
    "suffix_cliphist": "V",
    "prefix_toolbox": "SUPER",
    "suffix_toolbox": "S",
    "prefix_overview": "SUPER",
    "suffix_overview": "TAB",
    "prefix_wallpapers": "SUPER",
    "suffix_wallpapers": "COMMA",
    "prefix_randwall": "SUPER SHIFT",
    "suffix_randwall": "COMMA",
    "prefix_mixer": "SUPER",
    "suffix_mixer": "M",
    "prefix_emoji": "SUPER",
    "suffix_emoji": "PERIOD",
    "prefix_power": "SUPER",
    "suffix_power": "ESCAPE",
    "prefix_caffeine": "SUPER SHIFT",
    "suffix_caffeine": "M",
    "prefix_toggle": "SUPER CTRL",
    "suffix_toggle": "B",
    "prefix_css": "SUPER SHIFT",
    "suffix_css": "B",
    "wallpapers_dir": f"{HOME_DIR}/.config/{APP_NAME}/assets/wallpapers_example",
    "prefix_restart_inspector": "SUPER CTRL ALT",
    "suffix_restart_inspector": "B",
    "bar_position": "Top",
    "vertical": False,
    "centered_bar": False,
    "datetime_12h_format": False,
    "terminal_command": "kitty -e",
    "auto_append_hyprland": True,
    "dock_enabled": True,
    "dock_icon_size": 28,
    "dock_always_show": False,
    "bar_workspace_show_number": False,
    "bar_workspace_use_chinese_numerals": False,
    "bar_hide_special_workspace": True,
    "bar_theme": "Pills",
    "dock_theme": "Pills",
    "panel_theme": "Notch",
    "panel_position": "Center",
    "notif_pos": "Top",
    "bar_button_apps_visible": True,
    "bar_systray_visible": True,
    "bar_control_visible": True,
    "bar_network_visible": True,
    "bar_button_tools_visible": True,
    "bar_sysprofiles_visible": True,
    "bar_button_overview_visible": True,
    "bar_ws_container_visible": True,
    "bar_weather_visible": True,
    "bar_battery_visible": True,
    "bar_metrics_visible": True,
    "bar_language_visible": True,
    "bar_date_time_visible": True,
    "bar_button_power_visible": True,
    "corners_visible": True,
    "bar_metrics_disks": ["/"],
    "metrics_visible": {
        "cpu": True,
        "ram": True,
        "disk": True,
        "gpu": True,
    },
    "metrics_small_visible": {
        "cpu": True,
        "ram": True,
        "disk": True,
        "gpu": True,
    },
    "limited_apps_history": ["Spotify"],
    "history_ignored_apps": ["Hyprshot"],
    "selected_monitors": [],
}


class SettingsBridge:
    """Bridge to Aw-Shell's config.json settings storage."""

    def __init__(self):
        self.config_path = os.path.expanduser(
            f"~/.config/{APP_NAME}/config/config.json"
        )
        self._settings: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load settings from config.json, merging with defaults."""
        self._settings = DEFAULTS.copy()

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    saved = json.load(f)
                    self._deep_update(self._settings, saved)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading config: {e}, using defaults")

        # Ensure nested dicts have all keys
        for key in ["metrics_visible", "metrics_small_visible"]:
            if key in DEFAULTS and isinstance(DEFAULTS[key], dict):
                if not isinstance(self._settings.get(key), dict):
                    self._settings[key] = DEFAULTS[key].copy()
                else:
                    for subkey, subval in DEFAULTS[key].items():
                        if subkey not in self._settings[key]:
                            self._settings[key][subkey] = subval

    def _deep_update(self, target: dict, update: dict) -> dict:
        """Recursively update nested dictionaries."""
        for key, value in update.items():
            if (
                isinstance(value, dict)
                and key in target
                and isinstance(target[key], dict)
            ):
                self._deep_update(target[key], value)
            else:
                target[key] = value
        return target

    def save(self) -> None:
        """Save current settings to config.json."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._settings, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(
            key, default if default is not None else DEFAULTS.get(key)
        )

    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        self._settings[key] = value

    def get_all(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy()

    def set_all(self, settings: Dict[str, Any]) -> None:
        """Set all settings from a dictionary."""
        self._settings = settings

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = DEFAULTS.copy()

    def generate_hyprconf(self) -> str:
        """Generate Hyprland configuration string."""
        home = HOME_DIR
        bar_position = self.get("bar_position")
        is_vertical = bar_position in ["Left", "Right"]
        animation_type = "slidefadevert" if is_vertical else "slidefade"

        return f"""exec-once = uwsm-app $(python {home}/.config/{APP_NAME}/main.py)
exec = pgrep -x "hypridle" > /dev/null || uwsm app -- hypridle
exec = uwsm app -- awww-daemon
exec-once =  wl-paste --type text --watch cliphist store
exec-once =  wl-paste --type image --watch cliphist store

$fabricSend = fabric-cli exec {APP_NAME}
$axMessage = notify-send "{USER}" "Ya boi be cooking‼️🗣️🔥🕳️" -i "{home}/.config/{APP_NAME}/assets/tanjiro-kamado-red.png" -A "🗣️" -A "🔥" -A "🕳️" -a "Source Code"

bind = {self.get("prefix_restart")}, {self.get("suffix_restart")}, exec, killall {APP_NAME}; uwsm-app $(python {home}/.config/{APP_NAME}/main.py) # Reload {APP_NAME_CAP}
bind = {self.get("prefix_axmsg")}, {self.get("suffix_axmsg")}, exec, $axMessage # Message
bind = {self.get("prefix_dash")}, {self.get("suffix_dash")}, exec, $fabricSend 'notch.open_notch("dashboard")' # Dashboard
bind = {self.get("prefix_bluetooth")}, {self.get("suffix_bluetooth")}, exec, $fabricSend 'notch.open_notch("bluetooth")' # Bluetooth
bind = {self.get("prefix_pins")}, {self.get("suffix_pins")}, exec, $fabricSend 'notch.open_notch("pins")' # Pins
bind = {self.get("prefix_kanban")}, {self.get("suffix_kanban")}, exec, $fabricSend 'notch.open_notch("kanban")' # Kanban
bind = {self.get("prefix_launcher")}, {self.get("suffix_launcher")}, exec, $fabricSend 'notch.open_notch("launcher")' # App Launcher
bind = {self.get("prefix_tmux")}, {self.get("suffix_tmux")}, exec, $fabricSend 'notch.open_notch("tmux")' # Tmux
bind = {self.get("prefix_cliphist")}, {self.get("suffix_cliphist")}, exec, $fabricSend 'notch.open_notch("cliphist")' # Clipboard History
bind = {self.get("prefix_toolbox")}, {self.get("suffix_toolbox")}, exec, $fabricSend 'notch.open_notch("tools")' # Toolbox
bind = {self.get("prefix_overview")}, {self.get("suffix_overview")}, exec, $fabricSend 'notch.open_notch("overview")' # Overview
bind = {self.get("prefix_wallpapers")}, {self.get("suffix_wallpapers")}, exec, $fabricSend 'notch.open_notch("wallpapers")' # Wallpapers
bind = {self.get("prefix_randwall")}, {self.get("suffix_randwall")}, exec, $fabricSend 'notch.dashboard.wallpapers.set_random_wallpaper(None, external=True)' # Random Wallpaper
bind = {self.get("prefix_mixer")}, {self.get("suffix_mixer")}, exec, $fabricSend 'notch.open_notch("mixer")' # Audio Mixer
bind = {self.get("prefix_emoji")}, {self.get("suffix_emoji")}, exec, $fabricSend 'notch.open_notch("emoji")' # Emoji Picker
bind = {self.get("prefix_power")}, {self.get("suffix_power")}, exec, $fabricSend 'notch.open_notch("power")' # Power Menu
bind = {self.get("prefix_caffeine")}, {self.get("suffix_caffeine")}, exec, $fabricSend 'notch.dashboard.widgets.buttons.caffeine_button.toggle_inhibit(external=True)' # Toggle Caffeine
bind = {self.get("prefix_toggle")}, {self.get("suffix_toggle")}, exec, $fabricSend 'from utils.global_keybinds import get_global_keybind_handler; get_global_keybind_handler().toggle_bar()' # Toggle Bar
bind = {self.get("prefix_css")}, {self.get("suffix_css")}, exec, $fabricSend 'app.set_css()' # Reload CSS
bind = {self.get("prefix_restart_inspector")}, {self.get("suffix_restart_inspector")}, exec, killall {APP_NAME}; uwsm-app $(GTK_DEBUG=interactive python {home}/.config/{APP_NAME}/main.py) # Restart with inspector

# Wallpapers directory: {self.get("wallpapers_dir")}

source = {home}/.config/{APP_NAME}/config/hypr/colors.conf

layerrulev3 = animation 0, namespace:fabric

exec = cp $wallpaper ~/.current.wall

general {{
    col.active_border = rgb($primary)
    col.inactive_border = rgb($surface)
    gaps_in = 2
    gaps_out = 4
    border_size = 2
    layout = dwindle
}}

cursor {{
  no_warps=true
}}

decoration {{
    blur {{
        enabled = yes
        size = 1
        passes = 3
        new_optimizations = yes
        contrast = 1
        brightness = 1
    }}
    rounding = 14
    shadow {{
      enabled = true
      range = 10
      render_power = 2
      color = rgba(0, 0, 0, 0.25)
    }}
}}

animations {{
    enabled = yes
    bezier = myBezier, 0.4, 0.0, 0.2, 1.0
    animation = windows, 1, 2.5, myBezier, popin 80%
    animation = border, 1, 2.5, myBezier
    animation = fade, 1, 2.5, myBezier
    animation = workspaces, 1, 2.5, myBezier, {animation_type} 20%
}}
"""

    def apply_and_restart(
        self, replace_lock: bool = False, replace_idle: bool = False
    ) -> None:
        """Save settings, generate hyprconf, and restart Aw-Shell."""
        self.save()

        # Generate hyprconf
        hypr_config_dir = os.path.expanduser(f"~/.config/{APP_NAME}/config/hypr/")
        os.makedirs(hypr_config_dir, exist_ok=True)
        hypr_conf_path = os.path.join(hypr_config_dir, f"{APP_NAME}.conf")

        try:
            with open(hypr_conf_path, "w") as f:
                f.write(self.generate_hyprconf())
        except Exception as e:
            print(f"Error writing Hyprland config: {e}")

        # Handle lock/idle config replacement
        if replace_lock:
            src = os.path.expanduser(f"~/.config/{APP_NAME}/config/hypr/hyprlock.conf")
            dest = os.path.expanduser("~/.config/hypr/hyprlock.conf")
            if os.path.exists(src):
                self._backup_and_replace(src, dest, "Hyprlock")

        if replace_idle:
            src = os.path.expanduser(f"~/.config/{APP_NAME}/config/hypr/hypridle.conf")
            dest = os.path.expanduser("~/.config/hypr/hypridle.conf")
            if os.path.exists(src):
                self._backup_and_replace(src, dest, "Hypridle")

        # Auto-append to hyprland.conf if enabled
        if self.get("auto_append_hyprland", True):
            hypr_path = os.path.expanduser("~/.config/hypr/hyprland.conf")
            source_string = f"source = ~/.config/{APP_NAME}/config/hypr/{APP_NAME}.conf"

            try:
                needs_append = True
                if os.path.exists(hypr_path):
                    with open(hypr_path, "r") as f:
                        if source_string in f.read():
                            needs_append = False
                else:
                    os.makedirs(os.path.dirname(hypr_path), exist_ok=True)

                if needs_append:
                    with open(hypr_path, "a") as f:
                        f.write("\n" + source_string)
            except Exception as e:
                print(f"Error updating hyprland.conf: {e}")

        # Reload Hyprland
        try:
            subprocess.run(["hyprctl", "reload"], capture_output=True)
        except Exception as e:
            print(f"Error reloading Hyprland: {e}")

        # Restart Aw-Shell
        main_py = os.path.expanduser(f"~/.config/{APP_NAME}/main.py")
        try:
            subprocess.Popen(
                f"killall {APP_NAME}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            print(f"Error killing {APP_NAME}: {e}")

        try:
            subprocess.Popen(
                ["uwsm", "app", "--", "python", main_py],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            print(f"Error restarting {APP_NAME_CAP}: {e}")

    def _backup_and_replace(self, src: str, dest: str, config_name: str) -> None:
        """Backup existing config and replace with new one."""
        try:
            if os.path.exists(dest):
                backup_path = dest + ".bak"
                shutil.copy(dest, backup_path)
                print(f"{config_name} config backed up to {backup_path}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy(src, dest)
            print(f"{config_name} config replaced from {src}")
        except Exception as e:
            print(f"Error backing up/replacing {config_name} config: {e}")

    def get_available_monitors(self) -> list:
        """Get list of available monitors."""
        try:
            result = subprocess.run(
                ["hyprctl", "monitors", "-j"], capture_output=True, text=True
            )
            if result.returncode == 0:
                import json

                monitors = json.loads(result.stdout)
                return [
                    {
                        "id": m.get("id", 0),
                        "name": m.get("name", f"monitor-{m.get('id', 0)}"),
                    }
                    for m in monitors
                ]
        except Exception as e:
            print(f"Error getting monitors: {e}")

        return [{"id": 0, "name": "default"}]


# Global instance
_bridge: Optional[SettingsBridge] = None


def get_bridge() -> SettingsBridge:
    """Get the global settings bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = SettingsBridge()
    return _bridge
