"""What each open_notch() view name does, on a real Notch.

Behaviour of Notch._open_notch_internal(name), with the default layout
(Notch theme, bar at the top). Every call first reveals the notch and adds
the "open" style class to notch_box and stack.

| name           | stack child | dashboard section/applet | on open                    | hide |
|----------------|-------------|--------------------------|----------------------------|------|
| dashboard      | dashboard   | widgets / nhistory       | -                          | yes  |
| bluetooth      | dashboard   | widgets / btdevices      | -                          | yes  |
| network_applet | dashboard   | widgets / nwconnections  | -                          | yes  |
| pins           | dashboard   | pins                     | -                          | yes  |
| kanban         | dashboard   | kanban                   | -                          | yes  |
| wallpapers     | dashboard   | wallpapers               | -                          | yes  |
| mixer          | dashboard   | mixer                    | -                          | yes  |
| tmux           | tmux        | -                        | tmux.open_manager()        | no   |
| cliphist       | cliphist    | -                        | idle: cliphist.open()      | no   |
| launcher       | launcher    | -                        | open_launcher(); clear +   | no   |
|                |             |                          | focus search               |      |
| emoji          | emoji       | -                        | open_picker(); clear +     | no   |
|                |             |                          | focus search               |      |
| overview       | overview    | -                        | -                          | yes  |
| power          | power       | -                        | -                          | no   |
| tools          | tools       | -                        | -                          | no   |
| (unknown)      | dashboard   | unchanged                | -                          | yes  |

"hide" = hide the bar side revealers.

Opening a view: keyboard mode "exclusive", stack child set, on-open actions,
dashboard section (and applet), bar side revealers shown unless "hide"
(always shown for a Panel at top/bottom or a Notch with a bottom bar),
margin "0px 8px 8px 8px" if the bar is hidden at the top, then open.

Toggle: opening the view that is already showing closes the notch. For a
non-dashboard view that is "the stack shows it"; for a dashboard section, the
dashboard shows that section; for an applet, the dashboard shows the widgets
section with that applet. An unknown name never closes.

Applets while the dashboard is already showing (another section or applet)
switch in place: keyboard "exclusive", widgets section, applet - nothing
else (no bar revealers, margin or open-state changes). A dashboard section
in that case goes the full open path.
"""

from unittest.mock import MagicMock

import pytest
from conftest import pump, pump_until


@pytest.fixture(scope="module")
def built_notch():
    """One Notch for the module (building one is slow); reset per test."""
    from modules.notch import Notch

    notch = Notch(monitor_id=0)
    notch.bar = MagicMock(name="bar")
    modes = []
    real_set_keyboard_mode = notch.set_keyboard_mode
    notch.set_keyboard_mode = lambda mode: (modes.append(mode), real_set_keyboard_mode(mode))
    notch.keyboard_modes = modes
    # On-open actions with side effects: record them instead
    notch.tmux.open_manager = MagicMock(name="open_manager")
    notch.cliphist.open = MagicMock(name="cliphist_open", return_value=False)
    notch.launcher.open_launcher = MagicMock(name="open_launcher")
    notch.emoji.open_picker = MagicMock(name="open_picker")
    pump()
    yield notch
    notch.destroy()
    pump()


@pytest.fixture
def notch(built_notch):
    notch = built_notch
    notch.close_notch()
    pump()
    for mock in (notch.bar, notch.tmux.open_manager, notch.cliphist.open,
                 notch.launcher.open_launcher, notch.emoji.open_picker):
        mock.reset_mock()
    notch.bar.get_visible.return_value = True
    notch.cliphist.open.return_value = False
    del notch.keyboard_modes[:]
    return notch


def views(notch):
    d = notch.dashboard
    return {
        # name: (stack child, dashboard section, applet, hide bar revealers)
        "dashboard": (d, d.widgets, notch.nhistory, True),
        "bluetooth": (d, d.widgets, notch.btdevices, True),
        "network_applet": (d, d.widgets, notch.nwconnections, True),
        "pins": (d, d.pins, None, True),
        "kanban": (d, d.kanban, None, True),
        "wallpapers": (d, d.wallpapers, None, True),
        "mixer": (d, d.mixer, None, True),
        "tmux": (notch.tmux, None, None, False),
        "cliphist": (notch.cliphist, None, None, False),
        "launcher": (notch.launcher, None, None, False),
        "emoji": (notch.emoji, None, None, False),
        "overview": (notch.overview, None, None, True),
        "power": (notch.power, None, None, False),
        "tools": (notch.tools, None, None, False),
    }


NAMES = ["dashboard", "bluetooth", "network_applet", "pins", "kanban", "wallpapers", "mixer",
         "tmux", "cliphist", "launcher", "emoji", "overview", "power", "tools"]


def is_closed(notch):
    return notch.stack.get_visible_child() == notch.compact and not notch._is_notch_open


