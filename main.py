# ruff: noqa: E402
import sys

from utils.typelibs import add_private_typelibs

add_private_typelibs()  # before anything imports gi (see utils/typelibs.py)

if __name__ == "__main__" and sys.argv[1:] == ["--migrate"]:
    # Before the widget imports below: they need a display and Hyprland
    from config.migrate import main as migrate

    sys.exit(migrate())

import os
import shlex
import subprocess as _sp

import setproctitle
from fabric import Application
from fabric.utils import exec_shell_command_async, get_relative_path
from gi.repository import GLib

from config.data import APP_NAME, CACHE_DIR, CONFIG_FILE
from config.legacy import move_legacy_files
from config.migrate import fix_hyprlock_config, old_install_notice
from config.paths import APP_DIR, USER_DIR, self_updatable
from config.settings_utils import ensure_current_wallpaper
from modules.bar import Bar
from modules.corners import Corners
from modules.dock import Dock
from modules.notch import Notch
from modules.notifications import NotificationPopup
from utils.commands import ShellCommands, install_legacy_aliases
from utils.global_keybinds import init_global_keybind_objects
from utils.monitor_manager import get_monitor_manager, select_monitors
from utils.tooltips import install_tooltip_dedup

fonts_updated_file = f"{CACHE_DIR}/fonts_updated"


def build_monitor_components(monitor_id, monitor_manager, corners_visible):
    """Corners, bar, notch and dock for one monitor, registered with the
    monitor manager; returns them by name."""
    corners = Corners(monitor_id=monitor_id)
    bar = Bar(monitor_id=monitor_id)
    notch = Notch(monitor_id=monitor_id)
    dock = Dock(monitor_id=monitor_id)

    # Layer surfaces are per-output, so each monitor needs its own corners
    corners.set_visible(corners_visible)

    bar.notch = notch
    notch.bar = bar

    components = {"bar": bar, "notch": notch, "dock": dock, "corners": corners}
    monitor_manager.register_monitor_instances(monitor_id, components)
    return components


def build_notification_popup(notches, primary_monitor_id):
    """One notification popup, sharing the main monitor's notch widgets; the
    first shown monitor stands in if the main one isn't selected. It starts
    there and follows focus to any shown monitor as notifications arrive."""
    popup_monitor_id = primary_monitor_id if primary_monitor_id in notches else next(iter(notches))
    return NotificationPopup(
        widgets=notches[popup_monitor_id].dashboard.widgets,
        monitor=popup_monitor_id,
        follow_focus_monitors=list(notches),
    )

if __name__ == "__main__":
    setproctitle.setproctitle(APP_NAME)
    move_legacy_files()  # before any widget reads kanban, pins or history
    for line in fix_hyprlock_config():  # --migrate does it too; AUR installs don't run that
        print(line)
    install_tooltip_dedup()

    if not os.path.isfile(CONFIG_FILE):
        config_script_path = get_relative_path("config/config.py")
        # The shell's own interpreter; the system python lacks its dependencies
        exec_shell_command_async(shlex.join([sys.executable, config_script_path]))

    ensure_current_wallpaper()

    # Load configuration
    from config.data import load_config

    config = load_config()

    def _launch_updater(force=False):
        """Launch the PySide6 updater in a separate process."""
        cmd = [sys.executable, "-m", "modules.updater"]
        if force:
            cmd.append("--force")
        try:
            _sp.Popen(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            print(f"Error launching updater: {e}")

    # Package installs (AUR, Nix) update through their package manager
    if self_updatable():
        GLib.idle_add(_launch_updater)
        GLib.timeout_add(3600000, _launch_updater)

    # Multi-monitor services
    monitor_manager = get_monitor_manager()
    init_global_keybind_objects()
    monitors = select_monitors(monitor_manager.get_monitors(), config.get("selected_monitors", []))

    # The main monitor holds workspace 1; notifications start there
    primary_monitor_id = monitor_manager.get_primary_monitor_id()

    app_components = []
    notches = {}
    for monitor in monitors:
        components = build_monitor_components(
            monitor["id"], monitor_manager, config.get("corners_visible", True))
        app_components.extend(components[name] for name in ("corners", "bar", "notch", "dock"))
        notches[monitor["id"]] = components["notch"]

    # The last monitor's notch, as before: older configs' `notch.open_notch(...)`
    # binds use it (open_notch moves to the focused monitor's notch itself)
    notch = components["notch"]

    app_components.append(build_notification_popup(notches, primary_monitor_id))

    # Create the application with all components
    app = Application(f"{APP_NAME}", *app_components)

    # `fabric-cli exec aw-shell 'shell.<command>()'` (keybinds, matugen
    # post_hooks) runs in this module's namespace; see utils/commands.py
    shell = ShellCommands(app, notch)

    # Older generated aw-shell.lua / matugen configs call `app.set_css()`,
    # `app.apply_gtk_theme()` and `notch....`, so `app` and `notch` stay
    # module globals too
    install_legacy_aliases(app, shell)

    shell.reload_css()

    # GTK apps in the shell's colors (or put the user's files back when off);
    # matugen's post_hook calls it again after a wallpaper change
    shell.apply_gtk_theme()

    # Package installs: point users with an old clone at --migrate, once the
    # shell's notification server is up
    notice = old_install_notice(USER_DIR, APP_DIR)
    if notice:
        def _send_notice():
            cmd = ["notify-send", "-u", "critical", APP_NAME, notice]
            exec_shell_command_async(shlex.join(cmd))
            return False  # once

        GLib.timeout_add_seconds(10, _send_notice)

    app.run()
