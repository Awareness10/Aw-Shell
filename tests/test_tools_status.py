"""ToolsStatusMonitor process scan: recorder detection by exact name."""

import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tools():
    stubs = {}
    for name in (
        "fabric.hyprland",
        "fabric.hyprland.service",
        "fabric.widgets",
        "fabric.widgets.box",
        "fabric.widgets.button",
        "fabric.widgets.label",
    ):
        module = types.ModuleType(name)
        module.Hyprland = MagicMock()
        module.Box = module.Button = module.Label = type("Widget", (), {})
        stubs[name] = module
    with patch.dict(sys.modules, stubs):
        sys.modules.pop("modules.tools", None)
        yield importlib.import_module("modules.tools")
        sys.modules.pop("modules.tools", None)


def _proc(pid, cmdline, create_time=0.0):
    proc = MagicMock()
    proc.info = {"pid": pid, "cmdline": cmdline, "create_time": create_time}
    return proc


def _scan(tools, procs):
    with patch.object(tools.psutil, "process_iter", return_value=procs):
        return tools.ToolsStatusMonitor._scan_processes()


def test_recorder_start_time_reported(tools):
    procs = [_proc(10, ["/usr/bin/gpu-screen-recorder", "-w", "portal"], 123.5)]
    assert _scan(tools, procs) == (123.5, False)


def test_command_lines_mentioning_recorder_ignored(tools):
    procs = [
        _proc(11, ["bash", "-c", "pgrep gpu-screen-recorder"]),
        _proc(12, ["nvim", "gpu-screen-recorder.conf"]),
    ]
    assert _scan(tools, procs) == (None, False)


def test_pomodoro_detected(tools):
    procs = [_proc(13, ["bash", "/x/scripts/pomodoro.sh"])]
    assert _scan(tools, procs) == (None, True)
