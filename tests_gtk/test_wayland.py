"""WaylandWindow's layer-shell properties must reach gtk-layer-shell.

The enum types are GtkLayerShell's own C-registered enums. PyGObject 3.51+
makes them plain IntEnums without a GType, which fabric's Property couldn't
handle; Aw-Shell uses the Awareness10/fabric fork, which can.
"""

import pytest
from gi.repository import GtkLayerShell

from widgets.wayland import Edge, KeyboardMode, Layer, WaylandWindow


def test_enums_are_gtk_layer_shell_types():
    assert Layer is GtkLayerShell.Layer
    assert KeyboardMode is GtkLayerShell.KeyboardMode
    assert Edge is GtkLayerShell.Edge


def test_runs_on_pygobject_3_51_or_newer():
    # Guards against falling back to the old PyGObject 3.50.0 pin; the AUR
    # package runs on Arch's PyGObject, which is newer
    import gi

    assert gi.version_info >= (3, 51)


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
