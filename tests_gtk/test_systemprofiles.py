"""Systemprofiles shows a button per power profile, and nothing at all (not
even its empty background) when there are none, e.g. in a VM or without a
working powerprofilesctl."""

import subprocess
import time

import pytest
from conftest import pump_until

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


REAL_RUN = subprocess.run


def _powerprofilesctl(listing):
    def run(cmd, **kwargs):
        if cmd[0] != "powerprofilesctl":  # subprocess.run is shared by every module
            return REAL_RUN(cmd, **kwargs)
        time.sleep(0.1)  # powerprofilesctl is a Python script: ~50 ms to start
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
        start = time.monotonic()
        widget = Systemprofiles()
        assert time.monotonic() - start < 0.05  # asks powerprofilesctl in the background
        widgets.append(widget)
        widget.set_visible(True)  # what the bar does, before the profiles load
        assert pump_until(lambda: not widget.loading)
        return widget

    yield make
    for widget in widgets:
        widget.destroy()


@pytest.mark.parametrize("listing", [None, ""])  # powerprofilesctl failing, or no profiles
def test_hidden_without_profiles(make, listing):
    widget = make(listing)
    widget.set_visible(True)
    widget.show_all()
    assert not widget.get_visible()


def test_one_button_per_profile(make):
    widget = make(PROFILES)
    assert widget.get_visible()  # shown as the bar asked, once loaded
    assert all((widget.bat_save, widget.bat_balanced, widget.bat_perf))
    assert widget.current_mode == "balanced"
    assert widget.bat_balanced.get_style_context().has_class("active")


def test_disabled_in_settings_stays_hidden(make):
    widget = make(PROFILES)
    widget.set_visible(False)
    assert not widget.get_visible()
