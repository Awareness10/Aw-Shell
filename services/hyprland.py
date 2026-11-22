"""Hyprland requests over its command socket: JSON queries and dispatches.

Fabric's `Hyprland.send_command` opens a short-lived connection per request
and needs no event listener, so nothing here starts one. Widgets that follow
events use fabric's shared connection (`connection()`).

On a socket error fabric logs it and replies with nothing, so `query` raises
ValueError (no JSON); callers that can carry on catch it.
"""

import json

from fabric.hyprland.service import Hyprland


def connection() -> Hyprland:
    """Fabric's shared Hyprland connection, for its events."""
    from fabric.hyprland.widgets import get_hyprland_connection

    return get_hyprland_connection()


def query(command: str):
    """The parsed reply of `hyprctl -j <command>` (e.g. "clients",
    "activewindow", "getoption animations:enabled")."""
    return json.loads(Hyprland.send_command(f"j/{command}").reply.decode())


def dispatch(expression: str) -> None:
    """Run a dispatcher. Hyprland 0.56+ (Lua config) takes a Lua expression,
    e.g. `hl.dsp.focus({ window = "class:notch" })`."""
    Hyprland.send_command(f"/dispatch {expression}")


def focus_window(address: str) -> None:
    dispatch(f'hl.dsp.focus({{ window = "address:{address}" }})')


def close_window(address: str) -> None:
    dispatch(f'hl.dsp.window.close({{ window = "address:{address}" }})')


def move_window_to_workspace(address: str, workspace_id: int) -> None:
    """Move without following the window (the old movetoworkspacesilent)."""
    dispatch(
        f'hl.dsp.window.move({{ workspace = "{workspace_id}", '
        f'window = "address:{address}", follow = false }})'
    )
