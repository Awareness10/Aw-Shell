"""
Shell surfaces using KDE's layer-shell-qt via ctypes.

Provides the base surface types for the PySide6 shell:
- ShellSurface: base class with layer-shell integration
- PanelSurface: anchored to edge, reserves exclusive zone (bar)
- OverlaySurface: floats above windows (notch, launcher, dashboard)
- DockSurface: auto-hide edge surface with hover reveal (dock)
"""

import ctypes
import os
from enum import IntEnum, IntFlag
from typing import Optional

import shiboken6
from PySide6.QtCore import QMargins, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QWidget, QVBoxLayout

os.environ.setdefault("QT_WAYLAND_SHELL_INTEGRATION", "layer-shell")

_lib = ctypes.CDLL("libLayerShellQtInterface.so.6")

# LayerShellQt::Window::get(QWindow*)
_window_get = _lib._ZN12LayerShellQt6Window3getEP7QWindow
_window_get.argtypes = [ctypes.c_void_p]
_window_get.restype = ctypes.c_void_p

# LayerShellQt::Shell::useLayerShell()
_use_layer_shell = _lib._ZN12LayerShellQt5Shell13useLayerShellEv
_use_layer_shell.argtypes = []
_use_layer_shell.restype = None

# void setLayer(Layer)
_set_layer = _lib._ZN12LayerShellQt6Window8setLayerENS0_5LayerE
_set_layer.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_set_layer.restype = None

# void setAnchors(QFlags<Anchor>)
_set_anchors = _lib._ZN12LayerShellQt6Window10setAnchorsE6QFlagsINS0_6AnchorEE
_set_anchors.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_set_anchors.restype = None

# void setExclusiveZone(int32_t)
_set_exclusive_zone = _lib._ZN12LayerShellQt6Window16setExclusiveZoneEi
_set_exclusive_zone.argtypes = [ctypes.c_void_p, ctypes.c_int32]
_set_exclusive_zone.restype = None

# void setExclusiveEdge(Anchor)
_set_exclusive_edge = _lib._ZN12LayerShellQt6Window16setExclusiveEdgeENS0_6AnchorE
_set_exclusive_edge.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_set_exclusive_edge.restype = None

# void setKeyboardInteractivity(KeyboardInteractivity)
_set_keyboard = _lib._ZN12LayerShellQt6Window24setKeyboardInteractivityENS0_21KeyboardInteractivityE
_set_keyboard.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_set_keyboard.restype = None

# void setScope(const QString&) — skipped, uses complex ABI
# void setDesiredSize(const QSize&) — skipped, we use QWidget.resize()
# void setMargins(const QMargins&) — needs struct passing, handled below

# For setMargins we pass a QMargins struct (4x int32)
class _QMarginsStruct(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int32),
        ("top", ctypes.c_int32),
        ("right", ctypes.c_int32),
        ("bottom", ctypes.c_int32),
    ]

_set_margins = _lib._ZN12LayerShellQt6Window10setMarginsERK8QMargins
_set_margins.argtypes = [ctypes.c_void_p, ctypes.POINTER(_QMarginsStruct)]
_set_margins.restype = None

# void setActivateOnShow(bool)
_set_activate_on_show = _lib._ZN12LayerShellQt6Window17setActivateOnShowEb
_set_activate_on_show.argtypes = [ctypes.c_void_p, ctypes.c_bool]
_set_activate_on_show.restype = None

# void setCloseOnDismissed(bool)
_set_close_on_dismissed = _lib._ZN12LayerShellQt6Window19setCloseOnDismissedEb
_set_close_on_dismissed.argtypes = [ctypes.c_void_p, ctypes.c_bool]
_set_close_on_dismissed.restype = None


def init_layer_shell():
    """Call once before creating any QApplication."""
    _use_layer_shell()


class Layer(IntEnum):
    BACKGROUND = 0
    BOTTOM = 1
    TOP = 2
    OVERLAY = 3


class Anchor(IntFlag):
    NONE = 0
    TOP = 1
    BOTTOM = 2
    LEFT = 4
    RIGHT = 8


class KeyboardInteractivity(IntEnum):
    NONE = 0
    EXCLUSIVE = 1
    ON_DEMAND = 2


