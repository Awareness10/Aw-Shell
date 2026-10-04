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
