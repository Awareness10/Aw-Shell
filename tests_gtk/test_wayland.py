"""WaylandWindow's layer-shell properties must reach gtk-layer-shell.

The enum types are GtkLayerShell's own C-registered enums; custom Python
GEnum subclasses broke with PyGObject 3.50. PyGObject 3.51+ rejects even these
as property types, which is why it is pinned to 3.50.0.
"""

import pytest
from gi.repository import GtkLayerShell

from widgets.wayland import Edge, KeyboardMode, Layer, WaylandWindow


def test_enums_are_gtk_layer_shell_types():
    assert Layer is GtkLayerShell.Layer
    assert KeyboardMode is GtkLayerShell.KeyboardMode
    assert Edge is GtkLayerShell.Edge


@pytest.fixture
def window(run_pending):
    windows = []

    def make(**kwargs):
        win = WaylandWindow(**kwargs)
        windows.append(win)
        run_pending()
        return win

    yield make
    for win in windows:
        win.destroy()
    run_pending()


@pytest.mark.parametrize("value, expected", [
    ("background", Layer.BACKGROUND),
    ("bottom", Layer.BOTTOM),
    ("top", Layer.TOP),
    ("overlay", Layer.OVERLAY),
    (Layer.OVERLAY, Layer.OVERLAY),
])
def test_layer(window, value, expected):
    win = window(layer=value)
    assert GtkLayerShell.get_layer(win) == expected
    assert win.layer == expected


@pytest.mark.parametrize("value, expected", [
    ("none", KeyboardMode.NONE),
    ("exclusive", KeyboardMode.EXCLUSIVE),
    ("on-demand", KeyboardMode.ON_DEMAND),
])
def test_keyboard_mode(window, value, expected):
    win = window(keyboard_mode=value)
    assert GtkLayerShell.get_keyboard_mode(win) == expected


def test_anchor(window):
    win = window(anchor="top left")
    assert set(win.anchor) == {Edge.TOP, Edge.LEFT}
    assert not GtkLayerShell.get_anchor(win, Edge.BOTTOM)
