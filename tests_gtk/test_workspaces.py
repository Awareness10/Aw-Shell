"""The bar's workspaces with a special workspace open: Hyprland 0.57 leaves
its "id" out, and fabric's widget crashed the bar on startup."""

import json

import pytest
from fake_hyprland import CLIENT, DEFAULT_STATE, WORKSPACE

SPECIAL = {k: v for k, v in WORKSPACE.items() if k != "id"} | {
    "type": "special", "name": "special:magic", "address": "special:magic"}
SPECIAL_CLIENT = CLIENT | {
    "address": "0x2", "workspace": {"type": "special", "name": "special:magic"}}


@pytest.fixture
def scratchpad_open(sandbox):
    state = DEFAULT_STATE | {"workspaces": [WORKSPACE, SPECIAL],
                             "clients": [CLIENT, SPECIAL_CLIENT]}
    sandbox.hyprland.state_file.write_text(json.dumps(state))


def _workspaces():
    from fabric.hyprland.widgets import WorkspaceButton

    from widgets.hyprland import HyprlandWorkspaces

    return HyprlandWorkspaces(
        buttons=[WorkspaceButton(id=i) for i in range(1, 4)],
        buttons_factory=HyprlandWorkspaces.default_buttons_factory,
    )


def test_builds_with_a_special_workspace_open(scratchpad_open, run_pending):
    workspaces = _workspaces()
    run_pending()
    buttons = workspaces._buttons
    assert sorted(buttons) == [1, 2, 3]  # no button for the id-less one
    assert buttons[1].active and not buttons[1].empty
    assert buttons[2].empty
    workspaces.destroy()


def test_urgent_window_on_a_special_workspace_is_ignored(sandbox, scratchpad_open, run_pending):
    from conftest import pump_until

    workspaces = _workspaces()
    run_pending()
    sandbox.hyprland.emit("urgent", "2")  # SPECIAL_CLIENT
    sandbox.hyprland.emit("urgent", "1")  # CLIENT, on workspace 1
    buttons = workspaces._buttons
    assert pump_until(lambda: buttons[1].urgent)
    workspaces.destroy()
