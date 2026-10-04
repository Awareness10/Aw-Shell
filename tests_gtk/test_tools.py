"""Toolbox buttons run the right script with the right arguments.

The scripts themselves aren't run (bash isn't stubbed, and they'd take real
screenshots); exec_shell_command_async is captured instead.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from gi.repository import Gdk

import modules.tools as tools

SCRIPTS = Path(tools.SCREENSHOT_SCRIPT).parent


@pytest.fixture
def run(monkeypatch):
    commands = []
    monkeypatch.setattr(tools, "exec_shell_command_async", commands.append)
    return commands


@pytest.fixture
def toolbox(run, run_pending):
    widget = tools.Toolbox(notch=MagicMock(name="notch"))
    run_pending()
    yield widget
    widget.destroy()
    run_pending()


def _press(widget, button):
    event = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
    event.button.button = button
    widget.emit("button-press-event", event)


def _key(state=0):
    return SimpleNamespace(keyval=Gdk.KEY_Return, get_state=lambda: Gdk.ModifierType(state))


@pytest.mark.parametrize("button, command", [
    ("btn_ssregion", f"bash {SCRIPTS}/screenshot.sh s"),
    ("btn_ssfull", f"bash {SCRIPTS}/screenshot.sh p"),
    ("btn_sswindow", f"bash {SCRIPTS}/screenshot.sh w"),
    ("btn_ocr", f"bash {SCRIPTS}/ocr.sh s"),
    ("btn_gamemode", f"bash {SCRIPTS}/gamemode.sh"),
    ("btn_pomodoro", f"bash -c 'nohup bash {SCRIPTS}/pomodoro.sh > /dev/null 2>&1 & disown'"),
    ("btn_screenrecord",
     f"bash -c 'nohup bash {SCRIPTS}/screenrecord.sh > /dev/null 2>&1 & disown'"),
])
def test_click_runs_script_and_closes(toolbox, run, button, command):
    getattr(toolbox, button).clicked()
    assert run == [command]
    toolbox.notch.close_notch.assert_called_once_with()


@pytest.mark.parametrize("button, mode", [
    ("btn_ssregion", "s"), ("btn_ssfull", "p"), ("btn_sswindow", "w"),
])
def test_screenshot_mouse_buttons(toolbox, run, button, mode):
    _press(getattr(toolbox, button), 1)
    _press(getattr(toolbox, button), 3)
    assert run == [f"bash {SCRIPTS}/screenshot.sh {mode}",
                   f"bash {SCRIPTS}/screenshot.sh {mode} mockup"]


def test_fullscreen_shift_enter_takes_mockup(toolbox, run):
    assert toolbox.on_ssfull_key(None, _key()) is True
    assert toolbox.on_ssfull_key(None, _key(Gdk.ModifierType.SHIFT_MASK)) is True
    assert run == [f"bash {SCRIPTS}/screenshot.sh p",
                   f"bash {SCRIPTS}/screenshot.sh p mockup"]


@pytest.mark.parametrize("mouse_button, fmt", [(1, "-hex"), (2, "-hsv"), (3, "-rgb")])
def test_color_picker_mouse_format(toolbox, run, mouse_button, fmt):
    _press(toolbox.btn_color, mouse_button)
    assert run == [f"bash {SCRIPTS}/hyprpicker.sh {fmt}"]


@pytest.mark.parametrize("state, fmt", [
    (0, "-hex"),
    (Gdk.ModifierType.SHIFT_MASK, "-rgb"),
    (Gdk.ModifierType.CONTROL_MASK, "-hsv"),
])
def test_color_picker_key_format(toolbox, run, state, fmt):
    assert toolbox.colorpicker_key(None, _key(state)) is True
    assert run == [f"bash {SCRIPTS}/hyprpicker.sh {fmt}"]


@pytest.mark.parametrize("button, folder", [
    ("btn_screenshots_folder", "Pictures/Screenshots"),
    ("btn_recordings_folder", "Videos/Recordings"),
])
def test_open_folder_creates_it(sandbox, toolbox, run, monkeypatch, button, folder):
    monkeypatch.delenv("XDG_PICTURES_DIR", raising=False)
    monkeypatch.delenv("XDG_VIDEOS_DIR", raising=False)
    getattr(toolbox, button).clicked()
    path = sandbox.home / folder
    assert path.is_dir()
    assert run == [f"xdg-open {path}"]


def test_emoji_opens_picker_in_notch(toolbox, run):
    toolbox.btn_emoji.clicked()
    toolbox.notch.open_notch.assert_called_once_with("emoji")
    assert run == []
