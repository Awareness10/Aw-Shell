"""Tests for utils/occlusion.py - per-monitor top-edge occlusion."""

from utils.occlusion import is_top_edge_occluded

# Side-by-side layout: ultrawide at the origin, 1080p to its right
LEFT = {"name": "DP-3", "x": 0, "y": 0, "width": 3440, "height": 1440, "scale": 1.0,
        "transform": 0, "activeWorkspace": {"id": 1}, "specialWorkspace": {"id": 0}}
RIGHT = {"name": "HDMI-A-1", "x": 3440, "y": 0, "width": 1920, "height": 1080, "scale": 1.0,
         "transform": 0, "activeWorkspace": {"id": 2}, "specialWorkspace": {"id": 0}}


def client(ws, at, size, **extra):
    return {"mapped": True, "hidden": False, "workspace": {"id": ws}, "at": at, "size": size, **extra}


def test_window_below_top_edge_does_not_occlude():
    assert not is_top_edge_occluded(LEFT, [client(1, [10, 50], [800, 600])])


def test_window_touching_top_edge_occludes():
    assert is_top_edge_occluded(LEFT, [client(1, [10, 20], [800, 600])])


def test_fullscreen_window_on_offset_monitor_occludes():
    # Global coordinates: the right monitor starts at x=3440
    assert is_top_edge_occluded(RIGHT, [client(2, [3440, 0], [1920, 1080])])


def test_window_on_other_monitor_does_not_occlude():
    fullscreen_left = client(1, [0, 0], [3440, 1440])
    assert is_top_edge_occluded(LEFT, [fullscreen_left])
    assert not is_top_edge_occluded(RIGHT, [fullscreen_left])


def test_window_on_inactive_workspace_is_ignored():
    assert not is_top_edge_occluded(LEFT, [client(5, [0, 0], [3440, 1440])])


def test_open_special_workspace_counts():
    monitor = {**LEFT, "specialWorkspace": {"id": -98}}
    assert is_top_edge_occluded(monitor, [client(-98, [100, 0], [800, 600])])


def test_unmapped_and_hidden_windows_are_ignored():
    clients = [
        client(1, [0, 0], [3440, 1440], mapped=False),
        client(1, [0, 0], [3440, 1440], hidden=True),
    ]
    assert not is_top_edge_occluded(LEFT, clients)


def test_scaled_monitor_uses_logical_width():
    # 3840px at scale 2 spans 1920 logical px; a window at x=2000 is past it
    monitor = {**LEFT, "width": 3840, "height": 2160, "scale": 2.0}
    assert not is_top_edge_occluded(monitor, [client(1, [2000, 0], [500, 500])])
    assert is_top_edge_occluded(monitor, [client(1, [1800, 0], [500, 500])])
