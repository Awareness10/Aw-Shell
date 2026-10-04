"""App launcher: search, launch, the `:` commands and the calculator.

Apps are stand-ins whose launch() only records the call; real desktop
entries would start real programs.
"""

import json
import os
import shlex
import sys
from unittest.mock import MagicMock

import pytest
from conftest import pump_until

import modules.launcher as launcher_module


class FakeApp:
    def __init__(self, display_name, name=None, executable=None, description=""):
        self.display_name = display_name
        self.name = name or display_name.lower()
        self.executable = executable or self.name
        self.command_line = self.executable
        self.generic_name = None
        self.window_class = self.name
        self.description = description
        self.launched = 0

    def get_icon_pixbuf(self, size=24):
        return None

    def launch(self):
        self.launched += 1


FIREFOX = FakeApp("Firefox", executable="firefox")
FILES = FakeApp("Files", name="org.gnome.Nautilus", executable="nautilus")
FILEZILLA = FakeApp("FileZilla")


@pytest.fixture
def run(monkeypatch):
    commands = []
    monkeypatch.setattr(launcher_module, "exec_shell_command_async", commands.append)
    return commands


@pytest.fixture
def launcher(run, run_pending, monkeypatch, tmp_path):
    monkeypatch.setattr(launcher_module, "get_desktop_applications",
                        lambda: [FIREFOX, FILES, FILEZILLA])
    for app in (FIREFOX, FILES, FILEZILLA):
        app.launched = 0
    widget = launcher_module.AppLauncher(notch=MagicMock(name="notch"))
    widget.calc_history_path = str(tmp_path / "calc.json")
    widget.calc_history = []
    widget.open_launcher()
    run_pending()
    yield widget
    widget.destroy()
    run_pending()


def _labels(launcher):
    return [slot.get_child().get_children()[1].get_label()
            for slot in launcher.viewport.get_children()]


def _search(launcher, text):
    launcher.search_entry.set_text(text)
    launcher.arrange_viewport(text)
    ranked = [a.display_name for a in launcher_module.apps.rank_apps(launcher._all_apps, text)]
    assert pump_until(lambda: _labels(launcher) == ranked), _labels(launcher)


def test_empty_query_lists_every_app_by_name(launcher):
    assert pump_until(lambda: _labels(launcher) == ["Files", "FileZilla", "Firefox"])


def test_search_shows_best_match_first(launcher):
    _search(launcher, "file")
    assert _labels(launcher) == ["Files", "FileZilla"]


def test_enter_launches_top_result_and_closes(launcher):
    _search(launcher, "fire")
    launcher.on_search_entry_activate("fire")
    assert FIREFOX.launched == 1
    launcher.notch.close_notch.assert_called_once_with()


def test_click_launches_that_app(launcher):
    _search(launcher, "file")
    launcher.viewport.get_children()[1].clicked()
    assert (FILES.launched, FILEZILLA.launched) == (0, 1)


@pytest.mark.parametrize("command, module", [(":w", "wallpapers"), (":d", "dashboard"),
                                             (":p", "power")])
def test_colon_commands_open_notch_modules(launcher, command, module):
    launcher.on_search_entry_activate(command)
    launcher.notch.open_notch.assert_called_once_with(module)


@pytest.mark.parametrize("command", [":settings", ":config"])
def test_settings_use_the_shells_interpreter(launcher, run, command):
    launcher.on_search_entry_activate(command)
    python, script = shlex.split(run[0])
    assert python == sys.executable  # a bare `python` lacks the shell's dependencies
    assert os.path.isfile(script) and script.endswith("config/config.py")
    launcher.notch.close_notch.assert_called_once_with()


def test_update_runs_updater_with_shells_interpreter(launcher, monkeypatch):
    spawned = []
    monkeypatch.setattr(launcher_module._sp, "Popen", lambda args, **kw: spawned.append(args))
    launcher.on_search_entry_activate(":update")
    assert spawned == [[sys.executable, "-m", "modules.updater", "--force"]]


def test_calculator_result_saved(launcher):
    launcher.search_entry.set_text("=2^10")
    launcher.evaluate_calculator_expression("=2^10")
    assert launcher.calc_history[0] == "=2^10 => 1024"
    with open(launcher.calc_history_path) as f:
        assert json.load(f)[0] == "=2^10 => 1024"


def test_new_search_after_results_finished_loading(launcher):
    """The finished loader's idle source is gone; removing it again made GLib
    warn "Source ID ... was not found" on every search."""
    import warnings

    _search(launcher, "file")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _search(launcher, "fire")
