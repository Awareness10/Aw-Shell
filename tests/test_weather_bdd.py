"""BDD scenarios for the Weather widget visibility behavior.

Tests the core invariant: fetch failures must never clobber the user's
config-driven `enabled` flag, so the widget recovers on the next
successful fetch.
"""

import subprocess
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Ensure config.data has VERTICAL attr (conftest mocks may not include it)
import config.data as _data
if not hasattr(_data, "VERTICAL"):
    _data.VERTICAL = False

# ── Extra fabric.widgets mocks needed by modules/weather.py ──
_widgets = types.ModuleType("fabric.widgets")
_button_mod = types.ModuleType("fabric.widgets.button")
_label_mod = types.ModuleType("fabric.widgets.label")


class _FakeButton:
    """Minimal stand-in for fabric Button."""

    def __init__(self, **kw):
        self._gtk_visible = True

    def set_visible(self, v):
        self._gtk_visible = v

    def add(self, child):
        pass

    def show_all(self):
        pass

    def set_tooltip_text(self, t):
        self._tooltip = t


class _FakeLabel:
    def __init__(self, **kw):
        self.text = ""

    def set_label(self, t):
        self.text = t

    def set_markup(self, t):
        self.text = t


_button_mod.Button = _FakeButton
_label_mod.Label = _FakeLabel
_widgets.button = _button_mod
_widgets.label = _label_mod

sys.modules.setdefault("fabric.widgets", _widgets)
sys.modules.setdefault("fabric.widgets.button", _button_mod)
sys.modules.setdefault("fabric.widgets.label", _label_mod)

# Mock modules.icons so Weather can import it
_icons = types.ModuleType("modules.icons")
_icons.loader = "⏳"
_icons.cloud_off = "☁"
sys.modules.setdefault("modules.icons", _icons)

# Now safe to import
from modules.weather import Weather  # noqa: E402


# ── helpers ──

def _make_weather(enabled=True):
    """Create a Weather widget with timers disabled, optionally pre-enabled."""
    with patch("gi.repository.GLib.timeout_add_seconds"), \
         patch("gi.repository.GLib.timeout_add"):
        w = Weather()
    if enabled:
        w.set_visible(True)  # simulate apply_component_props
    return w


def _run_fetch(weather, curl_side_effect):
    """Run _fetch_weather_thread synchronously with a mocked subprocess.run,
    then flush all GLib.idle_add callbacks inline."""
    pending = []

    def capture_idle(fn, *args):
        pending.append((fn, args))

    with patch("gi.repository.GLib.idle_add", side_effect=capture_idle), \
         patch("subprocess.run", side_effect=curl_side_effect):
        weather._fetch_weather_thread(None)

    for fn, args in pending:
        fn(*args)


def _curl_ok(url_fragment="", stdout="☀ +2°C"):
    """Return a successful curl CompletedProcess matching *url_fragment*."""
    return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")


def _curl_fail():
    return subprocess.CompletedProcess([], 22, stdout="", stderr="")


# ── BDD Scenarios ──


