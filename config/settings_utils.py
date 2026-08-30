import json
import os
import shutil
import subprocess
import time
import toml
from pathlib import Path

from .settings_constants import DEFAULTS, APP_NAME,APP_NAME_CAP # noqa: E402
from .data import (
    USERNAME,
    HOME_DIR,
    CONFIG_DIR,
    AW_CONFIG_DIR,
    CONFIG_FILE,
    FACE_ICON,
    DEFAULT_FACE_ICON,
    get_default,
)

from fabric.utils.helpers import exec_shell_command_async

CURRENT_WALL = HOME_DIR / ".current.wall"
HYPR_COLORS = AW_CONFIG_DIR / "hypr" / "colors.conf"
HYPR_COLORS_LUA = AW_CONFIG_DIR / "hypr" / "colors.lua"
CSS_COLORS = AW_CONFIG_DIR / "styles" / "colors.css"

# Global variable to store binding variables, managed by this module
bind_vars = {}  # Se inicializa vacío, load_bind_vars lo poblará


def get_bind_var(setting_str: str, default=None):
    if default is not None:
        return bind_vars.get(setting_str, default)
    return bind_vars.get(setting_str, get_default(setting_str))


def set_bind_var(key: str, value) -> None:
    bind_vars[key] = value


def set_all_bind_vars(settings: dict) -> None:
    bind_vars.clear()
    bind_vars.update(settings)


