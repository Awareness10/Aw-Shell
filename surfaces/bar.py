"""
PySide6 bar surface — port of modules/bar.py.

Three-section layout (start/center/end) on a PanelSurface.
Supports horizontal and vertical orientation, theme variants
(Pills, Dense, Edge), component visibility, and toggle animation.

Complex Fabric widgets (Workspaces, SystemTray, Metrics, etc.) are
currently placeholder widgets — they'll be replaced with real
PySide6 implementations in later phases.
"""

from datetime import datetime as dt
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QScreen
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget,
)

from core.animator import Animator, SPRING
from core.surface import PanelSurface
from config.settings_utils import get_bind_var

RUNES = ["ᚠ", "ᚢ", "ᚦ", "ᚯ", "ᚱ", "ᚴ", "ᚼ", "ᚾ", "ᛁ", "ᛅ"]


def _icon_font() -> QFont:
    """Tabler Icons font for bar buttons."""
    f = QFont("tabler-icons")
    f.setPixelSize(20)
    return f


def _make_icon_button(icon_char: str, tooltip: str = "") -> QPushButton:
    btn = QPushButton(icon_char)
    btn.setFont(_icon_font())
    btn.setToolTip(tooltip)
    btn.setObjectName("button-bar")
    btn.setFixedSize(36, 36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _make_label(text: str, name: str = "") -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    return lbl


class WorkspaceIndicator(QWidget):
    """Placeholder workspace indicator — shows dots for 10 workspaces."""

    workspace_clicked = Signal(int)

    def __init__(self, vertical: bool = False, show_numbers: bool = False,
                 use_runes: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("workspaces-container")
        self._active_ws = 1
        self._vertical = vertical
        self._show_numbers = show_numbers
        self._use_runes = use_runes

        if vertical:
            self._layout = QVBoxLayout(self)
        else:
            self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(4 if use_runes else 6)

        self._buttons: list[QPushButton] = []
        for i in range(1, 11):
            if show_numbers:
                if use_runes and 0 <= (i - 1) < len(RUNES):
                    label = RUNES[i - 1]
                else:
                    label = str(i)
            else:
                label = ""

            btn = QPushButton(label)
            btn.setObjectName("ws-button")
            btn.setCheckable(True)
            if not show_numbers:
                btn.setFixedSize(8, 8)
            else:
                btn.setFixedSize(22, 22)
            btn.clicked.connect(lambda checked, ws=i: self.workspace_clicked.emit(ws))
            self._layout.addWidget(btn)
            self._buttons.append(btn)

        self.set_active(1)

    def set_active(self, ws_id: int):
        self._active_ws = ws_id
        for i, btn in enumerate(self._buttons):
            btn.setChecked((i + 1) == ws_id)


class DateTimeWidget(QLabel):
    """Clock widget matching the Fabric DateTime behavior."""

    def __init__(self, format_12h: bool = False, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("date-time")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if format_12h:
            self._fmt = "%I:%M %p" if not vertical else "%I\n%M\n%p"
        else:
            self._fmt = "%H:%M" if not vertical else "%H\n%M"

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update)
        self._timer.start()
        self._update()

    def _update(self):
        self.setText(dt.now().strftime(self._fmt))


class Bar(QWidget):
    """Bar content widget — placed inside a PanelSurface.

    Manages the three-section layout, widget creation, theming,
    and visibility toggling. One Bar instance per monitor.
    """

    def __init__(
        self,
        state,
        vertical: bool = False,
        monitor_name: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("bar-inner")
        self._state = state
        self._vertical = vertical
        self._monitor_name = monitor_name
        self._hidden = False
        self._anim = None  # prevent GC

        # Read config
        position = state.get("bar_position", "Top")
        show_numbers = state.get("bar_workspace_show_number", False)
        use_runes = state.get("bar_workspace_use_runes", False)
        format_12h = state.get("datetime_12h_format", False)
        theme = state.get("bar_theme", "Pills")
        visibility = state.get("bar_components_visibility", {})

        # --- Create widgets ---

        # Buttons
        # Using unicode codepoints from modules/icons.py (tabler-icons font)
        self.button_apps = _make_icon_button("\uf1fd", "Launcher")
        self.button_overview = _make_icon_button("\uefe6", "Overview")
        self.button_tools = _make_icon_button("\uebca", "Toolbox")
        self.button_power = _make_icon_button("\ueb0d", "Power Menu")

        self.button_apps.clicked.connect(lambda: (print("[Bar] Apps clicked", flush=True), state.notch_opened.emit("launcher")))
        self.button_overview.clicked.connect(lambda: (print("[Bar] Overview clicked", flush=True), state.notch_opened.emit("overview")))
        self.button_tools.clicked.connect(lambda: (print("[Bar] Tools clicked", flush=True), state.notch_opened.emit("tools")))
        self.button_power.clicked.connect(lambda: (print("[Bar] Power clicked", flush=True), state.notch_opened.emit("power")))

        # Workspaces
        self.workspaces = WorkspaceIndicator(
            vertical=vertical, show_numbers=show_numbers,
            use_runes=use_runes,
        )
        state.workspace_changed.connect(self.workspaces.set_active)

        # DateTime
        self.date_time = DateTimeWidget(format_12h=format_12h, vertical=vertical)

        # Placeholder widgets for complex components (Phase 5+)
        self.systray = _make_label("", "systray")
        self.weather = _make_label("", "weather")
        self.network = _make_label("", "network")
        self.battery = _make_label("", "battery")
        self.metrics = _make_label("", "metrics")
        self.control = _make_label("", "control")
        self.sysprofiles = _make_label("", "sysprofiles")
        self.language = _make_label("", "language")

        # --- Layout ---
        if vertical:
            self._build_vertical_layout()
        else:
            self._build_horizontal_layout()

        # --- Theme ---
        self._apply_theme(theme)

        # --- Component visibility ---
        self._apply_visibility(visibility)

        # --- Connect state ---
        state.bar_toggled.connect(self._on_bar_toggled)

    def _build_horizontal_layout(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        # Start section
        start = QHBoxLayout()
        start.setSpacing(4)
        start.addWidget(self.button_apps)
        start.addWidget(self.workspaces)
        start.addWidget(self.button_overview)
        start.addWidget(self.weather)
        start.addWidget(self.sysprofiles)
        start.addWidget(self.network)

        # Center (will hold dock in later phases)
        center = QHBoxLayout()
        center.addStretch()

        # End section
        end = QHBoxLayout()
        end.setSpacing(4)
        end.addWidget(self.metrics)
        end.addWidget(self.control)
        end.addWidget(self.battery)
        end.addWidget(self.systray)
        end.addWidget(self.button_tools)
        end.addWidget(self.language)
        end.addWidget(self.date_time)
        end.addWidget(self.button_power)

        layout.addLayout(start)
        layout.addLayout(center, 1)
        layout.addLayout(end)

    def _build_vertical_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        # Start section
        start = QVBoxLayout()
        start.setSpacing(4)
        start.addWidget(self.button_apps, 0, Qt.AlignmentFlag.AlignCenter)
        start.addWidget(self.systray, 0, Qt.AlignmentFlag.AlignCenter)
        start.addWidget(self.control, 0, Qt.AlignmentFlag.AlignCenter)
        start.addWidget(self.sysprofiles, 0, Qt.AlignmentFlag.AlignCenter)
        start.addWidget(self.network, 0, Qt.AlignmentFlag.AlignCenter)
        start.addWidget(self.button_tools, 0, Qt.AlignmentFlag.AlignCenter)

        # Center
        center = QVBoxLayout()
        center.setSpacing(4)
        center.addWidget(self.button_overview, 0, Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.workspaces, 0, Qt.AlignmentFlag.AlignCenter)
        center.addWidget(self.weather, 0, Qt.AlignmentFlag.AlignCenter)

        # End
        end = QVBoxLayout()
        end.setSpacing(4)
        end.addWidget(self.battery, 0, Qt.AlignmentFlag.AlignCenter)
        end.addWidget(self.metrics, 0, Qt.AlignmentFlag.AlignCenter)
        end.addWidget(self.language, 0, Qt.AlignmentFlag.AlignCenter)
        end.addWidget(self.date_time, 0, Qt.AlignmentFlag.AlignCenter)
        end.addWidget(self.button_power, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(start)
        layout.addStretch()
        layout.addLayout(center)
        layout.addStretch()
        layout.addLayout(end)

    def _apply_theme(self, theme: str):
        """Apply bar theme as a property for stylesheet selection."""
        theme_class = {
            "Pills": "pills",
            "Dense": "dense",
            "Edge": "edge",
        }.get(theme, "pills")
        self.setProperty("theme", theme_class)

    def _apply_visibility(self, visibility: dict):
        """Show/hide components based on config."""
        widget_map = {
            "button_apps": self.button_apps,
            "systray": self.systray,
            "control": self.control,
            "network": self.network,
            "button_tools": self.button_tools,
            "sysprofiles": self.sysprofiles,
            "button_overview": self.button_overview,
            "ws_container": self.workspaces,
            "weather": self.weather,
            "battery": self.battery,
            "metrics": self.metrics,
            "language": self.language,
            "date_time": self.date_time,
            "button_power": self.button_power,
        }
        for name, widget in widget_map.items():
            visible = visibility.get(name, True)
            widget.setVisible(visible)

    def _on_bar_toggled(self, visible: bool):
        """Animate bar show/hide — mirrors the Fabric toggle_hidden."""
        self._hidden = not visible
        if visible:
            self._anim = Animator.fade(self, 0.0, 1.0, 250, SPRING)
        else:
            self._anim = Animator.fade(self, 1.0, 0.0, 250, SPRING)
        self._anim.start()

    @property
    def hidden(self) -> bool:
        return self._hidden


def get_bar_stylesheet(theme: object) -> str:
    """Generate bar-specific stylesheet from a Glaze Theme.

    Pills theme: transparent bar, each component is a separate rounded pill.
    Matches styles/bar.css + styles/workspaces.css + styles/shadows.css.
    """
    t = theme
    # shadow = darkest bg for pills, surface_variant = lighter for hover
    shadow = t.surface
    surface = t.surface_variant
    accent = t.accent
    on_accent = t.on_accent
    fg = t.text_primary
    fg2 = t.text_secondary

    return f"""
        /* --- Bar container --- */
        #bar-inner {{
            margin: 8px;
        }}
        #bar-inner[theme="pills"] {{
            background: transparent;
        }}
        #bar-inner[theme="dense"] {{
            background: {shadow};
            border: 2px solid {surface};
            border-radius: 16px;
            padding: 4px;
        }}
        #bar-inner[theme="edge"] {{
            background: {shadow};
            border-bottom: 2px solid {surface};
            border-radius: 0px;
            padding: 4px;
        }}

        /* --- Buttons (each is a pill) --- */
        #button-bar {{
            background: {shadow};
            color: {accent};
            border: none;
            border-radius: 16px;
            padding: 4px;
            min-width: 28px;
            min-height: 28px;
            font-size: 20px;
        }}
        #button-bar:hover {{
            background: {surface};
        }}
        #button-bar:pressed {{
            background: {accent};
            color: {shadow};
        }}

        /* --- Workspaces pill --- */
        #workspaces-container {{
            background: {shadow};
            border-radius: 16px;
            padding: 4px;
        }}
        #ws-button {{
            background: {fg};
            border: none;
            border-radius: 16px;
            min-width: 8px;
            min-height: 8px;
            max-width: 8px;
            max-height: 8px;
        }}
        #ws-button:checked {{
            background: {accent};
            min-width: 48px;
            max-width: 48px;
            border-radius: 16px;
        }}

        /* --- Date/time pill --- */
        #date-time {{
            background: {shadow};
            border-radius: 16px;
            color: {fg};
            font-size: 13px;
            font-weight: 600;
            padding: 0 8px;
            min-height: 36px;
        }}

        /* --- Other widget pills (placeholders until real implementations) --- */
        #systray, #weather, #language, #network,
        #battery, #metrics, #control, #sysprofiles {{
            background: {shadow};
            border-radius: 16px;
            min-height: 36px;
            padding: 0 8px;
        }}
    """


def create_bar_surfaces(
    state,
    screens: list[QScreen],
) -> list[tuple[PanelSurface, Bar]]:
    """Create a bar surface per monitor. Returns (surface, bar) pairs."""
    position = state.get("bar_position", "Top")
    vertical = position in ("Left", "Right")
    edge = position.lower()
    size = 40 if not vertical else 48

    results = []
    for screen in screens:
        surface = PanelSurface(
            edge=edge,
            size=size,
            screen=screen,
        )

        bar = Bar(
            state=state,
            vertical=vertical,
            monitor_name=screen.name(),
        )
        surface.content_layout.addWidget(bar)
        results.append((surface, bar))

    return results
