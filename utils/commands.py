"""Commands the running shell accepts from outside.

Hyprland keybinds and matugen post_hooks call into the shell with
`fabric-cli exec aw-shell '<python>'`. fabric runs that code in main.py's
module namespace, where an instance of ShellCommands is published as `shell`,
so a bind only says `shell.open("launcher")` and this class is the one place
that knows where things live in the widget tree.

The names older generated configs use (`notch`, `app.set_css()`,
`app.apply_gtk_theme()`, ...) stay resolvable in main.py for configs written
before the facade existed (see tests/test_commands.py).
"""

from utils.global_keybinds import get_global_keybind_handler

# Notch views the keybinds open (Notch.open_notch names)
NOTCH_VIEWS = (
    "dashboard",
    "bluetooth",
    "pins",
    "kanban",
    "launcher",
    "tmux",
    "cliphist",
    "tools",
    "overview",
    "wallpapers",
    "mixer",
    "emoji",
    "power",
)


class ShellCommands:
    """One method per action keybinds and hooks trigger.

    `notch` is any monitor's notch: open_notch moves to the focused monitor's
    notch itself, and the wallpaper and caffeine actions aren't per-monitor.
    """

    def __init__(self, app, notch):
        self._app = app
        self._notch = notch

    def open(self, view: str) -> None:
        """Open (or toggle) a notch view on the focused monitor."""
        self._notch.open_notch(view)

    def random_wallpaper(self) -> None:
        self._notch.dashboard.wallpapers.set_random_wallpaper(None, external=True)

    def toggle_caffeine(self) -> None:
        self._notch.dashboard.widgets.buttons.caffeine_button.toggle_inhibit(external=True)

    def toggle_bar(self) -> bool:
        """Show/hide the bar on every monitor."""
        return get_global_keybind_handler().toggle_bar()

    def reload_css(self) -> None:
        from config.paths import APP_DIR
        from utils.stylesheet import build_stylesheet

        self._app.set_stylesheet_from_string(build_stylesheet(), base_path=str(APP_DIR))

    def apply_gtk_theme(self) -> None:
        """GTK apps in the shell's colors (or the user's files back when off)."""
        from config.data import GTK_THEMING
        from config.gtk_theme import apply_gtk_theme

        apply_gtk_theme(GTK_THEMING)


def install_legacy_aliases(app, shell: ShellCommands) -> None:
    """Keep `app.set_css()` and `app.apply_gtk_theme()` working: keybinds and
    matugen post_hooks generated before the facade call them."""
    app.set_css = shell.reload_css
    app.apply_gtk_theme = shell.apply_gtk_theme