def save_bind_vars() -> None:
    """Save current bind_vars to config.json."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        CONFIG_FILE.write_text(json.dumps(bind_vars, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"Error saving config: {e}")


def reset_to_defaults() -> None:
    bind_vars.clear()
    bind_vars.update(DEFAULTS.copy())


def get_available_monitors() -> list:
    """Get list of available monitors from Hyprland."""
    try:
        result = subprocess.run(
            ["hyprctl", "monitors", "-j"], capture_output=True, text=True
        )
        if result.returncode == 0:
            monitors = json.loads(result.stdout)
            return [
                {"id": m.get("id", 0), "name": m.get("name", f"monitor-{m.get('id', 0)}")}
                for m in monitors
            ]
    except Exception as e:
        print(f"Error getting monitors: {e}")
    return [{"id": 0, "name": "default"}]


def apply_and_restart(replace_lock: bool = False, replace_idle: bool = False) -> None:
    """Save settings, generate hyprconf, and restart Aw-Shell."""
    save_bind_vars()

    hypr_config_dir = AW_CONFIG_DIR / "hypr"
    hypr_config_dir.mkdir(parents=True, exist_ok=True)
    hypr_lua_path = hypr_config_dir / f"{APP_NAME}.lua"

    try:
        hypr_lua_path.write_text(generate_hyprlua(), encoding="utf-8")
    except Exception as e:
        print(f"Error writing Hyprland config: {e}")

    if replace_lock:
        src = AW_CONFIG_DIR / "hypr" / "hyprlock.conf"
        dest = CONFIG_DIR / "hypr" / "hyprlock.conf"
        if src.exists():
            backup_and_replace(src, dest, "Hyprlock")

    if replace_idle:
        src = AW_CONFIG_DIR / "hypr" / "hypridle.conf"
        dest = CONFIG_DIR / "hypr" / "hypridle.conf"
        if src.exists():
            backup_and_replace(src, dest, "Hypridle")

    if get_bind_var("auto_append_hyprland"):
        hypr_path = CONFIG_DIR / "hypr" / "hyprland.lua"
        dofile_string = f'dofile("{AW_CONFIG_DIR}/hypr/{APP_NAME}.lua")'
        try:
            needs_append = True
            if hypr_path.exists():
                if dofile_string in hypr_path.read_text(encoding="utf-8"):
                    needs_append = False
            else:
                hypr_path.parent.mkdir(parents=True, exist_ok=True)
            if needs_append:
                with open(hypr_path, "a") as f:
                    f.write("\n" + dofile_string + "\n")
        except Exception as e:
            print(f"Error updating hyprland.lua: {e}")

    try:
        subprocess.run(["hyprctl", "reload"], capture_output=True)
    except Exception as e:
        print(f"Error reloading Hyprland: {e}")

    install_dir = CONFIG_DIR / APP_NAME
    main_py = str(install_dir / "main.py")
    venv_python = str(install_dir / ".venv" / "bin" / "python")
    try:
        subprocess.Popen(
            f"killall {APP_NAME}", shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        print(f"Error killing {APP_NAME}: {e}")

    try:
        subprocess.Popen(
            ["uwsm", "app", "--", venv_python, main_py],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        print(f"Error restarting {APP_NAME_CAP}: {e}")


def deep_update(target: dict, update: dict) -> dict:
    """
    Recursively update a nested dictionary with values from another dictionary.
    Modifies target in-place.
    """
    for key, value in update.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            # Si el valor es un diccionario y la clave ya existe en target como diccionario,
            # entonces actualiza recursivamente.
            deep_update(target[key], value)
        else:
            # De lo contrario, simplemente establece/sobrescribe el valor.
            target[key] = value
    return target  # Aunque modifica in-place, devolverlo es una convención común


def ensure_matugen_config():
    """
    Ensure that the matugen configuration file exists and is updated
    with the expected settings.
    """
    expected_config = {
        "config": {
            "reload_apps": True,
            "wallpaper": {
                "command": "awww",
                "arguments": [
                    "img",
                    "-t",
                    "fade",
                    "--transition-duration",
                    "0.5",
                    "--transition-step",
                    "255",
                    "--transition-fps",
                    "60",
                    "-f",
                    "Nearest",
                ],
                "set": True,
            },
            "custom_colors": {
                "red": {"color": "#FF0000", "blend": True},
                "green": {"color": "#00FF00", "blend": True},
                "yellow": {"color": "#FFFF00", "blend": True},
                "blue": {"color": "#0000FF", "blend": True},
                "magenta": {"color": "#FF00FF", "blend": True},
                "cyan": {"color": "#00FFFF", "blend": True},
                "white": {"color": "#FFFFFF", "blend": True},
            },
        },
        "templates": {
            "hyprland": {
                "input_path": f"{str(AW_CONFIG_DIR)}/matugen/templates/hyprland-colors.conf",
                "output_path": f"{str(AW_CONFIG_DIR)}/hypr/colors.conf",
            },
            "hyprland-lua": {
                "input_path": f"{str(AW_CONFIG_DIR)}/matugen/templates/hyprland-colors.lua",
                "output_path": f"{str(AW_CONFIG_DIR)}/hypr/colors.lua",
            },
            f"{APP_NAME}": {
                "input_path": f"{str(AW_CONFIG_DIR)}/matugen/templates/{APP_NAME}.css",
                "output_path": f"~/.config/{APP_NAME}/styles/colors.css",
                "post_hook": f"fabric-cli exec {APP_NAME} 'app.set_css()' &",
            },
        },
    }

    config_path = os.path.expanduser("~/.config/matugen/config.toml")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    existing_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                existing_config = toml.load(f)
            shutil.copyfile(config_path, config_path + ".bak")
        except toml.TomlDecodeError:
            print(
                f"Warning: Could not decode TOML from {config_path}. A new default config will be created."
            )
            existing_config = {}  # Resetear si está corrupto
        except Exception as e:
            print(f"Error reading or backing up {config_path}: {e}")
            # existing_config podría estar parcialmente cargado o vacío.
            # Continuar para intentar fusionar con defaults.

    # Usamos una copia de existing_config para deep_update si no queremos modificarlo directamente
    # o asegurarse que deep_update no lo haga si no es deseado.
    # La implementación actual de deep_update modifica 'target'.
    # Para ser más seguros, podemos pasar una copia si existing_config no debe cambiar.
    # merged_config = deep_update(existing_config.copy(), expected_config)
    # O si existing_config puede ser modificado:
    merged_config = deep_update(
        existing_config, expected_config
    )  # existing_config se modifica in-place

    try:
        with open(config_path, "w") as f:
            toml.dump(merged_config, f)
    except Exception as e:
        print(f"Error writing matugen config to {config_path}: {e}")

    # Ensure config directories exist (harmless if already present)
    HYPR_COLORS.parent.mkdir(parents=True, exist_ok=True)
    CSS_COLORS.parent.mkdir(parents=True, exist_ok=True)

    example_wallpaper = CONFIG_DIR / f"{APP_NAME}" / "assets" / "wallpapers_example" / "example-1.jpg"

    image_path: Path | None = None

    # Resolve current wallpaper (symlink or direct file)
    try:
        if CURRENT_WALL.is_symlink():
            image_path = CURRENT_WALL.resolve(strict=True)
        elif CURRENT_WALL.exists():
            image_path = CURRENT_WALL
    except FileNotFoundError:
        pass

    # If no valid wallpaper, create default symlink
    if not image_path or not image_path.exists():
        CURRENT_WALL.unlink(missing_ok=True)  # Clean broken/old
        if example_wallpaper.exists():
            try:
                CURRENT_WALL.symlink_to(example_wallpaper)
                image_path = example_wallpaper
            except Exception as e:
                print(f"Error creating symlink for wallpaper: {e}")
                image_path = None
        else:
            print("Example wallpaper not found.")
            image_path = None

    # Generate theme if valid image exists
    if image_path and image_path.exists():
        print(f"Generating color theme from wallpaper: {image_path}")
        try:
            matugen_cmd = f"matugen image '{image_path}' --source-color-index 0"
            exec_shell_command_async(matugen_cmd)
            print("Matugen color theme generation initiated.")
        except FileNotFoundError:
            print("Error: matugen command not found. Please install matugen.")
        except Exception as e:
            print(f"Error initiating matugen: {e}")
    elif image_path:
        print(f"Warning: Wallpaper at {image_path} not found. Cannot generate matugen theme.")
    else:
        print("Warning: No wallpaper path determined to generate matugen theme from.")


def load_bind_vars() -> None:
    """
    Load saved key binding variables from JSON, if available.
    Populates the global `bind_vars` in-place.
    """
    global bind_vars

    # Ensure config directory exists (for future saves)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Reset to defaults
    bind_vars.clear()
    bind_vars.update(DEFAULTS.copy())

    if CONFIG_FILE.exists():
        try:
            saved_vars = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            deep_update(bind_vars, saved_vars)

            # Ensure nested dict structure for specific keys
            for vis_key in ["metrics_visible", "metrics_small_visible"]:
                default_sub = DEFAULTS.get(vis_key)
                if isinstance(default_sub, dict):
                    if not isinstance(bind_vars.get(vis_key), dict):
                        bind_vars[vis_key] = default_sub.copy()
                    else:
                        for sub_key, sub_val in default_sub.items():
                            if sub_key not in bind_vars[vis_key]:
                                bind_vars[vis_key][sub_key] = sub_val

        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {CONFIG_FILE}. Using defaults.")
        except Exception as e:
            print(f"Error reading {CONFIG_FILE}: {e}. Using defaults.")


def generate_hyprlua() -> str:
    """
    Generate the Hyprland Lua configuration string using the current
    bind_vars - the Lua-syntax equivalent of generate_hyprconf(), for
    hyprland.lua's native Lua config support (which this setup now loads
    instead of hyprland.conf).
    """
    LOCAL_APP = CONFIG_DIR / APP_NAME
    APP_MAIN = LOCAL_APP / "main.py"
    VENV_PYTHON = LOCAL_APP / ".venv" / "bin" / "python"
    bar_position = get_bind_var("bar_position")
    is_vertical = bar_position in ["Left", "Right"]
    animation_type = "slidefadevert" if is_vertical else "slidefade"

    def lua_str(s: str) -> str:
        return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

    def mods_and_key(prefix_key: str, suffix_key: str) -> str:
        return " + ".join(get_bind_var(prefix_key).split() + [get_bind_var(suffix_key)])

    def notch_bind(prefix_key: str, suffix_key: str, expr: str, comment: str) -> str:
        cmd = "fabricSend .. " + lua_str(f" '{expr}'")
        return f'hl.bind({lua_str(mods_and_key(prefix_key, suffix_key))}, hl.dsp.exec_cmd({cmd})) -- {comment}'

    notch_binds = [
        ("prefix_dash", "suffix_dash", 'notch.open_notch("dashboard")', "Dashboard"),
        ("prefix_bluetooth", "suffix_bluetooth", 'notch.open_notch("bluetooth")', "Bluetooth"),
        ("prefix_pins", "suffix_pins", 'notch.open_notch("pins")', "Pins"),
        ("prefix_kanban", "suffix_kanban", 'notch.open_notch("kanban")', "Kanban"),
        ("prefix_launcher", "suffix_launcher", 'notch.open_notch("launcher")', "App Launcher"),
        ("prefix_tmux", "suffix_tmux", 'notch.open_notch("tmux")', "Tmux"),
        ("prefix_cliphist", "suffix_cliphist", 'notch.open_notch("cliphist")', "Clipboard History"),
        ("prefix_toolbox", "suffix_toolbox", 'notch.open_notch("tools")', "Toolbox"),
        ("prefix_overview", "suffix_overview", 'notch.open_notch("overview")', "Overview"),
        ("prefix_wallpapers", "suffix_wallpapers", 'notch.open_notch("wallpapers")', "Wallpapers"),
        ("prefix_randwall", "suffix_randwall",
         'notch.dashboard.wallpapers.set_random_wallpaper(None, external=True)', "Random Wallpaper"),
        ("prefix_mixer", "suffix_mixer", 'notch.open_notch("mixer")', "Audio Mixer"),
        ("prefix_emoji", "suffix_emoji", 'notch.open_notch("emoji")', "Emoji Picker"),
        ("prefix_power", "suffix_power", 'notch.open_notch("power")', "Power Menu"),
        ("prefix_caffeine", "suffix_caffeine",
         "notch.dashboard.widgets.buttons.caffeine_button.toggle_inhibit(external=True)", "Toggle Caffeine"),
        ("prefix_toggle", "suffix_toggle",
         "from utils.global_keybinds import get_global_keybind_handler; get_global_keybind_handler().toggle_bar()",
         "Toggle Bar"),
        ("prefix_css", "suffix_css", "app.set_css()", "Reload CSS"),
    ]

    bind_lines = [
        f'hl.bind({lua_str(mods_and_key("prefix_restart", "suffix_restart"))}, '
        f'hl.dsp.exec_cmd({lua_str(f"killall {APP_NAME}; uwsm-app $({VENV_PYTHON} {APP_MAIN})")})) '
        f'-- Reload {APP_NAME_CAP}',
        f'hl.bind({lua_str(mods_and_key("prefix_axmsg", "suffix_axmsg"))}, '
        f'hl.dsp.exec_cmd(axMessage)) -- Message',
    ]
    bind_lines += [notch_bind(*spec) for spec in notch_binds]
    bind_lines.append(
        f'hl.bind({lua_str(mods_and_key("prefix_restart_inspector", "suffix_restart_inspector"))}, '
        f'hl.dsp.exec_cmd({lua_str(f"killall {APP_NAME}; uwsm-app $(GTK_DEBUG=interactive {VENV_PYTHON} {APP_MAIN})")})) '
        f'-- Restart with inspector'
    )
    binds_block = "\n".join(bind_lines)

    return f"""-- Generated by generate_hyprlua() in config/settings_utils.py - do not edit by hand,
