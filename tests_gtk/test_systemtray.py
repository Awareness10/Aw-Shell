"""Tray items must show on every bar, not only the first monitor's.

Each bar builds its own SystemTray. A process can only serve one
org.kde.StatusNotifierWatcher, so trays must share it; a second watcher never
receives RegisterStatusNotifierItem and its tray stays empty.
"""

import time

from conftest import pump
from gi.repository import Gio, GLib

SNI_XML = """<node><interface name="org.kde.StatusNotifierItem">
<property name="Id" type="s" access="read"/>
<property name="Title" type="s" access="read"/>
<property name="IconName" type="s" access="read"/>
<property name="Status" type="s" access="read"/>
<property name="Category" type="s" access="read"/>
</interface></node>"""


def _pump_until(condition, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        pump()
        time.sleep(0.01)
    return condition()


def _shows(tray, title: str) -> bool:
    return any(b.get_tooltip_text() == title for b in tray.get_children())


def _register_fake_item(title: str) -> Gio.DBusConnection:
    """Export an item on its own connection, like a real app would."""
    address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
    conn = Gio.DBusConnection.new_for_address_sync(
        address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None,
    )
    # The watcher claims its bus name asynchronously
    def watcher_owned() -> bool:
        reply = conn.call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
            "NameHasOwner", GLib.Variant("(s)", ("org.kde.StatusNotifierWatcher",)),
            GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, -1, None,
        )
        return reply.unpack()[0]

    assert _pump_until(watcher_owned), "no StatusNotifierWatcher on the bus"

    values = {"Id": title, "Title": title, "IconName": "image-missing",
              "Status": "Active", "Category": "ApplicationStatus"}
    interface = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
    conn.register_object(
        "/StatusNotifierItem", interface, None,
        lambda _c, _s, _p, _i, prop: GLib.Variant("s", values[prop]), None,
    )
    # Async: the watcher answers from this same main loop
    conn.call(
        "org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
        "org.kde.StatusNotifierWatcher", "RegisterStatusNotifierItem",
        GLib.Variant("(s)", ("/StatusNotifierItem",)),
        None, Gio.DBusCallFlags.NONE, 2000, None, None,
    )
    return conn


def test_item_shows_on_every_tray():
    from modules.systemtray import SystemTray

    first, second = SystemTray(), SystemTray()
    conn = _register_fake_item("every-tray")
    try:
        assert _pump_until(lambda: _shows(first, "every-tray")
                           and _shows(second, "every-tray")), (
            f"first={_shows(first, 'every-tray')} second={_shows(second, 'every-tray')}"
        )
    finally:
        conn.close_sync(None)
        first.destroy()
        second.destroy()
        pump()


def test_tray_built_later_shows_existing_items():
    from modules.systemtray import SystemTray

    first = SystemTray()
    conn = _register_fake_item("existing-item")
    try:
        assert _pump_until(lambda: _shows(first, "existing-item"))
        late = SystemTray()
        pump()
        assert _shows(late, "existing-item")
        late.destroy()
    finally:
        conn.close_sync(None)
        first.destroy()
        pump()


def test_item_removed_from_every_tray():
    from modules.systemtray import SystemTray

    first, second = SystemTray(), SystemTray()
    conn = _register_fake_item("removed-item")
    try:
        assert _pump_until(lambda: _shows(first, "removed-item")
                           and _shows(second, "removed-item"))
        conn.close_sync(None)  # app quits: its bus name vanishes
        assert _pump_until(lambda: not _shows(first, "removed-item")
                           and not _shows(second, "removed-item"))
    finally:
        first.destroy()
        second.destroy()
        pump()


def test_destroyed_tray_stops_listening():
    from modules.systemtray import SystemTray, _get_watcher

    tray = SystemTray()
    handler = tray._watcher_handler
    tray.destroy()
    pump()
    assert not _get_watcher().handler_is_connected(handler)
