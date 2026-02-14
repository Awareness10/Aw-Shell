"""Tests for utils/monitor_manager.py - Monitor detection, workspace mapping, and notch state."""

import json
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from utils.monitor_manager import MonitorManager, Signal, get_monitor_manager


# ── Fixtures ──────────────────────────────────────────────────────────


# Sample hyprctl output: 3 monitors, primary at origin
TRIPLE_MONITOR = json.dumps([
    {"name": "DP-1", "id": 1, "width": 2560, "height": 1440, "x": 2560, "y": 0, "scale": 1.0, "focused": False},
    {"name": "HDMI-A-1", "id": 0, "width": 2560, "height": 1440, "x": 0, "y": 0, "scale": 1.0, "focused": True},
    {"name": "DP-2", "id": 2, "width": 2560, "height": 1440, "x": 5120, "y": 0, "scale": 1.0, "focused": False},
])

SINGLE_MONITOR = json.dumps([
    {"name": "eDP-1", "id": 0, "width": 1920, "height": 1080, "x": 0, "y": 0, "scale": 1.25, "focused": True},
])

STACKED_MONITORS = json.dumps([
    {"name": "DP-1", "id": 0, "width": 3840, "height": 2160, "x": 0, "y": 0, "scale": 2.0, "focused": True},
    {"name": "DP-2", "id": 1, "width": 1920, "height": 1080, "x": 0, "y": 2160, "scale": 1.0, "focused": False},
])


def _hyprctl_result(stdout: str):
    """Create a mock subprocess.run result."""
    result = MagicMock()
    result.stdout = stdout
    return result


def _make_manager(hyprctl_stdout: str) -> MonitorManager:
    """Create a fresh MonitorManager with mocked hyprctl output."""
    # Reset singleton
    MonitorManager._instance = None

    with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(hyprctl_stdout)):
        mgr = MonitorManager()
    return mgr