-- changes will be overwritten the next time settings are applied.
local colors = dofile({lua_str(str(HYPR_COLORS_LUA))})

local fabricSend = "fabric-cli exec {APP_NAME}"
local axMessage = {lua_str(f'notify-send "{USERNAME}" "Ya boi be cooking‼️\U0001f5e3️\U0001f525\U0001f573️" -i "{LOCAL_APP}/assets/tanjiro-kamado-red.png" -A "\U0001f5e3️" -A "\U0001f525" -A "\U0001f573️" -a "Source Code"')}

{binds_block}

-- Wallpapers directory: {get_bind_var("wallpapers_dir")}

-- layerrulev3 = animation 0, namespace:fabric
-- TODO: manual review - layerrulev3 has no known hl.* equivalent yet, check the Hyprland wiki

hl.config({{
    general = {{
        gaps_in = 2,
        gaps_out = 4,
        border_size = 2,
        layout = "dwindle",
        col = {{
            active_border = "rgb(" .. colors.primary .. ")",
            inactive_border = "rgb(" .. colors.surface .. ")",
        }},
    }},
}})

hl.config({{
    cursor = {{
        no_warps = true,
    }},
}})

hl.config({{
    decoration = {{
        blur = {{
            enabled = true,
            size = 1,
            passes = 3,
            new_optimizations = true,
            contrast = 1,
            brightness = 1,
        }},
        rounding = 14,
        shadow = {{
            enabled = true,
            range = 10,
            render_power = 2,
            color = "rgba(00000040)",
        }},
    }},
}})

