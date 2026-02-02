"""
PySide6 dock surface — port of modules/dock.py.

Shows pinned and running application buttons on a DockSurface
with hover-reveal animation. Discovers running apps via Hyprland
IPC, resolves icons from the system icon theme + .desktop fallback.
"""

import configparser
import glob
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QTimer, Signal
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget, QFrame, QApplication,
)

from core.animator import Animator, SPRING
from core.hyprland import hyprctl, hyprctl_json
from core.surface import DockSurface


DOCK_JSON_PATH = Path(__file__).parent.parent / "config" / "dock.json"


def _load_pinned_apps() -> list[dict]:
    try:
        with open(DOCK_JSON_PATH) as f:
            data = json.load(f)
        return data.get("pinned_apps", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _build_class_to_icon_map() -> dict[str, str]:
    """Build window-class -> icon-name from .desktop files."""
    mapping = {}
    desktop_dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
    ]
    for d in desktop_dirs:
        for path in glob.glob(os.path.join(d, "*.desktop")):
            try:
                cp = configparser.ConfigParser(interpolation=None)
                cp.read(path)
                wm_class = cp.get("Desktop Entry", "StartupWMClass", fallback="")
                icon = cp.get("Desktop Entry", "Icon", fallback="")
                name = cp.get("Desktop Entry", "Name", fallback="")
                exe = cp.get("Desktop Entry", "Exec", fallback="")
                if wm_class and icon:
                    mapping[wm_class.lower()] = icon
                if name and icon:
                    mapping[name.lower()] = icon
                if exe:
                    exe_base = exe.split()[0].split("/")[-1].lower()
                    if exe_base and icon:
                        mapping[exe_base] = icon
            except Exception:
                pass
    return mapping


def _setup_icon_theme():
    """Ensure Qt picks up the system icon theme."""
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "icon-theme"],
            capture_output=True, text=True,
        )
        theme = result.stdout.strip().strip("'")
        if theme:
            QIcon.setThemeName(theme)
    except Exception:
        pass
    QIcon.setThemeSearchPaths([
        "/usr/share/icons",
        os.path.expanduser("~/.local/share/icons"),
        "/usr/share/pixmaps",
    ])


def _resolve_icon(window_class: str, class_to_icon: dict, size: int = 28) -> QIcon:
    """Resolve an icon for a window class, with desktop-file fallback."""
    # Direct theme lookup
    icon = QIcon.fromTheme(window_class)
    if not icon.isNull():
        return icon

    # Desktop file mapping
    icon_name = class_to_icon.get(window_class.lower(), "")
    if icon_name:
        icon = QIcon.fromTheme(icon_name)
        if not icon.isNull():
            return icon

    # Fallback
    return QIcon.fromTheme("application-x-executable")