class TestWeatherVisibility:
    """
    Scenario: Widget shows after a successful fetch when config-enabled
    """

    def test_shows_after_successful_fetch(self):
        # Given a weather widget that is enabled by config
        w = _make_weather(enabled=True)
        assert w.enabled is True
        assert w.has_weather_data is False

        # When a successful weather fetch completes
        _run_fetch(w, lambda *a, **kw: _curl_ok())

        # Then the widget should be visible
        assert w.has_weather_data is True
        assert w._gtk_visible is True

    """
    Scenario: Widget stays hidden when config-disabled, even after successful fetch
    """

    def test_stays_hidden_when_config_disabled(self):
        # Given a weather widget that is disabled by config
        w = _make_weather(enabled=False)

        # When a successful weather fetch completes
        _run_fetch(w, lambda *a, **kw: _curl_ok())

        # Then the widget should remain hidden
        assert w.has_weather_data is True
        assert w._gtk_visible is False
        # And the enabled flag should still be False
        assert w.enabled is False

    """
    Scenario: Failed fetch hides widget but preserves enabled flag
    """

    def test_failed_fetch_preserves_enabled_flag(self):
        # Given a weather widget that is enabled by config
        w = _make_weather(enabled=True)

        # When the weather fetch fails (curl error)
        _run_fetch(w, lambda *a, **kw: _curl_fail())

        # Then the widget should be hidden (no data to show)
        assert w._gtk_visible is False
        # But the enabled flag must NOT be clobbered
        assert w.enabled is True

    """
    Scenario: Widget recovers after a failed fetch followed by a successful one
    """

    def test_recovers_after_failure_then_success(self):
        # Given a weather widget that is enabled by config
        w = _make_weather(enabled=True)

        # When the first fetch fails
        _run_fetch(w, lambda *a, **kw: _curl_fail())
        assert w._gtk_visible is False

        # And then a subsequent fetch succeeds
        w.fetching = False  # reset guard
        _run_fetch(w, lambda *a, **kw: _curl_ok())

        # Then the widget should be visible again
        assert w._gtk_visible is True
        assert w.enabled is True

    """
    Scenario: Network timeout hides widget but preserves enabled flag
    """

    def test_timeout_preserves_enabled_flag(self):
        # Given a weather widget that is enabled by config
        w = _make_weather(enabled=True)

        # When the fetch times out
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="curl", timeout=6)

        _run_fetch(w, raise_timeout)

        # Then the widget should be hidden
        assert w._gtk_visible is False
        # But enabled must still be True
        assert w.enabled is True

    """
    Scenario: "Unknown" weather response hides widget but preserves enabled flag
    """

    def test_unknown_response_preserves_enabled_flag(self):
        # Given a weather widget that is enabled by config
        w = _make_weather(enabled=True)

        # When wttr.in returns "Unknown"
        _run_fetch(w, lambda *a, **kw: _curl_ok(stdout="Unknown location"))

        # Then the widget should be hidden
        assert w._gtk_visible is False
        assert w.has_weather_data is False
        # But enabled must still be True
        assert w.enabled is True

    """
    Scenario: Recovery after "Unknown" response when location resolves later
    """

    def test_recovers_after_unknown_then_success(self):
        # Given a weather widget enabled by config
        w = _make_weather(enabled=True)

        # When first fetch returns Unknown
        _run_fetch(w, lambda *a, **kw: _curl_ok(stdout="Unknown location"))
        assert w._gtk_visible is False

        # And then a subsequent fetch succeeds
        w.fetching = False
        _run_fetch(w, lambda *a, **kw: _curl_ok())

        # Then the widget should be visible
        assert w._gtk_visible is True
        assert w.enabled is True

    """
    Scenario: User toggles widget off while weather data exists
    """

    def test_user_disables_with_existing_data(self):
        # Given a widget with weather data showing
        w = _make_weather(enabled=True)
        _run_fetch(w, lambda *a, **kw: _curl_ok())
        assert w._gtk_visible is True

        # When the user disables the weather widget via settings
        w.set_visible(False)

        # Then it should be hidden
        assert w._gtk_visible is False
        assert w.enabled is False

    """
    Scenario: User re-enables widget that already has cached weather data
    """

    def test_user_reenables_with_cached_data(self):
        # Given a widget that was showing but then disabled
        w = _make_weather(enabled=True)
        _run_fetch(w, lambda *a, **kw: _curl_ok())
        w.set_visible(False)
        assert w._gtk_visible is False

        # When the user re-enables it
        w.set_visible(True)

        # Then it should show immediately (data is cached)
        assert w._gtk_visible is True
        assert w.enabled is True

    """
    Scenario: Concurrent fetch prevention
    """

    def test_concurrent_fetch_blocked(self):
        # Given a weather widget currently fetching
        w = _make_weather(enabled=True)
        w.fetching = True

        # When fetch_weather is called again
        result = w.fetch_weather()

        # Then it should return True (to keep timer) but not start another fetch
        assert result is True
        assert w.fetching is True  # unchanged, no new thread spawned