hl.config({{
    animations = {{
        enabled = true,
    }},
}})

hl.curve("myBezier", {{
    type = "bezier",
    points = {{ {{ 0.4, 0.0 }}, {{ 0.2, 1.0 }} }},
}})

hl.animation({{ leaf = "windows", enabled = true, speed = 2.5, bezier = "myBezier", style = "popin 80%" }})
hl.animation({{ leaf = "border", enabled = true, speed = 2.5, bezier = "myBezier" }})
hl.animation({{ leaf = "fade", enabled = true, speed = 2.5, bezier = "myBezier" }})
hl.animation({{ leaf = "workspaces", enabled = true, speed = 2.5, bezier = "myBezier", style = "{animation_type} 20%" }})

-- Autostart
hl.on("hyprland.start", function()
    hl.exec_cmd({lua_str(f"uwsm-app $({VENV_PYTHON} {APP_MAIN})")})
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")
end)

-- Exec (run every reload)
hl.on("config.reloaded", function()
    hl.exec_cmd("pgrep -x \\"hypridle\\" > /dev/null || uwsm app -- hypridle")
    -- ~/.current.wall is a symlink (see modules/wallpapers.py). Relink it
    -- rather than cp-ing into it - cp follows the symlink and overwrites
    -- the real target file's bytes with colors.wallpaper's content, which
    -- silently corrupts whichever wallpaper is currently selected any time
    -- colors.wallpaper is stale relative to it.
    hl.exec_cmd("ln -sf " .. colors.wallpaper .. " ~/.current.wall")
    hl.exec_cmd({lua_str(f"{LOCAL_APP}/scripts/start-awww.sh")})
end)