WORKSPACE_DATA = json.dumps([
    {"id": 1, "monitor": "HDMI-A-1"},
    {"id": 2, "monitor": "HDMI-A-1"},
    {"id": 3, "monitor": "DP-1"},
    {"id": 4, "monitor": "DP-2"},
])


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure each test gets a fresh singleton."""
    MonitorManager._instance = None
    import utils.monitor_manager as mm
    mm._monitor_manager_instance = None
    yield
    MonitorManager._instance = None
    mm._monitor_manager_instance = None


# =========================================================================
# Monitor detection and sorting
# =========================================================================

class TestMonitorDetection:

    def test_triple_monitor_sorted_by_distance(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        monitors = mgr.get_monitors()
        assert len(monitors) == 3
        # Primary (origin) should be id 0
        assert monitors[0]["name"] == "HDMI-A-1"
        assert monitors[0]["id"] == 0
        # DP-1 at x=2560 should be id 1
        assert monitors[1]["name"] == "DP-1"
        assert monitors[1]["id"] == 1
        # DP-2 at x=5120 should be id 2
        assert monitors[2]["name"] == "DP-2"
        assert monitors[2]["id"] == 2

    def test_single_monitor(self):
        mgr = _make_manager(SINGLE_MONITOR)
        monitors = mgr.get_monitors()
        assert len(monitors) == 1
        assert monitors[0]["name"] == "eDP-1"
        assert monitors[0]["scale"] == 1.25

    def test_stacked_monitors_sorted_by_distance(self):
        mgr = _make_manager(STACKED_MONITORS)
        monitors = mgr.get_monitors()
        # Origin monitor first
        assert monitors[0]["name"] == "DP-1"
        assert monitors[0]["y"] == 0
        # Below monitor second
        assert monitors[1]["name"] == "DP-2"
        assert monitors[1]["y"] == 2160

    def test_fallback_default_when_hyprctl_fails(self):
        MonitorManager._instance = None
        with patch("utils.monitor_manager.subprocess.run", side_effect=FileNotFoundError):
            with patch.object(MonitorManager, "_fallback_to_gtk"):
                mgr = MonitorManager()
        # Should have the hardcoded default
        monitors = mgr.get_monitors()
        assert len(monitors) == 1
        assert monitors[0]["name"] == "default"
        assert monitors[0]["width"] == 1920

    def test_get_monitors_returns_copy(self):
        mgr = _make_manager(SINGLE_MONITOR)
        m1 = mgr.get_monitors()
        m2 = mgr.get_monitors()
        assert m1 is not m2
        assert m1 == m2


# =========================================================================
# Focused monitor
# =========================================================================

class TestFocusedMonitor:

    def test_initial_focused_monitor(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        assert mgr.get_focused_monitor_id() == 0
        focused = mgr.get_focused_monitor()
        assert focused["name"] == "HDMI-A-1"

    def test_focus_change_via_callback(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        mgr._on_monitor_focused("DP-1", 1, 3)
        assert mgr.get_focused_monitor_id() == 1


# =========================================================================
# get_monitor_by_id
# =========================================================================

class TestGetMonitorById:

    def test_existing_id(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        m = mgr.get_monitor_by_id(1)
        assert m is not None
        assert m["name"] == "DP-1"

    def test_nonexistent_id(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        assert mgr.get_monitor_by_id(99) is None

    def test_returns_copy(self):
        mgr = _make_manager(SINGLE_MONITOR)
        m1 = mgr.get_monitor_by_id(0)
        m2 = mgr.get_monitor_by_id(0)
        assert m1 is not m2


# =========================================================================
# Workspace ranges
# =========================================================================

class TestWorkspaceRange:

    def test_all_monitors_share_1_to_10(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        for monitor_id in range(3):
            assert mgr.get_workspace_range_for_monitor(monitor_id) == (1, 10)

    def test_unknown_monitor_still_returns_1_to_10(self):
        mgr = _make_manager(SINGLE_MONITOR)
        assert mgr.get_workspace_range_for_monitor(99) == (1, 10)


# =========================================================================
# Monitor scale
# =========================================================================

class TestMonitorScale:

    def test_scale_from_hyprland(self):
        mgr = _make_manager(SINGLE_MONITOR)
        assert mgr.get_monitor_scale(0) == 1.25

    def test_scale_default_for_unknown(self):
        mgr = _make_manager(SINGLE_MONITOR)
        assert mgr.get_monitor_scale(99) == 1.0

    def test_hidpi_scale(self):
        mgr = _make_manager(STACKED_MONITORS)
        assert mgr.get_monitor_scale(0) == 2.0
        assert mgr.get_monitor_scale(1) == 1.0


# =========================================================================
# Notch state management
# =========================================================================

class TestNotchState:

    def test_initial_state_closed(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        for i in range(3):
            assert mgr.is_notch_open(i) is False
            assert mgr.get_current_notch_module(i) is None

    def test_set_notch_open(self):
        mgr = _make_manager(SINGLE_MONITOR)
        mgr.set_notch_state(0, True, "dashboard")
        assert mgr.is_notch_open(0) is True
        assert mgr.get_current_notch_module(0) == "dashboard"

    def test_set_notch_closed_clears_module(self):
        mgr = _make_manager(SINGLE_MONITOR)
        mgr.set_notch_state(0, True, "launcher")
        mgr.set_notch_state(0, False)
        assert mgr.is_notch_open(0) is False
        assert mgr.get_current_notch_module(0) is None

    def test_close_all_notches_except(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        mgr.set_notch_state(0, True, "dashboard")
        mgr.set_notch_state(1, True, "launcher")
        mgr.set_notch_state(2, True, "power")
        mgr.close_all_notches_except(1)
        assert mgr.is_notch_open(0) is False
        assert mgr.is_notch_open(1) is True
        assert mgr.is_notch_open(2) is False


# =========================================================================
# Component instance registry
# =========================================================================

class TestInstanceRegistry:

    def test_register_and_retrieve(self):
        mgr = _make_manager(SINGLE_MONITOR)
        mock_bar = MagicMock()
        mock_notch = MagicMock()
        mgr.register_monitor_instances(0, {"bar": mock_bar, "notch": mock_notch})
        assert mgr.get_instance(0, "bar") is mock_bar
        assert mgr.get_instance(0, "notch") is mock_notch

    def test_unregistered_monitor_returns_empty(self):
        mgr = _make_manager(SINGLE_MONITOR)
        assert mgr.get_monitor_instances(5) == {}
        assert mgr.get_instance(5, "bar") is None

    def test_get_focused_instance(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        mock_bar = MagicMock()
        mgr.register_monitor_instances(0, {"bar": mock_bar})
        assert mgr.get_focused_instance("bar") is mock_bar


# =========================================================================
# Signal integration
# =========================================================================

class TestMonitorSignals:

    def test_monitor_changed_emitted_on_refresh(self):
        results = []
        mgr = _make_manager(SINGLE_MONITOR)
        mgr.monitor_changed.connect(lambda monitors: results.append(len(monitors)))

        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(TRIPLE_MONITOR)):
            mgr.refresh_monitors()

        assert results == [3]

    def test_notch_focus_changed_emitted(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        results = []
        mgr.notch_focus_changed.connect(lambda old, new: results.append((old, new)))
        mgr._on_monitor_focused("DP-1", 1, 3)
        assert results == [(0, 1)]

    def test_no_signal_when_focus_unchanged(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        results = []
        mgr.notch_focus_changed.connect(lambda old, new: results.append((old, new)))
        mgr._on_monitor_focused("HDMI-A-1", 0, 1)
        assert results == []  # same monitor, no switch


# =========================================================================
# Notch focus switching
# =========================================================================

class TestNotchFocusSwitch:

    def test_notch_transfers_to_new_monitor(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        mock_notch_0 = MagicMock()
        mock_notch_0.close_notch = MagicMock()
        mock_notch_1 = MagicMock()
        mock_notch_1.open_module = MagicMock()
        mgr.register_monitor_instances(0, {"notch": mock_notch_0})
        mgr.register_monitor_instances(1, {"notch": mock_notch_1})

        mgr.set_notch_state(0, True, "dashboard")
        mgr._on_monitor_focused("DP-1", 1, 3)

        # Old notch should have been closed
        mock_notch_0.close_notch.assert_called()
        # New notch should open with same module
        mock_notch_1.open_module.assert_called_with("dashboard")

    def test_no_transfer_when_notch_closed(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        mock_notch_1 = MagicMock()
        mgr.register_monitor_instances(1, {"notch": mock_notch_1})

        mgr._on_monitor_focused("DP-1", 1, 3)
        mock_notch_1.open_module.assert_not_called()


# =========================================================================
# Internal Signal class (from monitor_manager, not utils.signal)
# =========================================================================

class TestMonitorManagerSignalClass:

    def test_connect_and_emit(self):
        sig = Signal()
        results = []
        sig.connect(lambda x: results.append(x))
        sig.emit(42)
        assert results == [42]

    def test_error_doesnt_stop_others(self, capsys):
        sig = Signal()
        results = []

        def bad_cb():
            raise RuntimeError("boom")

        sig.connect(bad_cb)
        sig.connect(lambda: results.append("ok"))
        sig.emit()
        assert results == ["ok"]
        assert "Error in signal callback" in capsys.readouterr().out


# =========================================================================
# Singleton re-init guard
# =========================================================================

class TestSingletonBehavior:

    def test_second_init_is_noop(self):
        mgr = _make_manager(SINGLE_MONITOR)
        original_monitors = mgr.get_monitors()
        # Calling __init__ again should not re-run refresh
        mgr.__init__()
        assert mgr.get_monitors() == original_monitors

    def test_get_monitor_manager_returns_singleton(self):
        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(SINGLE_MONITOR)):
            mgr1 = get_monitor_manager()
            mgr2 = get_monitor_manager()
        assert mgr1 is mgr2

    def test_get_monitor_manager_creates_instance(self):
        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(SINGLE_MONITOR)):
            mgr = get_monitor_manager()
        assert mgr is not None
        assert len(mgr.get_monitors()) == 1


# =========================================================================
# get_monitor_for_workspace (hyprctl workspaces query)
# =========================================================================

class TestGetMonitorForWorkspace:

    def test_workspace_on_primary(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(WORKSPACE_DATA)):
            result = mgr.get_monitor_for_workspace(1)
        assert result == 0  # HDMI-A-1 is id 0

    def test_workspace_on_secondary(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(WORKSPACE_DATA)):
            result = mgr.get_monitor_for_workspace(3)
        assert result == 1  # DP-1 is id 1

    def test_workspace_on_tertiary(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(WORKSPACE_DATA)):
            result = mgr.get_monitor_for_workspace(4)
        assert result == 2  # DP-2 is id 2

    def test_nonexistent_workspace_returns_none(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(WORKSPACE_DATA)):
            result = mgr.get_monitor_for_workspace(99)
        assert result is None

    def test_hyprctl_failure_returns_none(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        with patch("utils.monitor_manager.subprocess.run", side_effect=subprocess.CalledProcessError(1, "hyprctl")):
            result = mgr.get_monitor_for_workspace(1)
        assert result is None

    def test_workspace_on_unknown_monitor_returns_none(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        bad_ws = json.dumps([{"id": 1, "monitor": "NONEXISTENT"}])
        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(bad_ws)):
            result = mgr.get_monitor_for_workspace(1)
        assert result is None


# =========================================================================
# GTK fallback paths
# =========================================================================

class TestGtkFallback:

    def test_fallback_to_gtk_populates_monitors(self):
        """Test that _fallback_to_gtk reads from GDK display."""
        MonitorManager._instance = None
        mock_monitor = MagicMock()
        mock_geometry = MagicMock()
        mock_geometry.width = 1920
        mock_geometry.height = 1080
        mock_geometry.x = 0
        mock_geometry.y = 0
        mock_monitor.get_geometry.return_value = mock_geometry
        mock_monitor.get_scale_factor.return_value = 1
        mock_monitor.get_model.return_value = "GDK-Monitor"

        mock_display = MagicMock()
        mock_display.get_n_monitors.return_value = 1
        mock_display.get_monitor.return_value = mock_monitor

        with patch("utils.monitor_manager.subprocess.run", side_effect=FileNotFoundError):
            with patch("utils.monitor_manager.Gdk.Display.get_default", return_value=mock_display):
                mgr = MonitorManager()

        monitors = mgr.get_monitors()
        assert len(monitors) == 1
        assert monitors[0]["name"] == "GDK-Monitor"
        assert monitors[0]["width"] == 1920
        assert monitors[0]["scale"] == 1

    def test_fallback_with_no_display_uses_default(self):
        """When GTK also fails, should get the hardcoded default."""
        MonitorManager._instance = None
        with patch("utils.monitor_manager.subprocess.run", side_effect=FileNotFoundError):
            with patch("utils.monitor_manager.Gdk.Display.get_default", return_value=None):
                mgr = MonitorManager()

        monitors = mgr.get_monitors()
        assert len(monitors) == 1
        assert monitors[0]["name"] == "default"

    def test_fallback_multiple_gtk_monitors(self):
        MonitorManager._instance = None

        def make_mock_monitor(name, x, scale):
            m = MagicMock()
            geo = MagicMock()
            geo.width, geo.height, geo.x, geo.y = 2560, 1440, x, 0
            m.get_geometry.return_value = geo
            m.get_scale_factor.return_value = scale
            m.get_model.return_value = name
            return m

        monitors_list = [
            make_mock_monitor("DP-1", 0, 1),
            make_mock_monitor("DP-2", 2560, 2),
        ]

        mock_display = MagicMock()
        mock_display.get_n_monitors.return_value = 2
        mock_display.get_monitor.side_effect = lambda i: monitors_list[i]

        with patch("utils.monitor_manager.subprocess.run", side_effect=FileNotFoundError):
            with patch("utils.monitor_manager.Gdk.Display.get_default", return_value=mock_display):
                mgr = MonitorManager()

        result = mgr.get_monitors()
        assert len(result) == 2
        assert result[0]["scale"] == 1
        assert result[1]["scale"] == 2

    def test_get_gtk_monitor_info_returns_list(self):
        """Test _get_gtk_monitor_info directly."""
        mgr = _make_manager(SINGLE_MONITOR)

        mock_monitor = MagicMock()
        mock_geo = MagicMock()
        mock_geo.width, mock_geo.height, mock_geo.x, mock_geo.y = 3840, 2160, 0, 0
        mock_monitor.get_geometry.return_value = mock_geo
        mock_monitor.get_scale_factor.return_value = 2
        mock_monitor.get_model.return_value = "HiDPI-Monitor"

        mock_display = MagicMock()
        mock_display.get_n_monitors.return_value = 1
        mock_display.get_monitor.return_value = mock_monitor

        with patch("utils.monitor_manager.Gdk.Display.get_default", return_value=mock_display):
            info = mgr._get_gtk_monitor_info()

        assert len(info) == 1
        assert info[0]["name"] == "HiDPI-Monitor"
        assert info[0]["width"] == 3840
        assert info[0]["scale"] == 2

    def test_get_gtk_monitor_info_no_display(self):
        mgr = _make_manager(SINGLE_MONITOR)
        with patch("utils.monitor_manager.Gdk.Display.get_default", return_value=None):
            info = mgr._get_gtk_monitor_info()
        assert info == []


# =========================================================================
# Monitor focus service integration
# =========================================================================

class TestMonitorFocusService:

    def test_set_monitor_focus_service(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        mock_service = MagicMock()
        mock_service.monitor_focused = Signal()
        mgr.set_monitor_focus_service(mock_service)
        assert mgr._monitor_focus_service is mock_service

    def test_focus_service_signal_triggers_update(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        mock_service = MagicMock()
        mock_service.monitor_focused = Signal()
        mgr.set_monitor_focus_service(mock_service)

        # Emit from the service signal
        mock_service.monitor_focused.emit("DP-1", 1, 3)
        assert mgr.get_focused_monitor_id() == 1

    def test_set_none_service(self):
        mgr = _make_manager(TRIPLE_MONITOR)
        mgr.set_monitor_focus_service(None)
        assert mgr._monitor_focus_service is None


# =========================================================================
# Edge cases
# =========================================================================

class TestEdgeCases:

    def test_json_decode_error_falls_back(self):
        """Invalid JSON from hyprctl should trigger fallback."""
        MonitorManager._instance = None
        bad_result = MagicMock()
        bad_result.stdout = "not valid json"
        with patch("utils.monitor_manager.subprocess.run", return_value=bad_result):
            with patch.object(MonitorManager, "_fallback_to_gtk"):
                mgr = MonitorManager()
        monitors = mgr.get_monitors()
        assert len(monitors) == 1
        assert monitors[0]["name"] == "default"

    def test_called_process_error_falls_back(self):
        MonitorManager._instance = None
        with patch("utils.monitor_manager.subprocess.run", side_effect=subprocess.CalledProcessError(1, "hyprctl")):
            with patch.object(MonitorManager, "_fallback_to_gtk"):
                mgr = MonitorManager()
        monitors = mgr.get_monitors()
        assert len(monitors) == 1
        assert monitors[0]["name"] == "default"

    def test_hypr_id_preserved(self):
        """Verify original Hyprland ID is kept alongside logical ID."""
        mgr = _make_manager(TRIPLE_MONITOR)
        monitors = mgr.get_monitors()
        # HDMI-A-1 has hypr_id=0, logical id=0
        assert monitors[0]["hypr_id"] == 0
        # DP-1 has hypr_id=1, logical id=1
        assert monitors[1]["hypr_id"] == 1

    def test_refresh_replaces_monitors(self):
        mgr = _make_manager(SINGLE_MONITOR)
        assert len(mgr.get_monitors()) == 1
        with patch("utils.monitor_manager.subprocess.run", return_value=_hyprctl_result(TRIPLE_MONITOR)):
            mgr.refresh_monitors()
        assert len(mgr.get_monitors()) == 3
