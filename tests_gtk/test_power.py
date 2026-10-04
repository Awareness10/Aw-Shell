"""Power menu buttons run the right command, then close the notch."""

import shutil
from unittest.mock import MagicMock

import pytest
from conftest import pump_until


@pytest.fixture
def menu(run_pending):
    from modules.power import PowerMenu

    widget = PowerMenu(notch=MagicMock(name="notch"))
    run_pending()
    yield widget
    widget.destroy()


@pytest.mark.parametrize("button, command", [
    ("btn_lock", "loginctl lock-session"),
    ("btn_suspend", "systemctl suspend"),
    ("btn_reboot", "systemctl reboot"),
    ("btn_shutdown", "systemctl poweroff"),
])
def test_button_runs_command(sandbox, menu, button, command):
    before = len(sandbox.commands())
    getattr(menu, button).clicked()
    assert pump_until(lambda: sandbox.commands()[before:] == [command]), sandbox.commands()[before:]
    menu.notch.close_notch.assert_called_once_with()


def test_logout_exits_hyprland(sandbox, menu):
    # Never let this reach a real session
    assert shutil.which("hyprctl") == str(sandbox.bin / "hyprctl")
    before = len(sandbox.hyprland.hyprctl_calls())

    def calls():
        return sandbox.hyprland.hyprctl_calls()[before:]

    menu.btn_logout.clicked()
    assert pump_until(lambda: calls() == ["dispatch hl.dsp.exit()"]), calls()
    menu.notch.close_notch.assert_called_once_with()
