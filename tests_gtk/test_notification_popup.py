"""The notification popup opens on the focused monitor.

It only moves while nothing is on screen, so a visible stack never jumps
between monitors.
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from conftest import pump
from gi.repository import Gio, GLib


def _pump_until(condition, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        pump()
        time.sleep(0.01)
    return condition()


def _notify(summary: str) -> None:
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    # The server claims its bus name asynchronously
    def server_owned() -> bool:
        reply = bus.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "NameHasOwner", GLib.Variant("(s)", ("org.freedesktop.Notifications",)),
            GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, -1, None,
        )
        return reply.unpack()[0]

    assert _pump_until(server_owned), "no notification server on the bus"

    # Async: the notification server answers from this same main loop
    bus.call(
        "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications", "Notify",
        GLib.Variant("(susssasa{sv}i)", ("test", 0, "", summary, "", [], {}, -1)),
        None, Gio.DBusCallFlags.NONE, 2000, None, None,
    )


def test_before_show_runs_only_when_nothing_on_screen():
    from modules.notifications import NotificationContainer, NotificationHistory

    shown_before = []
    container = NotificationContainer(
        NotificationHistory(),
        before_show=lambda: shown_before.append(len(container.notifications)),
    )
    try:
        _notify("first")
        assert _pump_until(lambda: len(container.notifications) == 1)
        _notify("second")
        assert _pump_until(lambda: len(container.notifications) == 2)
        assert shown_before == [0]
    finally:
        container.destroy()
        pump()



def test_new_container_takes_over_the_server():
    """The D-Bus server is process-wide (fabric can't register a second one);
    a destroyed container must stop receiving and the next one must receive."""
    from modules.notifications import NotificationContainer, NotificationHistory

    first = NotificationContainer(NotificationHistory())
    first.destroy()
    pump()
    second = NotificationContainer(NotificationHistory())
    try:
        _notify("after rebuild")
        assert _pump_until(lambda: len(second.notifications) == 1)
        assert first.notifications == []
    finally:
        second.destroy()
        pump()

def test_popup_follows_focus_to_shown_monitors(monkeypatch):
    from modules.notifications import NotificationPopup

    manager = MagicMock()
    monkeypatch.setattr("utils.monitor_manager.get_monitor_manager", lambda: manager)
    popup = SimpleNamespace(_follow_focus_monitors=[0, 1], monitor=0)

    manager.query_focused_monitor_id.return_value = 1
    NotificationPopup._move_to_focused_monitor(popup)
    assert popup.monitor == 1

    # Focus on a monitor the shell isn't shown on, or unknown: stay put
    for focused in (2, None):
        manager.query_focused_monitor_id.return_value = focused
        NotificationPopup._move_to_focused_monitor(popup)
        assert popup.monitor == 1


def test_popup_without_follow_list_stays(monkeypatch):
    from modules.notifications import NotificationPopup

    manager = MagicMock()
    monkeypatch.setattr("utils.monitor_manager.get_monitor_manager", lambda: manager)
    popup = SimpleNamespace(_follow_focus_monitors=None, monitor=0)

    NotificationPopup._move_to_focused_monitor(popup)
    assert popup.monitor == 0
    manager.query_focused_monitor_id.assert_not_called()