class DockAppButton(QPushButton):
    """Single app button in the dock."""

    app_activated = Signal(str, list)  # window_class, [addresses]

    def __init__(
        self,
        window_class: str,
        icon: QIcon,
        instances: list[dict],
        display_name: str = "",
        icon_size: int = 28,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("dock-app-button")
        self.window_class = window_class
        self.instances = instances
        self._last_focused_idx = -1

        self.setIcon(icon)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedSize(icon_size + 12, icon_size + 12)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(display_name or window_class)

        # Running indicator
        self.setProperty("running", len(instances) > 0)
        self.setProperty("pinned", False)

        self.clicked.connect(self._on_click)

    def _on_click(self):
        self.app_activated.emit(self.window_class, self.instances)


class DockSeparator(QFrame):
    """Visual separator between pinned and running apps."""

    def __init__(self, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("dock-separator")
        if vertical:
            self.setFrameShape(QFrame.Shape.HLine)
            self.setFixedHeight(2)
            self.setMinimumWidth(20)
        else:
            self.setFrameShape(QFrame.Shape.VLine)
            self.setFixedWidth(2)
            self.setMinimumHeight(20)


class Dock(QWidget):
    """Dock content widget — placed inside a DockSurface.

    Manages pinned + running app buttons, icon resolution,
    and click-to-focus/launch behavior.
    """

    def __init__(
        self,
        state,
        vertical: bool = False,
        icon_size: int = 28,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("dock")
        self._state = state
        self._vertical = vertical
        self._icon_size = icon_size
        self._class_to_icon = _build_class_to_icon_map()
        self._buttons: list[DockAppButton] = []
        self._anim = None

        if vertical:
            self._layout = QVBoxLayout(self)
        else:
            self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(6, 4, 6, 4)
        self._layout.setSpacing(4)

        # Periodic refresh of running apps
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self.update_dock)

        # Listen for window open/close via hyprland events
        # (HyprlandListener emits workspace_changed on focus changes)
        state.workspace_changed.connect(lambda _: self.update_dock())

        self.update_dock()
        self._refresh_timer.start()

    def update_dock(self):
        """Rebuild dock buttons from pinned apps + running windows."""
        try:
            clients = hyprctl_json("clients")
        except Exception:
            return

        # Group running windows by class
        running: dict[str, list[dict]] = {}
        for c in clients:
            if not c.get("mapped", False):
                continue
            cls = c.get("class", "")
            if not cls:
                continue
            running.setdefault(cls, []).append(c)

        # Pinned apps
        pinned = _load_pinned_apps()
        pinned_classes: set[str] = set()
        new_buttons: list[QWidget] = []

        for app in pinned:
            if isinstance(app, dict):
                cls = app.get("window_class") or app.get("name") or ""
                display = app.get("display_name") or cls
            else:
                cls = str(app)
                display = cls

            if not cls:
                continue

            pinned_classes.add(cls.lower())
            instances = running.get(cls, [])
            icon = _resolve_icon(cls, self._class_to_icon, self._icon_size)

            btn = DockAppButton(
                window_class=cls,
                icon=icon,
                instances=instances,
                display_name=display,
                icon_size=self._icon_size,
            )
            btn.setProperty("pinned", True)
            btn.app_activated.connect(self._handle_app)
            new_buttons.append(btn)

        # Separator (only if both pinned and unpinned running apps exist)
        unpinned_running = {
            cls: insts for cls, insts in running.items()
            if cls.lower() not in pinned_classes
        }

        if pinned and unpinned_running:
            new_buttons.append(DockSeparator(vertical=self._vertical))

        # Unpinned running apps
        for cls, instances in unpinned_running.items():
            icon = _resolve_icon(cls, self._class_to_icon, self._icon_size)
            btn = DockAppButton(
                window_class=cls,
                icon=icon,
                instances=instances,
                display_name=cls,
                icon_size=self._icon_size,
            )
            btn.app_activated.connect(self._handle_app)
            new_buttons.append(btn)

        # Replace layout contents
        self._clear_layout()
        self._buttons.clear()
        for w in new_buttons:
            self._layout.addWidget(w)
            if isinstance(w, DockAppButton):
                self._buttons.append(w)

    def _clear_layout(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _handle_app(self, window_class: str, instances: list[dict]):
        """Focus next instance, or launch if not running."""
        if not instances:
            self._launch_app(window_class)
            return

        # Cycle through instances
        try:
            focused_addr = hyprctl_json("activewindow").get("address", "")
        except Exception:
            focused_addr = ""

        addrs = [i["address"] for i in instances]
        try:
            idx = addrs.index(focused_addr)
            next_idx = (idx + 1) % len(addrs)
        except ValueError:
            next_idx = 0

        hyprctl(f"dispatch focuswindow address:{addrs[next_idx]}")

    def _launch_app(self, window_class: str):
        """Launch an app by looking up its .desktop Exec line."""
        desktop_dirs = [
            "/usr/share/applications",
            os.path.expanduser("~/.local/share/applications"),
        ]
        for d in desktop_dirs:
            for path in glob.glob(os.path.join(d, "*.desktop")):
                try:
                    cp = configparser.ConfigParser(interpolation=None)
                    cp.read(path)
                    wm_class = cp.get("Desktop Entry", "StartupWMClass", fallback="")
                    if wm_class.lower() == window_class.lower():
                        exe = cp.get("Desktop Entry", "Exec", fallback="")
                        if exe:
                            # Strip field codes
                            cmd = exe.split("%")[0].strip()
                            subprocess.Popen(
                                ["nohup"] + cmd.split(),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=True,
                            )
                            return
                except Exception:
                    pass

        # Fallback: try window class as command
        subprocess.Popen(
            ["nohup", window_class],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def get_dock_stylesheet(theme: object) -> str:
    """Generate dock-specific stylesheet from a Glaze Theme."""
    t = theme
    return f"""
        #dock {{
            background: {t.surface};
            border-radius: 12px;
            padding: 2px;
        }}
        #dock-app-button {{
            background: transparent;
            border: none;
            border-radius: 8px;
            padding: 4px;
        }}
        #dock-app-button:hover {{
            background: {t.surface_variant};
        }}
        #dock-app-button[running="true"] {{
            border-bottom: 2px solid {t.accent};
        }}
        #dock-separator {{
            background: {t.outline};
            border: none;
        }}
    """


def create_dock_surfaces(
    state,
    screens: list,
) -> list[tuple[DockSurface, Dock]]:
    """Create a dock surface per monitor. Returns (surface, dock) pairs."""
    position = state.get("bar_position", "Top")
    dock_enabled = state.get("dock_enabled", True)
    always_show = state.get("dock_always_show", False)
    icon_size = state.get("dock_icon_size", 28)

    if not dock_enabled:
        return []

    # Dock goes on the opposite edge from the bar, or bottom by default
    edge_map = {"Top": "bottom", "Bottom": "top", "Left": "right", "Right": "left"}
    edge = edge_map.get(position, "bottom")
    vertical = edge in ("left", "right")

    _setup_icon_theme()

    results = []
    for screen in screens:
        surface = DockSurface(
            edge=edge,
            screen=screen,
            always_show=always_show,
        )

        dock = Dock(
            state=state,
            vertical=vertical,
            icon_size=icon_size,
        )
        surface.content_layout.addWidget(dock)

        # Wire reveal signal to dock animation
        surface.revealed.connect(
            lambda show, d=dock, s=surface: _animate_reveal(show, d, s, edge)
        )

        results.append((surface, dock))

    return results


def _animate_reveal(show: bool, dock: Dock, surface: DockSurface, edge: str):
    """Animate dock show/hide matching the Fabric 250ms slide."""
    # Map edge to slide direction
    direction_map = {
        "bottom": "down",
        "top": "up",
        "left": "left",
        "right": "right",
    }
    direction = direction_map.get(edge, "down")

    if show:
        dock.setVisible(True)
        dock._anim = Animator.group(
            Animator.fade(dock, 0.0, 1.0, 250, SPRING),
        )
    else:
        dock._anim = Animator.fade(dock, 1.0, 0.0, 250, SPRING)
        dock._anim.finished.connect(lambda: dock.setVisible(False))

    dock._anim.start()
