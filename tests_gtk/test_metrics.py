"""Metrics must keep working on systems without UPower (no battery)."""

import os
import subprocess
import sys


def test_import_without_upower(no_upower):
    # modules.metrics builds its provider at import time, which the bar
    # triggers at startup; run it in a fresh process like the real shell
    result = subprocess.run(
        [sys.executable, "-c", "import modules.metrics"],
        capture_output=True, text=True, env=os.environ, timeout=30,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def test_provider_without_upower(no_upower):
    from modules.metrics import MetricsProvider

    provider = MetricsProvider()
    assert provider._update() is True
    assert provider.get_battery() == (0.0, None, 0)


def test_update_survives_upower_stopping(sandbox):
    from modules.metrics import MetricsProvider

    provider = MetricsProvider()
    provider._update()
    assert provider.get_battery()[0] == 80.0

    sandbox.stop_upower()
    try:
        # Returning anything but True would end the GLib timer and freeze
        # the CPU/memory/disk readings too
        assert provider._update() is True
        assert provider.get_battery() == (0.0, None, 0)
    finally:
        sandbox.start_upower()


def test_battery_read_with_upower():
    from modules.metrics import MetricsProvider

    provider = MetricsProvider()
    provider._update()
    assert provider.get_battery() == (80.0, False, 5400)


def test_destroyed_widgets_stop_updating(run_pending):
    """Bars are destroyed when their monitor goes away; their periodic updates
    must stop, or they hit dead widgets (Gtk-CRITICALs, caught by conftest)."""
    import time

    from modules.metrics import Battery, Metrics, MetricsSmall, NetworkApplet

    widgets = [Metrics(), MetricsSmall(), Battery(), NetworkApplet()]
    run_pending()
    for widget in widgets:
        widget.destroy()
    deadline = time.monotonic() + 2.5  # every update interval elapses at least once
    while time.monotonic() < deadline:
        run_pending()
        time.sleep(0.05)


def test_gpu_info_asked_once_in_the_background(sandbox, monkeypatch):
    """nvtop takes ~0.2 s with an NVIDIA card; every metrics widget (bar and
    dashboard, on each monitor) used to ask it again while the shell started,
    and then waited for it."""
    import time

    from conftest import pump_until

    import modules.metrics as metrics

    calls = []
    gpus = [{"device_name": "RTX", "gpu_util": "5%"}]

    real = subprocess.check_output

    def check_output(cmd, **kwargs):
        if cmd[0] != "nvtop":  # check_output is shared by every module
            return real(cmd, **kwargs)
        calls.append(cmd)
        time.sleep(0.3)
        return '[{"device_name": "RTX", "gpu_util": "5%"}]'

    monkeypatch.setattr(metrics.subprocess, "check_output", check_output)
    start = time.monotonic()
    provider = metrics.MetricsProvider()
    answers = []
    provider.when_gpu_info(answers.append)
    provider.when_gpu_info(answers.append)
    assert time.monotonic() - start < 0.1  # doesn't wait for nvtop
    assert answers == []
    assert pump_until(lambda: len(answers) == 2)
    assert answers == [gpus, gpus]
    provider.when_gpu_info(answers.append)  # known by now: answered at once
    assert answers[-1] == gpus
    assert calls == [["nvtop", "-s"]]


def test_widgets_add_gpu_gauges_when_nvtop_answers(sandbox, monkeypatch):
    import time

    from conftest import pump_until

    import modules.metrics as metrics

    real = subprocess.check_output

    def check_output(cmd, **kwargs):
        if cmd[0] != "nvtop":  # check_output is shared by every module
            return real(cmd, **kwargs)
        time.sleep(0.3)
        return '[{"device_name": "RTX", "gpu_util": "5%"}]'

    monkeypatch.setattr(metrics.subprocess, "check_output", check_output)
    monkeypatch.setattr(metrics, "shared_provider", metrics.MetricsProvider())
    start = time.monotonic()
    small, big = metrics.MetricsSmall(), metrics.Metrics()
    assert time.monotonic() - start < 0.1
    assert small.gpu == [] and big.gpu == []
    assert pump_until(lambda: small.gpu and big.gpu)
    assert len(small.gpu) == len(big.gpu) == 1
    assert small.gpu[0].box.get_parent() is not None
    assert big.gpu[0].box.get_parent() is big
    small.destroy()
    big.destroy()
