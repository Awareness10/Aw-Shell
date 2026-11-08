"""Brightness: detecting DDC/CI monitors (ddcutil, ~1 s) runs in the
background, and the brightness controls appear once it's done."""

import subprocess
import time

import pytest
from conftest import pump_until

import services.brightness as brightness_module
from services.brightness import Brightness

REAL_RUN = subprocess.run


def _ddcutil(monitor: bool, calls: list):
    def run(cmd, **kwargs):
        if cmd[0] != "ddcutil":  # subprocess.run is shared by every module
            return REAL_RUN(cmd, **kwargs)
        calls.append(cmd)
        time.sleep(0.2)  # ddcutil talks to the monitor over I2C
        if cmd[1] == "detect":
            out = "Display 1\n   I2C bus:  /dev/i2c-5\n" if monitor else "No displays found.\n"
            return subprocess.CompletedProcess(cmd, 0 if monitor else 1, out, "")
        return subprocess.CompletedProcess(
            cmd, 0, "VCP code 0x10 (Brightness): current value =    40, max value =   100\n", "")
    return run


@pytest.fixture
def ddcutil(sandbox, monkeypatch):
    """A desktop: no backlight, ddcutil installed. Returns (setup, calls)."""
    calls = []
    monkeypatch.setattr(Brightness, "instance", None)
    monkeypatch.setattr(Brightness, "_get_screen_device", lambda self: "")
    monkeypatch.setattr(brightness_module.shutil, "which",
                        lambda name: f"/usr/bin/{name}" if name == "ddcutil" else None)

    def setup(monitor: bool):
        monkeypatch.setattr(brightness_module.subprocess, "run", _ddcutil(monitor, calls))
    return setup, calls


def test_ddcutil_detected_in_the_background(ddcutil):
    setup, calls = ddcutil
    setup(monitor=True)
    ready = []
    start = time.monotonic()
    service = Brightness.get_initial()
    assert time.monotonic() - start < 0.1  # doesn't wait for ddcutil
    service.connect("ready", lambda *_: ready.append(True))
    assert service.detecting and service.screen_brightness == -1

    assert pump_until(lambda: not service.detecting)
    assert ready == [True]
    assert (service.backend, service.ddcutil_bus, service.max_screen) == ("ddcutil", 5, 100)
    count = len(calls)
    assert service.screen_brightness == 40  # read during detection, cached
    assert len(calls) == count


def test_no_ddc_monitor(ddcutil):
    setup, _ = ddcutil
    setup(monitor=False)
    service = Brightness.get_initial()
    assert pump_until(lambda: not service.detecting)
    assert service.backend is None and service.screen_brightness == -1


@pytest.mark.parametrize("monitor", [True, False])
def test_controls_added_once_detected(ddcutil, monitor):
    from modules.controls import BrightnessSmall, ControlSliders, ControlSmall

    setup, _ = ddcutil
    setup(monitor=monitor)
    small, sliders = ControlSmall(), ControlSliders()
    try:
        service = Brightness.get_initial()
        assert pump_until(lambda: not service.detecting)
        pump_until(lambda: False, timeout=0.1)
        first = small.get_children()[0]
        assert isinstance(first, BrightnessSmall) is monitor
        rows = sliders.get_children()
        assert len(rows) == (3 if monitor else 2)  # brightness row first, then volume, mic
    finally:
        small.destroy()
        sliders.destroy()
