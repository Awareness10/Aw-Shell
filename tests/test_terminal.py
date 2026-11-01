"""config/terminal.py: the default terminal_command is the user's own
terminal, run with that terminal's own syntax, and never replaces a saved one."""

import json
import subprocess
from unittest.mock import patch

import pytest

import config.terminal
from config.settings_utils import get_bind_var, load_bind_vars, reset_to_defaults
from config.terminal import FALLBACK, TERMINALS, detect_terminal_command

# Each terminal's "run the rest of the line" syntax, checked against its
# --help, man page or docs (see config/terminal.py)
SYNTAX = {
    "kitty": "kitty -e",
    "foot": "foot",
    "alacritty": "alacritty -e",
    "ghostty": "ghostty -e",
    "wezterm": "wezterm start --",
    "konsole": "konsole -e",
    "gnome-terminal": "gnome-terminal --",
    "ptyxis": "ptyxis --",
    "xfce4-terminal": "xfce4-terminal -x",
}


def _which(*installed):
    return lambda name: f"/usr/bin/{name}" if name.rsplit("/", 1)[-1] in installed else None


@pytest.fixture
def xdg_finds():
    """Set whether xdg-terminal-exec --print-id finds a terminal."""
    result = {"code": 1}
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, result["code"])

    with patch("config.terminal.subprocess.run", side_effect=run):
        yield lambda found: result.update(code=0 if found else 1)
    assert all(cmd == ["xdg-terminal-exec", "--print-id"] for cmd in calls)


def test_every_terminal_has_its_checked_syntax():
    assert TERMINALS == SYNTAX


@pytest.mark.parametrize("name", list(SYNTAX))
def test_installed_terminal_runs_with_its_syntax(name, xdg_finds):
    assert detect_terminal_command({}, _which(name)) == SYNTAX[name]


@pytest.mark.parametrize("name", list(SYNTAX))
def test_terminal_variable_uses_its_syntax(name, xdg_finds):
    assert detect_terminal_command({"TERMINAL": name}, _which(name)) == SYNTAX[name]


def test_terminal_variable_keeps_a_full_path(xdg_finds):
    assert (detect_terminal_command({"TERMINAL": "/usr/bin/wezterm"}, _which("wezterm"))
            == "/usr/bin/wezterm start --")


def test_unknown_terminal_variable_gets_dash_e(xdg_finds):
    assert detect_terminal_command({"TERMINAL": "st"}, _which("st", "kitty")) == "st -e"


def test_terminal_variable_comes_first(xdg_finds):
    xdg_finds(True)
    which = _which("foot", "kitty", "xdg-terminal-exec")
    assert detect_terminal_command({"TERMINAL": "foot"}, which) == "foot"


def test_terminal_variable_ignored_when_not_installed(xdg_finds):
    assert detect_terminal_command({"TERMINAL": "foot"}, _which("alacritty")) == "alacritty -e"


def test_xdg_terminal_exec_before_the_list(xdg_finds):
    xdg_finds(True)
    which = _which("kitty", "xdg-terminal-exec")
    assert detect_terminal_command({}, which) == "xdg-terminal-exec"


def test_xdg_terminal_exec_without_a_terminal_is_skipped(xdg_finds):
    xdg_finds(False)
    which = _which("foot", "xdg-terminal-exec")
    assert detect_terminal_command({}, which) == "foot"


def test_list_order(xdg_finds):
    assert detect_terminal_command({}, _which("foot", "kitty", "alacritty")) == "kitty -e"


def test_no_terminal_falls_back_to_kitty(xdg_finds):
    assert detect_terminal_command({}, _which()) == FALLBACK == "kitty -e"


class TestSettings:
    """The detected terminal is only a default."""

    @pytest.fixture(autouse=True)
    def detected(self, monkeypatch):
        monkeypatch.setattr(config.terminal, "default_terminal_command", lambda: "foot")

    def test_first_run_uses_the_detected_terminal(self, tmp_path):
        with patch("config.settings_utils.CONFIG_FILE", tmp_path / "config.json"):
            load_bind_vars()
        assert get_bind_var("terminal_command") == "foot"

    def test_saved_terminal_is_not_overridden(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"terminal_command": "alacritty -e"}))
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        assert get_bind_var("terminal_command") == "alacritty -e"

    def test_settings_without_a_terminal_get_the_detected_one(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"bar_position": "Bottom"}))
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        assert get_bind_var("terminal_command") == "foot"

    def test_reset_to_defaults_uses_the_detected_terminal(self):
        reset_to_defaults()
        assert get_bind_var("terminal_command") == "foot"
