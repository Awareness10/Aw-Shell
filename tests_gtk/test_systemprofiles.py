"""Systemprofiles shows a button per power profile, and nothing at all (not
even its empty background) when there are none, e.g. in a VM or without a
working powerprofilesctl."""

import subprocess

import pytest

import modules.systemprofiles as systemprofiles
from modules.systemprofiles import Systemprofiles

PROFILES = """\
  performance:
    CpuDriver:  amd_pstate
* balanced:
    CpuDriver:  amd_pstate
  power-saver:
    CpuDriver:  amd_pstate
"""


def _powerprofilesctl(listing):
    def run(cmd, **kwargs):
        if listing is None:
            raise subprocess.CalledProcessError(1, cmd)
        out = listing if cmd[1] == "list" else "balanced\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
    return run


@pytest.fixture
def make(sandbox, monkeypatch):
    widgets = []

    def make(listing):
        monkeypatch.setattr(systemprofiles.subprocess, "run", _powerprofilesctl(listing))
        widget = Systemprofiles()
        widgets.append(widget)
        return widget

    yield make
    for widget in widgets:
        widget.destroy()


@pytest.mark.parametrize("listing", [None, ""])  # powerprofilesctl failing, or no profiles
def test_hidden_without_profiles(make, listing):
    widget = make(listing)
    widget.set_visible(True)  # what the bar does when the component is enabled
    widget.show_all()
    assert not widget.get_visible()


def test_one_button_per_profile(make):
    widget = make(PROFILES)
    widget.set_visible(True)
    assert widget.get_visible()
    assert all((widget.bat_save, widget.bat_balanced, widget.bat_perf))


def test_disabled_in_settings_stays_hidden(make):
    widget = make(PROFILES)
    widget.set_visible(False)
    assert not widget.get_visible()
