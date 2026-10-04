import os
import shlex
import subprocess as _sp
import sys

import setproctitle
from fabric import Application
from fabric.utils import exec_shell_command_async, get_relative_path
from gi.repository import GLib

from config.data import APP_NAME, CACHE_DIR, CONFIG_FILE
from config.settings_utils import ensure_current_wallpaper
from modules.bar import Bar
from modules.corners import Corners
from modules.dock import Dock
from modules.notch import Notch
from modules.notifications import NotificationPopup
from utils.tooltips import install_tooltip_dedup

fonts_updated_file = f"{CACHE_DIR}/fonts_updated"

if __name__ == "__main__":
    setproctitle.setproctitle(APP_NAME)
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

    GLib.idle_add(_launch_updater)
    GLib.timeout_add(3600000, _launch_updater)

    # Initialize multi-monitor services
    try:
        from utils.global_keybinds import init_global_keybind_objects
        from utils.monitor_manager import get_monitor_manager
        
        monitor_manager = get_monitor_manager()
        init_global_keybind_objects()
        
        # Get all available monitors
        all_monitors = monitor_manager.get_monitors()
        multi_monitor_enabled = True
    except ImportError:
        # Fallback to single monitor mode
        all_monitors = [{'id': 0, 'name': 'default'}]
        monitor_manager = None
        multi_monitor_enabled = False
    
    # Filter monitors based on selected_monitors configuration
    selected_monitors_config = config.get("selected_monitors", [])
    
    # If selected_monitors is empty, show on all monitors (current behavior)
    if not selected_monitors_config:
        monitors = all_monitors
        print("Aw-Shell: No specific monitors selected, showing on all monitors")
    else:
        # Filter monitors to only include selected ones
        monitors = []
        selected_monitor_names = set(selected_monitors_config)
        
        for monitor in all_monitors:
            monitor_name = monitor.get('name', f'monitor-{monitor.get("id", 0)}')
            if monitor_name in selected_monitor_names:
                monitors.append(monitor)
                print(f"Aw-Shell: Including monitor '{monitor_name}' (selected)")
            else:
                print(f"Aw-Shell: Excluding monitor '{monitor_name}' (not selected)")
        
        # Fallback: if no valid monitors found, use all monitors
        if not monitors:
            print("Aw-Shell: No valid selected monitors found, falling back to all monitors")
            monitors = all_monitors
    
    # Create application components list
    app_components = []
    notches = {}

    # The main monitor holds workspace 1; notifications start there
    primary_monitor_id = monitor_manager.get_primary_monitor_id() if monitor_manager else 0
    
    # Create components for each monitor
    for monitor in monitors:
        monitor_id = monitor['id']
        
        # Create monitor-specific components
        if multi_monitor_enabled:
            corners = Corners(monitor_id=monitor_id)
            bar = Bar(monitor_id=monitor_id)
            notch = Notch(monitor_id=monitor_id)
            dock = Dock(monitor_id=monitor_id)
        else:
            # Single monitor fallback
            corners = Corners()
            bar = Bar()
            notch = Notch()
            dock = Dock()

        # Layer surfaces are per-output, so each monitor needs its own corners
        corners.set_visible(config.get("corners_visible", True))
        app_components.append(corners)
        
        # Connect bar and notch
        bar.notch = notch
        notch.bar = bar
        
        notches[monitor_id] = notch

        # Register instances in monitor manager if available
        if multi_monitor_enabled and monitor_manager:
            monitor_manager.register_monitor_instances(monitor_id, {
                'bar': bar,
                'notch': notch,
                'dock': dock,
                'corners': corners
            })
        
        # Add components to app list
        app_components.extend([bar, notch, dock])

    # One notification popup, sharing the main monitor's notch widgets; the
    # first shown monitor stands in if the main one isn't selected. It starts
    # there and follows focus to any shown monitor as notifications arrive
    popup_monitor_id = primary_monitor_id if primary_monitor_id in notches else next(iter(notches))
    app_components.append(NotificationPopup(
        widgets=notches[popup_monitor_id].dashboard.widgets,
        monitor=popup_monitor_id if multi_monitor_enabled else None,
        follow_focus_monitors=list(notches) if multi_monitor_enabled else None,
    ))

    # Create the application with all components
    app = Application(f"{APP_NAME}", *app_components)

    def set_css():
        app.set_stylesheet_from_file(
            get_relative_path("main.css"),
        )

    app.set_css = set_css

    app.set_css()

    app.run()
