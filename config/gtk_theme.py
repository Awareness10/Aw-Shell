"""GTK apps in aw-shell's matugen colors (the gtk_theming setting).

Writes ~/.config/gtk-3.0/gtk.css and ~/.config/gtk-4.0/gtk.css from the
palette matugen renders to colors.json. They only set the color names
adw-gtk3 (GTK 3) and libadwaita (GTK 4) read, in the shell's dark style:
OLED black windows, matugen surfaces and accents. A file already there is
kept as gtk.css.aw-shell-backup and put back when the setting is off.

GTK reads these files when an app starts. The file picker runs inside
xdg-desktop-portal-gtk, which stays up, so it's restarted on a change.

No GTK imports here: the settings window uses this too.
"""

import json
import os
import subprocess
from pathlib import Path

from config.paths import COLORS_JSON, CONFIG_HOME

MARKER = "/* Written by aw-shell (GTK colors setting). Edits are overwritten. */"
BACKUP_SUFFIX = ".aw-shell-backup"

BLACK = "#000000"
# libadwaita's dark defaults, until colors.json has matugen's custom colors
FALLBACK_GREEN = "#26a269"
FALLBACK_YELLOW = "#cd9309"
DARK_TEXT = "rgba(0, 0, 0, 0.8)"


def gtk_palette(c: dict) -> dict:
    """libadwaita color names for a matugen palette (dark mode)."""
    fg = c["on_surface"]
    border = c["outline_variant"]
    lowest = c["surface_container_lowest"]
    low = c["surface_container_low"]
    container = c["surface_container"]
    green = c.get("green", FALLBACK_GREEN)
    yellow = c.get("yellow", FALLBACK_YELLOW)
    palette = {
        "accent_bg_color": c["primary"],
        "accent_fg_color": c["on_primary"],
        "accent_color": c["primary"],
        "destructive_bg_color": c["error"],
        "destructive_fg_color": c["on_error"],
        "destructive_color": c["error"],
        "error_bg_color": c["error"],
        "error_fg_color": c["on_error"],
        "error_color": c["error"],
        "success_bg_color": green,
        "success_fg_color": DARK_TEXT,
        "success_color": green,
        "warning_bg_color": yellow,
        "warning_fg_color": DARK_TEXT,
        "warning_color": yellow,
        "window_bg_color": BLACK,
        "window_fg_color": fg,
        "view_bg_color": BLACK,
        "view_fg_color": fg,
        "headerbar_bg_color": BLACK,
        "headerbar_fg_color": fg,
        "headerbar_border_color": fg,
        "headerbar_backdrop_color": BLACK,
        "headerbar_shade_color": "rgba(0, 0, 0, 0.36)",
        "headerbar_darker_shade_color": "rgba(0, 0, 0, 0.9)",
        "card_bg_color": low,
        "card_fg_color": fg,
        "card_shade_color": "rgba(0, 0, 0, 0.36)",
        "dialog_bg_color": lowest,
        "dialog_fg_color": fg,
        "popover_bg_color": container,
        "popover_fg_color": fg,
        "popover_shade_color": "rgba(0, 0, 0, 0.25)",
        "thumbnail_bg_color": container,
        "thumbnail_fg_color": fg,
        "shade_color": "rgba(0, 0, 0, 0.36)",
        "scrollbar_outline_color": "rgba(0, 0, 0, 0.5)",
    }
    for sidebar in ("sidebar", "secondary_sidebar"):
        palette.update({
            f"{sidebar}_bg_color": lowest,
            f"{sidebar}_fg_color": fg,
            f"{sidebar}_backdrop_color": BLACK,
            f"{sidebar}_border_color": border,
            f"{sidebar}_shade_color": "rgba(0, 0, 0, 0.25)",
        })
    return palette


def _named_colors(palette: dict) -> str:
    return "\n".join(f"@define-color {name} {value};" for name, value in palette.items())


def render_gtk3_css(colors: dict) -> str:
    return f"{MARKER}\n\n{_named_colors(gtk_palette(colors))}\n"


def render_gtk4_css(colors: dict) -> str:
    # libadwaita 1.6+ reads CSS variables; plain GTK 4 themes the named colors
    palette = gtk_palette(colors)
    variables = "\n".join(
        f"  --{name.replace('_', '-')}: {value};" for name, value in palette.items()
    )
    return f"{MARKER}\n\n{_named_colors(palette)}\n\n:root {{\n{variables}\n}}\n"


def _is_ours(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.readline().rstrip("\n") == MARKER


def _backup(path: Path) -> Path:
    return path.with_name(path.name + BACKUP_SUFFIX)


def _install(path: Path, content: str) -> bool:
    """Write our file, keeping what was there. False when nothing changed."""
    if _is_ours(path):
        if path.read_text(encoding="utf-8") == content:
            return False
    elif os.path.lexists(path):
        if os.path.lexists(_backup(path)):
            # A file the user put back after a backup was made: theirs wins
            print(f"Not changing {path}: {_backup(path)} already exists")
            return False
        os.rename(path, _backup(path))  # a symlink moves as it is
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    return True


def _uninstall(path: Path) -> bool:
    if not _is_ours(path):
        return False
    path.unlink()
    if os.path.lexists(_backup(path)):
        os.rename(_backup(path), path)
    return True


def sync_gtk_theme(enabled: bool, colors_file: Path, config_home: Path) -> bool:
    """Write (or remove) the GTK color files. True when a file changed."""
    targets = {
        config_home / "gtk-3.0" / "gtk.css": render_gtk3_css,
        config_home / "gtk-4.0" / "gtk.css": render_gtk4_css,
    }
    changed = False
    try:
        if not enabled:
            for path in targets:
                changed |= _uninstall(path)
            return changed
        try:
            colors = json.loads(colors_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return False  # matugen hasn't run yet
        for path, render in targets.items():
            changed |= _install(path, render(colors))
    except (OSError, ValueError, KeyError) as e:
        print(f"Error updating the GTK colors: {e}")
    return changed


def restart_file_picker() -> None:
    """Restart the portal's GTK backend (if running) so the next file picker
    loads the new colors. It's started again on demand."""
    try:
        subprocess.Popen(
            ["systemctl", "--user", "try-restart", "xdg-desktop-portal-gtk.service"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except OSError as e:
        print(f"Error restarting xdg-desktop-portal-gtk: {e}")


def apply_gtk_theme(enabled: bool) -> None:
    """Sync with the current matugen colors; called at startup and by
    matugen's post_hook after a wallpaper change."""
    if sync_gtk_theme(enabled, COLORS_JSON, CONFIG_HOME):
        restart_file_picker()