return {{
    fabricSend = fabricSend,
    axMessage = axMessage,
}}
"""


def ensure_face_icon() -> None:
    """Ensure ~/.face.icon exists by copying the default if missing."""
    if not FACE_ICON.exists() and DEFAULT_FACE_ICON.exists():
        try:
            shutil.copy(DEFAULT_FACE_ICON, FACE_ICON)
        except Exception as e:
            print(f"Error copying default face icon: {e}")

def backup_and_replace(src: Path, dest: Path, config_name: str) -> None:
    """Backup existing dest file (to .bak) and replace with src."""
    try:
        if dest.exists():
            backup = dest.with_name(dest.name + ".bak")
            shutil.copy(dest, backup)
            print(f"{config_name} config backed up to {backup}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
        print(f"{config_name} config replaced from {src}")
    except Exception as e:
        print(f"Error backing up/replacing {config_name} config: {e}")

def start_config() -> None:
    """Final setup: ensure assets/configs, write Hyprland conf, reload."""
    print(f"{time.time():.4f}: start_config: Ensuring matugen config...")
    ensure_matugen_config()

    print(f"{time.time():.4f}: start_config: Ensuring face icon...")
    ensure_face_icon()

    print(f"{time.time():.4f}: start_config: Generating hypr conf...")
    hypr_config_dir = AW_CONFIG_DIR / "hypr"
    hypr_config_dir.mkdir(parents=True, exist_ok=True)
    hypr_lua_path = hypr_config_dir / f"{APP_NAME}.lua"

    try:
        hypr_lua_path.write_text(generate_hyprlua(), encoding="utf-8")
        print(f"Generated Hyprland config at {hypr_lua_path}")
    except Exception as e:
        print(f"Error writing Hyprland config: {e}")

    print(f"{time.time():.4f}: start_config: Initiating hyprctl reload...")
    try:
        exec_shell_command_async("hyprctl reload")
        print(f"{time.time():.4f}: start_config: Hyprland reload initiated.")
    except Exception as e:
        print(f"Error initiating hyprctl reload: {e}")