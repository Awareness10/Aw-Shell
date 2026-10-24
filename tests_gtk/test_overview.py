"""Overview window actions must use Hyprland's Lua dispatch syntax.

Since Hyprland 0.56 (Lua config), `dispatch` takes a Lua expression;
the old `focuswindow address:...` form fails with a Lua syntax error.
"""

from types import SimpleNamespace

import pytest
from gi.repository import Gdk

ADDRESS = "0x1"  # the window in tests_gtk/fake_hyprland.py

FOCUS = f'/dispatch hl.dsp.focus({{ window = "address:{ADDRESS}" }})'
CLOSE = f'/dispatch hl.dsp.window.close({{ window = "address:{ADDRESS}" }})'


@pytest.fixture
def button(sandbox, run_pending):
    from modules.overview import Overview

    overview = Overview(monitor_id=0)
    overview.update()
    run_pending()
    sandbox.hyprland.log.clear()
    yield overview.clients[ADDRESS]
    overview.destroy()


def dispatches(sandbox):
    return [c for c in sandbox.hyprland.log if c.startswith("/dispatch")]


def test_click_focuses_window(sandbox, button):
    button.clicked()
    assert dispatches(sandbox) == [FOCUS]


def test_right_click_closes_window(sandbox, button):
    event = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
    event.button.button = 3
    button.emit("button-press-event", event)
    assert dispatches(sandbox) == [CLOSE]


def test_left_press_does_not_close(sandbox, button):
    event = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
    event.button.button = 1
    button.emit("button-press-event", event)
    assert CLOSE not in dispatches(sandbox)


def test_shift_enter_closes_window(sandbox, button):
    event = SimpleNamespace(keyval=Gdk.KEY_Return,
                            get_state=lambda: Gdk.ModifierType.SHIFT_MASK)
    assert button.on_key_press_event(button, event) is True
    assert dispatches(sandbox) == [CLOSE]


def test_drop_moves_window_silently(sandbox):
    from modules.overview import WorkspaceEventBox

    box = WorkspaceEventBox(workspace_id=3)
    data = SimpleNamespace(get_data=lambda: ADDRESS.encode())
    box.on_drag_data_received(box, None, 0, 0, data)
    assert dispatches(sandbox) == [
        f'/dispatch hl.dsp.window.move({{ workspace = "3", window = "address:{ADDRESS}", '
        "follow = false })"
    ]
    box.destroy()


def test_screen_size_without_deprecated_api():
    """The fallback size spans all monitors, as Gdk.Screen.get_width/height
    did (deprecated); the sandbox has one 1920x1080 output."""
    import warnings

    from modules.overview import CURRENT_HEIGHT, CURRENT_WIDTH, _screen_size

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert _screen_size() == (1920, 1080)
    assert (CURRENT_WIDTH, CURRENT_HEIGHT) == (1920, 1080)