@pytest.mark.parametrize("name", NAMES)
def test_open_then_toggle_closed(notch, name, run_pending):
    child, section, applet, hide = views(notch)[name]
    notch.launcher.search_entry.set_text("typed")
    notch.emoji.search_entry.set_text("typed")
    assert is_closed(notch)

    notch._open_notch_internal(name)
    run_pending()

    assert notch.stack.get_visible_child() == child
    assert notch._is_notch_open
    assert notch.keyboard_modes == ["exclusive"]
    assert notch.notch_box.get_style_context().has_class("open")
    assert notch.stack.get_style_context().has_class("open")
    if section is not None:
        assert notch.dashboard.stack.get_visible_child() == section
    if applet is not None:
        assert notch.applet_stack.get_visible_child() == applet
    notch.bar.revealer_right.set_reveal_child.assert_called_with(not hide)
    notch.bar.revealer_left.set_reveal_child.assert_called_with(not hide)

    assert notch.tmux.open_manager.call_count == (name == "tmux")
    assert notch.launcher.open_launcher.call_count == (name == "launcher")
    assert notch.emoji.open_picker.call_count == (name == "emoji")
    if name == "cliphist":
        assert pump_until(lambda: notch.cliphist.open.called)
    else:
        notch.cliphist.open.assert_not_called()
    assert notch.launcher.search_entry.get_text() == ("" if name == "launcher" else "typed")
    assert notch.emoji.search_entry.get_text() == ("" if name == "emoji" else "typed")

    # Same name again closes the notch
    notch._open_notch_internal(name)
    run_pending()
    assert is_closed(notch)
    assert notch.keyboard_modes == ["exclusive", "none"]
    assert notch.applet_stack.get_visible_child() == notch.nhistory
    assert not notch.notch_box.get_style_context().has_class("open")


@pytest.mark.parametrize("first", NAMES)
@pytest.mark.parametrize("second", NAMES)
def test_switch_between_views(notch, first, second, run_pending):
    """From any open view to any other: closes only when it is the same view."""
    table = views(notch)
    notch._open_notch_internal(first)
    run_pending()
    notch.bar.reset_mock()
    del notch.keyboard_modes[:]

    notch._open_notch_internal(second)
    run_pending()

    if first == second:
        assert is_closed(notch)
        return
    child, section, applet, hide = table[second]
    assert notch.stack.get_visible_child() == child
    assert notch._is_notch_open
    assert notch.keyboard_modes == ["exclusive"]
    if section is not None:
        assert notch.dashboard.stack.get_visible_child() == section
    if applet is not None:
        assert notch.applet_stack.get_visible_child() == applet
    in_place = applet is not None and table[first][0] == notch.dashboard
    if in_place:
        notch.bar.revealer_right.set_reveal_child.assert_not_called()
    else:
        notch.bar.revealer_right.set_reveal_child.assert_called_with(not hide)
        notch.bar.revealer_left.set_reveal_child.assert_called_with(not hide)


def test_unknown_name_opens_dashboard_and_never_closes(notch, run_pending):
    notch._open_notch_internal("pins")
    notch._open_notch_internal("no-such-view")
    run_pending()
    assert notch.stack.get_visible_child() == notch.dashboard
    assert notch.dashboard.stack.get_visible_child() == notch.dashboard.pins
    notch.bar.revealer_right.set_reveal_child.assert_called_with(False)

    notch._open_notch_internal("no-such-view")
    run_pending()
    assert notch.stack.get_visible_child() == notch.dashboard
    assert notch._is_notch_open


def test_hidden_top_bar_margins(notch, run_pending):
    notch.bar.get_visible.return_value = False
    margins = []
    real_set_margin = notch.set_margin
    notch.set_margin = lambda m: (margins.append(m), real_set_margin(m))
    try:
        notch._open_notch_internal("power")
        notch._open_notch_internal("power")
        run_pending()
    finally:
        del notch.set_margin
    assert margins == ["0px 8px 8px 8px", "-40px 0px 0px 0px"]


def test_open_launcher_with_text(notch, run_pending):
    notch._open_notch_internal("dashboard")
    notch.dashboard.add_style_class("open")
    notch.open_launcher_with_text("a")
    run_pending()
    assert notch.stack.get_visible_child() == notch.launcher
    assert notch.stack.get_style_context().has_class("launcher")
    assert notch.launcher.get_style_context().has_class("open")
    assert not notch.dashboard.get_style_context().has_class("open")
    assert notch._is_notch_open
    assert pump_until(lambda: notch.launcher.search_entry.get_text() == "a")


def test_typing_on_dashboard_widgets_opens_launcher(notch, run_pending):
    from types import SimpleNamespace

    from gi.repository import Gdk

    notch._open_notch_internal("power")
    assert notch.on_key_press(notch, SimpleNamespace(keyval=Gdk.KEY_a)) is False
    notch._open_notch_internal("pins")
    assert notch.on_key_press(notch, SimpleNamespace(keyval=Gdk.KEY_a)) is False

    notch._open_notch_internal("dashboard")
    assert notch.on_key_press(notch, SimpleNamespace(keyval=Gdk.KEY_Return)) is False
    assert notch.stack.get_visible_child() == notch.dashboard
    assert notch.on_key_press(notch, SimpleNamespace(keyval=Gdk.KEY_a)) is True
    assert notch.stack.get_visible_child() == notch.launcher
    # Typed while the launcher opens: buffered, then applied
    assert notch.on_key_press(notch, SimpleNamespace(keyval=Gdk.KEY_b)) is True
    assert notch.on_key_press(notch, SimpleNamespace(keyval=Gdk.KEY_Escape)) is False
    assert pump_until(lambda: notch.launcher.search_entry.get_text() == "ab")
