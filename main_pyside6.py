"""
PySide6 Shell entry point.

Usage:
    QT_WAYLAND_SHELL_INTEGRATION=layer-shell python main_pyside6.py
    or: ./test-pyside6.sh
"""

import signal
import subprocess
import sys
import os

os.environ.setdefault("QT_WAYLAND_SHELL_INTEGRATION", "layer-shell")

# Ensure config module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QScreen
from PySide6.QtWidgets import QApplication

from core.state import ShellState
from core.hyprland import HyprlandListener
from core.ipc import ShellIPC
from surfaces.bar import create_bar_surfaces, get_bar_stylesheet
from surfaces.dock import create_dock_surfaces, get_dock_stylesheet
from surfaces.notch import create_notch_surface, get_notch_stylesheet
from views.dashboard import get_dashboard_stylesheet
from views.launcher import get_launcher_stylesheet
from views.power import get_power_stylesheet
from views.overview import get_overview_stylesheet
from views.tools import get_tools_stylesheet
from views.emoji import get_emoji_stylesheet


class MockTheme:
    """Temporary theme until Glaze is integrated."""
    surface = "#1e1e2e"
    surface_variant = "#313244"
    accent = "#cba6f7"
    on_accent = "#1e1e2e"
    text_primary = "#cdd6f4"
    text_secondary = "#a6adc8"
    outline = "#45475a"


def _detect_icon_theme() -> str:
    """Read icon theme from gsettings (same as GTK apps use)."""
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "icon-theme"],
            capture_output=True, text=True, timeout=2,
        )
        name = r.stdout.strip().strip("'\"")
        if name:
            return name
    except Exception:
        pass
    return "Adwaita"


def _dispatch_ipc(state, cmd: str, args: str):
    """Route IPC commands to shell state actions."""
    if cmd == "open_notch":
        state.notch_opened.emit(args or "dashboard")
    elif cmd == "close_notch":
        state.notch_closed.emit()
    elif cmd == "toggle_bar":
        state.toggle_bar()
    elif cmd == "reload_css":
        print("[IPC] reload_css not yet implemented", flush=True)
    else:
        print(f"[IPC] Unknown command: {cmd} {args}", flush=True)


def main():
    app = QApplication(sys.argv)

    # Let Ctrl+C kill the app (Qt blocks SIGINT by default)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    # Also pump a timer so Python's signal handler actually fires
    _sigint_timer = QTimer()
    _sigint_timer.setInterval(200)
    _sigint_timer.timeout.connect(lambda: None)
    _sigint_timer.start()

    # Set icon theme so QIcon.fromTheme works for dock/bar
    QIcon.setThemeName(_detect_icon_theme())

    # Create state bus
    state = ShellState()

    # Get screens
    screens = app.screens()
    if not screens:
        print("No screens available", flush=True)
        return 1

    # Theme (mock for now)
    theme = MockTheme()

    # Build and apply stylesheet
    stylesheet = (
        get_bar_stylesheet(theme) +
        get_dock_stylesheet(theme) +
        get_notch_stylesheet(theme) +
        get_dashboard_stylesheet(theme) +
        get_launcher_stylesheet(theme) +
        get_power_stylesheet(theme) +
        get_overview_stylesheet(theme) +
        get_tools_stylesheet(theme) +
        get_emoji_stylesheet(theme)
    )
    app.setStyleSheet(stylesheet)

    # Create surfaces
    surfaces = []

    # Bars (one per screen)
    for surface, bar in create_bar_surfaces(state, screens):
        surfaces.append(surface)
        surface.show()

    # Notch (one per screen)
    for screen in screens:
        notch_surface = create_notch_surface(state, screen)
        surfaces.append(notch_surface)
        notch_surface.show()

    # Dock (one per screen)
    for surface, dock in create_dock_surfaces(state, screens):
        surfaces.append(surface)
        surface.show()

    # Start Hyprland listener
    hypr = HyprlandListener(state)

    # Start IPC server (replaces fabric-cli exec for keybinds)
    ipc = ShellIPC()
    ipc.command_received.connect(lambda cmd, args: _dispatch_ipc(state, cmd, args))
    ipc.start()

    n_screens = len(screens)
    print(f"PySide6 shell running on {n_screens} screen(s)", flush=True)
    print(f"  IPC: aw-shell-msg open_notch dashboard", flush=True)
    print("  Click compact notch -> dashboard", flush=True)
    print("  Escape -> close notch", flush=True)
    print("  Ctrl+C -> quit", flush=True)

    ret = app.exec()
    ipc.stop()
    return ret


if __name__ == "__main__":
    sys.exit(main())
