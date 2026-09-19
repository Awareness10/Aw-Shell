"""Smoke tests: every widget builds against real GTK without raising."""

import importlib
from unittest.mock import MagicMock

import pytest

# Stand-ins for the parent a widget is normally built inside (Notch / Widgets)
NOTCH = {"notch": MagicMock(name="notch")}
WIDGETS_PARENT = {"widgets": MagicMock(name="widgets")}

# (module, class, kwargs)
WIDGETS = [
    ("modules.corners", "Corners", {"monitor_id": 0}),
    ("modules.bar", "Bar", {"monitor_id": 0}),
    ("modules.dock", "Dock", {"monitor_id": 0}),
    ("modules.notch", "Notch", {"monitor_id": 0}),
    ("modules.calendar", "Calendar", {}),
    ("modules.calendar", "Calendar", {"view_mode": "week"}),
    ("modules.cliphist", "ClipHistory", NOTCH),
    ("modules.controls", "ControlSliders", {}),
    ("modules.controls", "ControlSmall", {}),
    ("modules.emoji", "EmojiPicker", NOTCH),
    ("modules.kanban", "Kanban", {}),
    ("modules.launcher", "AppLauncher", NOTCH),
    ("modules.metrics", "Metrics", {}),
    ("modules.metrics", "MetricsSmall", {}),
    ("modules.metrics", "Battery", {}),
    ("modules.metrics", "NetworkApplet", {}),
    ("modules.mixer", "Mixer", {}),
    ("modules.bluetooth", "BluetoothConnections", WIDGETS_PARENT),
    ("modules.network", "NetworkConnections", {}),
    ("modules.buttons", "Buttons", WIDGETS_PARENT),
    ("modules.overview", "Overview", {"monitor_id": 0}),
    ("modules.pins", "Pins", {}),
    ("modules.player", "Player", {}),
    ("modules.player", "PlayerSmall", {}),
    ("modules.power", "PowerMenu", NOTCH),
    ("modules.systemprofiles", "Systemprofiles", {}),
    ("modules.systemtray", "SystemTray", {}),
    ("modules.tmux", "TmuxManager", NOTCH),
    ("modules.tools", "Toolbox", NOTCH),
    ("modules.wallpapers", "WallpaperSelector", {}),
    ("modules.weather", "Weather", {}),
    ("modules.notifications", "NotificationHistory", {}),
]


def _id(entry):
    module, cls, kwargs = entry
    args = ", ".join(f"{k}={v}" for k, v in kwargs.items() if not isinstance(v, MagicMock))
    return f"{cls}({args})"


@pytest.mark.parametrize("entry", WIDGETS, ids=[_id(w) for w in WIDGETS])
def test_widget_builds(entry, run_pending):
    module, cls, kwargs = entry
    widget = getattr(importlib.import_module(module), cls)(**kwargs)
    run_pending()
    assert widget is not None
    widget.destroy()
    run_pending()


def test_notification_popup_builds(run_pending):
    from modules.notch import Notch
    from modules.notifications import NotificationPopup

    notch = Notch(monitor_id=0)
    popup = NotificationPopup(widgets=notch.dashboard.widgets)
    run_pending()
    assert popup is not None
    popup.destroy()
    notch.destroy()
