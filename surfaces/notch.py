"""
PySide6 notch surface — port of modules/notch.py.

The notch is the central UI hub containing:
- Compact view (resting state): clock, media info, active window
- Expanded views via AnimatedStack: dashboard, launcher, power, etc.

Uses OverlaySurface with slide animations matching the Fabric version.
"""

from datetime import datetime as dt
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QFont, QScreen
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QVBoxLayout, QWidget, QFrame,
    QSizePolicy,
)

from core.animator import Animator, AnimatedStack, SPRING, SMOOTH
from core.surface import OverlaySurface, Anchor, Layer, KeyboardInteractivity
from views.dashboard import Dashboard
from views.launcher import Launcher
from views.power import PowerMenu
from views.overview import Overview
from views.tools import Toolbox
from views.emoji import EmojiPicker


def _icon_font(size: int = 14) -> QFont:
    f = QFont("tabler-icons")
    f.setPixelSize(size)
    return f


class CompactView(QWidget):
    """Resting state of the notch — shows clock and media info.

    Mirrors the Fabric compact_stack with slide-up-down transitions
    between user label, active window, player info, volume, mic.
    """

    clicked = Signal()
    scroll_up = Signal()
    scroll_down = Signal()

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.setObjectName("notch-compact")
        self._state = state

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Left: active window / user info (placeholder)
        self.info_label = QLabel("")
        self.info_label.setObjectName("compact-info")
        layout.addWidget(self.info_label)

        layout.addStretch()

        # Center: clock
        self.clock = QLabel()
        self.clock.setObjectName("compact-clock")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.clock)

        layout.addStretch()

        # Right: media info (placeholder)
        self.media_label = QLabel("")
        self.media_label.setObjectName("compact-media")
        layout.addWidget(self.media_label)

        # Clock timer
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start()
        self._update_clock()

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _update_clock(self):
        fmt = self._state.get("datetime_12h_format", False)
        if fmt:
            self.clock.setText(dt.now().strftime("%I:%M %p"))
        else:
            self.clock.setText(dt.now().strftime("%H:%M"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.scroll_up.emit()
        else:
            self.scroll_down.emit()
        super().wheelEvent(event)


class PlaceholderView(QWidget):
    """Placeholder for views not yet implemented (dashboard, launcher, etc.)."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(f"view-{name}")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(f"{name.title()} View")
        label.setObjectName("placeholder-label")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        hint = QLabel("(Phase 5 implementation)")
        hint.setObjectName("placeholder-hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)


class Notch(QWidget):
    """Notch content widget — placed inside a NotchSurface.

    Contains the AnimatedStack that switches between compact view
    and expanded modules (dashboard, launcher, power, etc.).
    """

    # Emitted when notch opens/closes for coordination with bar/dock
    opened = Signal(str)   # module name
    closed = Signal()

    # Module name -> stack index mapping
    MODULES = {
        "compact": 0,
        "dashboard": 1,
        "launcher": 2,
        "power": 3,
        "overview": 4,
        "tools": 5,
        "emoji": 6,
        "cliphist": 7,
        "tmux": 8,
    }

    def __init__(self, state, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("notch-box")
        self._state = state
        self._vertical = vertical
        self._is_open = False
        self._current_module = "compact"
        self._anim = None  # prevent GC

        # --- Build UI ---
        layout = QVBoxLayout(self) if not vertical else QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main content stack
        self.stack = AnimatedStack()
        self.stack.setObjectName("notch-content")
        self.stack.transition_duration = 250
        self.stack.transition_type = "crossfade"

        # Add views to stack
        self.compact = CompactView(state)
        self.compact.clicked.connect(lambda: self.open_notch("dashboard"))

        self.dashboard = Dashboard(state, vertical=vertical)
        self.launcher = Launcher(state, on_close=self.close_notch)
        self.power = PowerMenu(state, on_close=self.close_notch, vertical=vertical)
        self.overview = Overview(state, on_close=self.close_notch)
        self.tools = Toolbox(state, on_close=self.close_notch, vertical=vertical)
        self.emoji = EmojiPicker(state, on_close=self.close_notch, vertical=vertical)
        self.cliphist = PlaceholderView("cliphist")
        self.tmux = PlaceholderView("tmux")

        self.stack.addWidget(self.compact)      # 0
        self.stack.addWidget(self.dashboard)    # 1
        self.stack.addWidget(self.launcher)     # 2
        self.stack.addWidget(self.power)        # 3
        self.stack.addWidget(self.overview)     # 4
        self.stack.addWidget(self.tools)        # 5
        self.stack.addWidget(self.emoji)        # 6
        self.stack.addWidget(self.cliphist)     # 7
        self.stack.addWidget(self.tmux)         # 8

        layout.addWidget(self.stack)

        # Connect state signals
        state.notch_opened.connect(self.open_notch)

        # Size policy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def open_notch(self, module: str):
        """Open the notch to a specific module, or toggle if already open."""
        print(f"[Notch] open_notch called with module: {module}")
        if module not in self.MODULES:
            module = "dashboard"

        # Toggle behavior: if same module clicked, close
        if self._is_open and self._current_module == module:
            self.close_notch()
            return

        self._is_open = True
        self._current_module = module

        # Switch stack
        idx = self.MODULES[module]
        self.stack.switch_to(idx)

        # Module-specific initialization
        if module == "launcher":
            self.launcher.open()
        elif module == "overview":
            self.overview.open()
        elif module == "emoji":
            self.emoji.open()

        # Add open style class
        self.setProperty("open", True)
        self.style().unpolish(self)
        self.style().polish(self)

        self.opened.emit(module)

    def close_notch(self):
        """Return to compact view."""
        import traceback
        print(f"[Notch] close_notch called, is_open={self._is_open}", flush=True)
        print("".join(traceback.format_stack()[-5:-1]), flush=True)
        if not self._is_open:
            return

        self._is_open = False
        self._current_module = "compact"

        # Switch back to compact
        self.stack.switch_to(0)

        # Remove open style class
        self.setProperty("open", False)
        self.style().unpolish(self)
        self.style().polish(self)

        self.closed.emit()
        self._state.notch_closed.emit()

    @property
    def is_open(self) -> bool:
        return self._is_open


class NotchSurface(OverlaySurface):
    """Layer-shell surface containing the Notch widget.

    Handles:
    - Positioning based on theme (Notch vs Panel) and bar position
    - Slide reveal animation
    - Keyboard interactivity switching
    - Occlusion coordination
    """

    def __init__(
        self,
        state,
        screen: Optional[QScreen] = None,
        parent=None,
    ):
        # Determine position and anchors from config
        panel_theme = state.get("panel_theme", "Notch")
        bar_position = state.get("bar_position", "Top")
        panel_position = state.get("panel_position", "Center")
        vertical = bar_position in ("Left", "Right")

        # Calculate anchors based on theme and position
        if panel_theme == "Notch":
            # Notch theme: always top-center
            anchors = Anchor.TOP | Anchor.LEFT | Anchor.RIGHT
            self._slide_direction = "down"
            margins = (0, 0, 0, 0)
        else:
            # Panel theme: follows bar position
            if bar_position == "Top":
                anchors = Anchor.TOP | Anchor.LEFT | Anchor.RIGHT
                self._slide_direction = "down"
            elif bar_position == "Bottom":
                anchors = Anchor.BOTTOM | Anchor.LEFT | Anchor.RIGHT
                self._slide_direction = "up"
            elif bar_position == "Left":
                anchors = Anchor.LEFT | Anchor.TOP | Anchor.BOTTOM
                self._slide_direction = "right"
            else:  # Right
                anchors = Anchor.RIGHT | Anchor.TOP | Anchor.BOTTOM
                self._slide_direction = "left"
            margins = (0, 0, 0, 0)

        super().__init__(
            anchors=anchors,
            layer=Layer.OVERLAY,
            keyboard=KeyboardInteractivity.NONE,
            screen=screen,
            margins=margins,
        )

        self._state = state
        self._vertical = vertical
        self._is_revealed = True
        self._forced_occlusion = False

        # Build content
        self.notch = Notch(state, vertical=vertical)
        self.content_layout.addWidget(self.notch)

        # Connect signals
        self.notch.opened.connect(self._on_opened)
        self.notch.closed.connect(self._on_closed)
        state.occlusion_changed.connect(self._on_occlusion)

        # Style
        self.setObjectName("notch-surface")

    def _on_opened(self, module: str):
        """When notch opens, grab keyboard."""
        self.set_keyboard_interactivity(KeyboardInteractivity.EXCLUSIVE)
        self._reveal(True)

    def _on_closed(self):
        """When notch closes, release keyboard."""
        self.set_keyboard_interactivity(KeyboardInteractivity.NONE)

    def _on_occlusion(self, surface_id: str, occluded: bool):
        """Handle occlusion changes from OcclusionMonitor."""
        if surface_id != "notch":
            return

        if self._forced_occlusion:
            return

        if occluded and not self.notch.is_open:
            self._reveal(False)
        elif not occluded:
            self._reveal(True)

    def _reveal(self, show: bool):
        """Animate notch reveal/hide."""
        if show == self._is_revealed:
            return

        self._is_revealed = show
        # For now just show/hide — slide animation can be added
        # by animating margins or using a revealer pattern
        self.setVisible(show)

    def force_occlusion(self):
        """Force hide for bar toggle coordination."""
        self._forced_occlusion = True
        if not self.notch.is_open:
            self._reveal(False)

    def restore_from_occlusion(self):
        """Restore normal occlusion behavior."""
        self._forced_occlusion = False
        self._reveal(True)

    def keyPressEvent(self, event):
        """Handle Escape to close notch."""
        print(f"[NotchSurface] keyPressEvent: key={event.key()}, Qt.Key_Escape={Qt.Key.Key_Escape}", flush=True)
        if event.key() == Qt.Key.Key_Escape:
            self.notch.close_notch()
        else:
            super().keyPressEvent(event)


def get_notch_stylesheet(theme: object) -> str:
    """Generate notch-specific stylesheet from a Glaze Theme."""
    t = theme
    return f"""
        #notch-surface {{
            background: transparent;
        }}
        #notch-box {{
            background: {t.surface};
            border-radius: 0 0 16px 16px;
            min-height: 40px;
        }}
        #notch-box[open="true"] {{
            min-height: 400px;
            min-width: 500px;
        }}
        #notch-compact {{
            background: transparent;
        }}
        #compact-clock {{
            color: {t.text_primary};
            font-size: 14px;
            font-weight: 600;
        }}
        #compact-info, #compact-media {{
            color: {t.text_secondary};
            font-size: 12px;
        }}
        #placeholder-label {{
            color: {t.text_primary};
            font-size: 18px;
            font-weight: 600;
        }}
        #placeholder-hint {{
            color: {t.text_secondary};
            font-size: 12px;
        }}
    """


def create_notch_surface(
    state,
    screen: QScreen,
) -> NotchSurface:
    """Create a notch surface for a monitor."""
    return NotchSurface(state=state, screen=screen)
