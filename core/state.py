"""
Central state bus for the PySide6 shell.

All components connect to ShellState signals instead of directly
referencing each other. Replaces Fabric's service system, GObject
signals, and class-level instance tracking.
"""

from PySide6.QtCore import QObject, Signal

from config.settings_utils import get_bind_var, load_bind_vars


class ShellState(QObject):
    """Singleton signal bus for shell-wide state changes."""

    # Bar visibility toggled (True = visible)
    bar_toggled = Signal(bool)

    # Notch module opened/closed
    notch_opened = Signal(str)   # module name: "dashboard", "launcher", etc.
    notch_closed = Signal()

    # Theme changed (emitted after Matugen regenerates)
    theme_changed = Signal(object)  # Theme dataclass

    # Hyprland workspace events
    workspace_changed = Signal(int)     # workspace id
    monitor_focused = Signal(str)       # monitor name

    # Occlusion state per surface
    occlusion_changed = Signal(str, bool)  # surface_id, is_occluded

    # Fullscreen window state
    fullscreen_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        load_bind_vars()
        self._bar_visible = True

    def get(self, key: str, default=None):
        return get_bind_var(key, default)

    def toggle_bar(self):
        self._bar_visible = not self._bar_visible
        self.bar_toggled.emit(self._bar_visible)

    @property
    def bar_visible(self) -> bool:
        return self._bar_visible
