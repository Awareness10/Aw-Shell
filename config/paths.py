"""Where Aw-Shell's files live.

APP_DIR holds the code and the files it ships (assets, CSS, scripts,
templates). It can be read-only (/usr/share/aw-shell, /nix/store/...).
Everything the shell writes lives under the XDG folders instead. In old
installs and in dev mode ~/.config/aw-shell is the clone itself, so both
point at the same files.

No GTK imports here: the PySide6 updater and settings use this too.
"""

import os
import shlex
import tempfile
from pathlib import Path

from .settings_constants import APP_NAME


def _xdg_dir(var: str, fallback: str) -> Path:
    # The XDG spec says relative values are invalid and must be ignored
    value = os.environ.get(var, "")
    return Path(value) if os.path.isabs(value) else Path.home() / fallback


APP_DIR = Path(__file__).resolve().parent.parent

CONFIG_HOME = _xdg_dir("XDG_CONFIG_HOME", ".config")
USER_DIR = CONFIG_HOME / APP_NAME
CACHE_DIR = _xdg_dir("XDG_CACHE_HOME", ".cache") / APP_NAME
DATA_DIR = _xdg_dir("XDG_DATA_HOME", ".local/share") / APP_NAME
STATE_DIR = _xdg_dir("XDG_STATE_HOME", ".local/state") / APP_NAME
_runtime = os.environ.get("XDG_RUNTIME_DIR", "")
# No runtime dir (rare outside a login session): a per-user folder in /tmp
RUNTIME_DIR = (
    Path(_runtime) / APP_NAME
    if os.path.isabs(_runtime)
    else Path(tempfile.gettempdir()) / f"{APP_NAME}-{os.getuid()}"
)

# Written by the shell, matugen and the settings window
AW_CONFIG_DIR = USER_DIR / "config"
CONFIG_FILE = AW_CONFIG_DIR / "config.json"
DOCK_FILE = AW_CONFIG_DIR / "dock.json"
COLORS_JSON = AW_CONFIG_DIR / "colors.json"
HYPR_DIR = AW_CONFIG_DIR / "hypr"
MATUGEN_STATE_FILE = AW_CONFIG_DIR / "matugen" / "matugen-state"
MATUGEN_SCHEME_FILE = AW_CONFIG_DIR / "matugen" / "matugen-scheme"
CSS_COLORS = USER_DIR / "styles" / "colors.css"
USER_CSS = USER_DIR / "styles" / "user.css"  # optional overrides, loaded last

# User data, history (worth keeping, not precious) and session-only files
KANBAN_FILE = DATA_DIR / "kanban.json"
PINS_FILE = DATA_DIR / "pins.json"
CALC_HISTORY = STATE_DIR / "calc.json"
CONVERSION_HISTORY = STATE_DIR / "conversion.json"
NOTIFICATIONS_DIR = RUNTIME_DIR / "notifications"
NOTIFICATION_HISTORY = NOTIFICATIONS_DIR / "notification_history.json"
CAVA_FIFO = RUNTIME_DIR / "cava.fifo"
CAVA_CONFIG = RUNTIME_DIR / "cava.ini"  # the shipped one, pointed at CAVA_FIFO
REMOTE_VERSION_FILE = RUNTIME_DIR / "remote_version.json"

# Shipped with the code
MAIN_CSS = APP_DIR / "main.css"
DEFAULT_CSS_COLORS = APP_DIR / "styles" / "colors.default.css"
MATUGEN_TEMPLATES = APP_DIR / "config" / "matugen" / "templates"
HYPRLOCK_TEMPLATE = APP_DIR / "config" / "hypr" / "hyprlock.conf"
CAVA_TEMPLATE = APP_DIR / "config" / "cavalcade" / "cava.ini"
SCRIPTS_DIR = APP_DIR / "scripts"
DEFAULT_FACE_ICON = APP_DIR / "assets" / "tanjiro-kamado-red.png"
DEFAULT_WALLPAPER = APP_DIR / "assets" / "wallpapers_example" / "ax-red.jpg"


def ensure_dir(path: Path) -> Path:
    """Create a folder and any missing parents, each private to the user (the
    XDG spec asks for 0700), and return it. mkdir(parents=True) would give
    the parents default permissions."""
    missing = [p for p in (path, *path.parents) if not p.exists()]
    for folder in reversed(missing):
        folder.mkdir(mode=0o700, exist_ok=True)
    return path


def launch_command() -> list[str]:
    """Command that starts the shell: $AW_SHELL_LAUNCH (set by the AUR
    launcher and the Nix wrapper), else the clone's venv."""
    custom = os.environ.get("AW_SHELL_LAUNCH", "").strip()
    if custom:
        return shlex.split(custom)
    return [str(APP_DIR / ".venv" / "bin" / "python"), str(APP_DIR / "main.py")]


def self_updatable() -> bool:
    """The in-app updater git-pulls APP_DIR; package installs update through
    their package manager instead."""
    return (APP_DIR / ".git").exists() and os.access(APP_DIR, os.W_OK)


def colors_css() -> Path:
    """matugen's colors, or the shipped defaults until matugen has run."""
    return CSS_COLORS if CSS_COLORS.is_file() else DEFAULT_CSS_COLORS