# Convenience anchor combinations
ANCHOR_FILL_TOP = Anchor.TOP | Anchor.LEFT | Anchor.RIGHT
ANCHOR_FILL_BOTTOM = Anchor.BOTTOM | Anchor.LEFT | Anchor.RIGHT
ANCHOR_FILL_LEFT = Anchor.LEFT | Anchor.TOP | Anchor.BOTTOM
ANCHOR_FILL_RIGHT = Anchor.RIGHT | Anchor.TOP | Anchor.BOTTOM
ANCHOR_ALL = Anchor.TOP | Anchor.BOTTOM | Anchor.LEFT | Anchor.RIGHT


class ShellSurface(QWidget):
    """Base class for all layer-shell surfaces.

    Wraps a QWidget with KDE layer-shell-qt configuration.
    Must call `show()` to create the QWindow before layer-shell
    properties take effect.
    """

    surface_ready = Signal()

    def __init__(
        self,
        layer: Layer = Layer.TOP,
        anchors: Anchor = Anchor.NONE,
        exclusive_zone: int = 0,
        keyboard: KeyboardInteractivity = KeyboardInteractivity.NONE,
        margins: tuple[int, int, int, int] = (0, 0, 0, 0),
        screen: Optional[QScreen] = None,
        activate_on_show: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._layer = layer
        self._anchors = anchors
        self._exclusive_zone = exclusive_zone
        self._keyboard = keyboard
        self._margins = margins
        self._screen = screen
        self._activate_on_show = activate_on_show
        self._layer_window_ptr: Optional[int] = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self._content_layout = QVBoxLayout(self)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def show(self):
        """Show the surface and apply layer-shell configuration."""
        # Force QWindow creation before show so we can set screen
        self.winId()

        if self._screen:
            qwindow = self.windowHandle()
            if qwindow:
                qwindow.setScreen(self._screen)

        super().show()
        self._apply_layer_shell()

    def _apply_layer_shell(self):
        """Apply layer-shell properties via ctypes."""
        qwindow = self.windowHandle()
        if qwindow is None:
            return

        ptr = shiboken6.getCppPointer(qwindow)[0]
        self._layer_window_ptr = _window_get(ptr)

        if not self._layer_window_ptr:
            return

        p = self._layer_window_ptr
        _set_layer(p, self._layer.value)
        _set_anchors(p, int(self._anchors))
        _set_exclusive_zone(p, self._exclusive_zone)
        _set_keyboard(p, self._keyboard.value)
        _set_activate_on_show(p, self._activate_on_show)
        _set_close_on_dismissed(p, False)

        m = _QMarginsStruct(
            left=self._margins[3],
            top=self._margins[0],
            right=self._margins[1],
            bottom=self._margins[2],
        )
        _set_margins(p, ctypes.byref(m))

        self.surface_ready.emit()

    def set_layer(self, layer: Layer):
        self._layer = layer
        if self._layer_window_ptr:
            _set_layer(self._layer_window_ptr, layer.value)

    def set_anchors(self, anchors: Anchor):
        self._anchors = anchors
        if self._layer_window_ptr:
            _set_anchors(self._layer_window_ptr, int(anchors))

    def set_exclusive_zone(self, zone: int):
        self._exclusive_zone = zone
        if self._layer_window_ptr:
            _set_exclusive_zone(self._layer_window_ptr, zone)

    def set_keyboard_interactivity(self, mode: KeyboardInteractivity):
        self._keyboard = mode
        if self._layer_window_ptr:
            _set_keyboard(self._layer_window_ptr, mode.value)

    def set_margins(self, top: int = 0, right: int = 0, bottom: int = 0, left: int = 0):
        self._margins = (top, right, bottom, left)
        if self._layer_window_ptr:
            m = _QMarginsStruct(left=left, top=top, right=right, bottom=bottom)
            _set_margins(self._layer_window_ptr, ctypes.byref(m))


class PanelSurface(ShellSurface):
    """Surface anchored to a screen edge that reserves exclusive space.

    Used for the bar. Stretches across the full edge and pushes
    windows away by its height/width.
    """

    def __init__(
        self,
        edge: str = "top",
        size: int = 40,
        screen: Optional[QScreen] = None,
        margins: tuple[int, int, int, int] = (0, 0, 0, 0),
        parent: Optional[QWidget] = None,
    ):
        anchor_map = {
            "top": ANCHOR_FILL_TOP,
            "bottom": ANCHOR_FILL_BOTTOM,
            "left": ANCHOR_FILL_LEFT,
            "right": ANCHOR_FILL_RIGHT,
        }
        anchors = anchor_map.get(edge, ANCHOR_FILL_TOP)

        super().__init__(
            layer=Layer.TOP,
            anchors=anchors,
            exclusive_zone=size,
            keyboard=KeyboardInteractivity.NONE,
            margins=margins,
            screen=screen,
            parent=parent,
        )

        self._edge = edge
        self._size = size

        if edge in ("top", "bottom"):
            self.setFixedHeight(size)
        else:
            self.setFixedWidth(size)


class OverlaySurface(ShellSurface):
    """Surface floating above windows without reserving space.

    Used for the notch, launcher, dashboard, power menu, etc.
    Supports keyboard interactivity on demand for input fields.
    """

    def __init__(
        self,
        anchors: Anchor = Anchor.TOP | Anchor.LEFT | Anchor.RIGHT,
        layer: Layer = Layer.OVERLAY,
        keyboard: KeyboardInteractivity = KeyboardInteractivity.ON_DEMAND,
        screen: Optional[QScreen] = None,
        margins: tuple[int, int, int, int] = (0, 0, 0, 0),
        parent: Optional[QWidget] = None,
    ):
        super().__init__(
            layer=layer,
            anchors=anchors,
            exclusive_zone=0,
            keyboard=keyboard,
            margins=margins,
            screen=screen,
            activate_on_show=True,
            parent=parent,
        )

    def steal_input(self):
        self.set_keyboard_interactivity(KeyboardInteractivity.EXCLUSIVE)

    def return_input(self):
        self.set_keyboard_interactivity(KeyboardInteractivity.ON_DEMAND)


class DockSurface(OverlaySurface):
    """Auto-hide surface with hover reveal.

    Used for the dock. Shows a thin input region at the edge;
    when hovered, reveals the full dock. Hides after a delay
    when the mouse leaves.
    """

    revealed = Signal(bool)

    HOVER_HIDE_DELAY = 250  # ms, matches current Fabric implementation

    def __init__(
        self,
        edge: str = "bottom",
        screen: Optional[QScreen] = None,
        margins: tuple[int, int, int, int] = (0, 0, 0, 0),
        always_show: bool = False,
        parent: Optional[QWidget] = None,
    ):
        anchor_map = {
            "top": ANCHOR_FILL_TOP,
            "bottom": ANCHOR_FILL_BOTTOM,
            "left": ANCHOR_FILL_LEFT,
            "right": ANCHOR_FILL_RIGHT,
        }
        anchors = anchor_map.get(edge, ANCHOR_FILL_BOTTOM)

        super().__init__(
            anchors=anchors,
            layer=Layer.TOP,
            keyboard=KeyboardInteractivity.NONE,
            screen=screen,
            margins=margins,
            parent=parent,
        )

        self._edge = edge
        self._always_show = always_show
        self._is_hovered = False
        self._forced_occlusion = False
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(self.HOVER_HIDE_DELAY)
        self._hide_timer.timeout.connect(self._on_hide_timeout)

        self.setMouseTracking(True)

    @property
    def always_show(self) -> bool:
        return self._always_show

    @always_show.setter
    def always_show(self, value: bool):
        self._always_show = value

    def enterEvent(self, event):
        self._is_hovered = True
        self._hide_timer.stop()
        self.revealed.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        if not self._always_show:
            self._hide_timer.start()
        super().leaveEvent(event)

    def _on_hide_timeout(self):
        if not self._is_hovered and not self._always_show:
            self.revealed.emit(False)

    def force_occlusion(self):
        self._forced_occlusion = True
        if not self._is_hovered:
            self.revealed.emit(False)

    def restore_from_occlusion(self):
        self._forced_occlusion = False
        if self._always_show:
            self.revealed.emit(True)
