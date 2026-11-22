"""services/hyprland against the fake Hyprland sockets."""

import pytest

from services import hyprland

ADDRESS = "0x1"  # the window in tests_gtk/fake_hyprland.py
FOCUS = f'/dispatch hl.dsp.focus({{ window = "address:{ADDRESS}" }})'


def dispatches(sandbox):
    return [c for c in sandbox.hyprland.log if c.startswith("/dispatch")]


def test_query_parses_the_json_reply(sandbox):
    assert hyprland.query("clients")[0]["address"] == ADDRESS
    assert hyprland.query("activeworkspace")["id"] == 1
    assert sandbox.hyprland.log[-2:] == ["j/clients", "j/activeworkspace"]


def test_query_without_json_reply_raises_value_error(sandbox):
    with pytest.raises(ValueError):
        hyprland.query("no-such-request")  # the fake answers "ok"


def test_window_dispatches(sandbox):
    sandbox.hyprland.log.clear()
    hyprland.focus_window(ADDRESS)
    hyprland.close_window(ADDRESS)
    hyprland.move_window_to_workspace(ADDRESS, 3)
    hyprland.dispatch('hl.dsp.focus({ window = "class:notch" })')
    assert dispatches(sandbox) == [
        FOCUS,
        f'/dispatch hl.dsp.window.close({{ window = "address:{ADDRESS}" }})',
        f'/dispatch hl.dsp.window.move({{ workspace = "3", window = "address:{ADDRESS}", '
        "follow = false })",
        '/dispatch hl.dsp.focus({ window = "class:notch" })',
    ]


def test_dock_focuses_windows_over_the_socket(sandbox):
    from modules.dock import Dock

    sandbox.hyprland.log.clear()
    before = len(sandbox.hyprland.hyprctl_calls())
    Dock._focus_window(ADDRESS)
    assert dispatches(sandbox) == [FOCUS]
    assert sandbox.hyprland.hyprctl_calls()[before:] == []


def test_dock_queries(sandbox, monkeypatch):
    """get_clients/get_focused/get_workspace, and their fallbacks when
    Hyprland's reply isn't JSON."""
    from modules.dock import Dock

    def queries():  # they need no widget state
        return Dock.get_clients(None), Dock.get_focused(None), Dock.get_workspace(None)

    clients, focused, workspace = queries()
    assert ([c["address"] for c in clients], focused, workspace) == ([ADDRESS], ADDRESS, 1)

    def no_json(command):
        raise ValueError("no JSON")

    monkeypatch.setattr(hyprland, "query", no_json)
    assert queries() == ([], "", 0)
