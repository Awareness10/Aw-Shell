"""
PySide6 Shell entry point — test runner for the new implementation.

Usage:
    python main_pyside6.py
"""

import sys
import os

# Ensure config module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QScreen

from core.state import ShellState
from core.hyprland import HyprlandListener
from core.occlusion import OcclusionMonitor
from surfaces.bar import create_bar_surfaces, get_bar_stylesheet
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


def main():
    app = QApplication(sys.argv)

    # Create state bus
    state = ShellState()

    # Get screens
    screens = app.screens()
    if not screens:
        print("No screens available")
        return 1

    # Theme (mock for now)
    theme = MockTheme()

    # Build stylesheet
    stylesheet = (
        get_bar_stylesheet(theme) +
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

    # Notch (primary screen only for now)
    notch_surface = create_notch_surface(state, screens[0])
    surfaces.append(notch_surface)
    notch_surface.show()

    # Start Hyprland listener (auto-connects on init)
    hypr = HyprlandListener(state)

    # Start occlusion monitor
    occlusion = OcclusionMonitor(state)
    occlusion.register("bar", "top", 48)
    occlusion.register("notch", "top", 400)
    occlusion.start()

    print(f"PySide6 shell running on {len(screens)} screen(s)", flush=True)
    print("Click the compact bar to open dashboard. Press Escape to close.", flush=True)
    print("Bar buttons: Apps, Overview, Tools, Power", flush=True)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
