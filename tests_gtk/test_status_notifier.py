"""services/status_notifier.py against real D-Bus.

Each test gets its own dbus-daemon, so the watcher here never meets the one
the shell's trays share (tests_gtk/test_systemtray.py) on the sandbox bus.
"""

import subprocess
import time

import pytest
from conftest import pump
from gi.repository import GdkPixbuf, Gio, GLib

from services.status_notifier import (
    WATCHER_NAME,
    Pixmap,
    Watcher,
    pixmap_to_pixbuf,
)

SNI_XML = """<node><interface name="org.kde.StatusNotifierItem">
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="SecondaryActivate">
  <arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
<signal name="NewIcon"/>
<signal name="NewTitle"/>
<signal name="NewStatus"><arg type="s"/></signal>
<property name="Id" type="s" access="read"/>
<property name="Title" type="s" access="read"/>
<property name="Status" type="s" access="read"/>
<property name="IconName" type="s" access="read"/>
<property name="IconThemePath" type="s" access="read"/>
<property name="IconPixmap" type="a(iiay)" access="read"/>
<property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
<property name="Menu" type="o" access="read"/>
<property name="ItemIsMenu" type="b" access="read"/>
</interface></node>"""

SNI_IFACE = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
WATCHER_XML = """<node><interface name="org.kde.StatusNotifierWatcher">
<method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
<method name="RegisterStatusNotifierHost"><arg type="s" direction="in"/></method>
<property name="RegisteredStatusNotifierItems" type="as" access="read"/>
<signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
<signal name="StatusNotifierItemUnregistered"><arg type="s"/></signal>
</interface></node>"""


def pump_until(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        pump()
        time.sleep(0.01)
    return condition()


@pytest.fixture
def bus():
    """A private bus; returns a function that opens a new connection to it."""
    proc = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                            stdout=subprocess.PIPE, text=True)
    address = proc.stdout.readline().strip()
    conns = []

    def connect() -> Gio.DBusConnection:
        conn = Gio.DBusConnection.new_for_address_sync(
            address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None,
        )
        conns.append(conn)
        return conn

    yield connect
    for conn in conns:
        if not conn.is_closed():
            conn.close_sync(None)
    pump()
    proc.terminate()
    proc.wait(timeout=5)


class FakeApp:
    """An app exporting a StatusNotifierItem on its own connection."""

    def __init__(self, conn, path="/StatusNotifierItem", **props):
        self.conn = conn
        self.path = path
        self.calls = []
        self.props = {"Id": "app", "Title": "App", "Status": "Active", "IconName": "app",
                      "IconThemePath": "", "IconPixmap": [], "ToolTip": ("", [], "", ""),
                      "Menu": "/MenuBar", "ItemIsMenu": False, **props}
        conn.register_object(path, SNI_IFACE, self._method, self._get, None)

    def _method(self, _c, _sender, _path, _iface, method, params, invocation):
        self.calls.append((method, params.unpack()))
        invocation.return_value(None)

    def _get(self, _c, _sender, _path, _iface, prop):
        types = {p.name: p.signature for p in SNI_IFACE.properties}
        return GLib.Variant(types[prop], self.props[prop])

    def register(self, service: str | None = None, watcher_conn=None):
        self.conn.call(
            WATCHER_NAME, "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher",
            "RegisterStatusNotifierItem", GLib.Variant("(s)", (service or self.path,)),
            None, Gio.DBusCallFlags.NONE, 2000, None, None,
        )

    def emit(self, signal: str, params=None):
        self.conn.emit_signal(None, self.path, "org.kde.StatusNotifierItem", signal, params)

    @property
    def name(self) -> str:
        return self.conn.get_unique_name()


def _owned(conn) -> bool:
    reply = conn.call_sync(
        "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "NameHasOwner", GLib.Variant("(s)", (WATCHER_NAME,)),
        GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, -1, None,
    )
    return reply.unpack()[0]


def _watcher(bus) -> tuple[Watcher, list]:
    watcher = Watcher(bus())
    events = []
    watcher.connect("item-added", lambda _w, i: events.append(("added", i)))
    watcher.connect("item-removed", lambda _w, i: events.append(("removed", i)))
    assert pump_until(lambda: watcher.is_owner)
    return watcher, events


def test_path_registration_adds_item_with_its_properties(bus):
    watcher, events = _watcher(bus)
    app = FakeApp(bus(), Title="Hello", IconPixmap=[(2, 2, bytes(16))],
                  ToolTip=("tip-icon", [], "Tip", "Body"))
    app.register()
    identifier = app.name + "/StatusNotifierItem"
    assert pump_until(lambda: events == [("added", identifier)])
    item = watcher.get_item_for_identifier(identifier)
    assert watcher.get_items() == [identifier]
    assert item.get_title() == "Hello"
    assert item.get_status() == "Active"
    assert item.get_icon_name() == "app"
    assert item.get_icon_pixmaps() == [Pixmap(2, 2, bytes(16))]
    assert item.get_tooltip().title == "Tip"
    assert item.get_menu_path() == "/MenuBar"
    assert item.get_item_is_menu() is False


def test_ayatana_path_and_bus_name_forms(bus):
    watcher, events = _watcher(bus)
    ayatana = FakeApp(bus(), path="/org/ayatana/NotificationItem/thing")
    ayatana.register()
    named_conn = bus()
    Gio.bus_own_name_on_connection(named_conn, "org.example.Tray", Gio.BusNameOwnerFlags.NONE,
                                   None, None)
    named = FakeApp(named_conn)
    pump_until(lambda: False, timeout=0.2)  # let it own the name
    named.register("org.example.Tray")
    assert pump_until(lambda: len(events) == 2)
    assert set(watcher.get_items()) == {
        ayatana.name + "/org/ayatana/NotificationItem/thing",
        "org.example.Tray/StatusNotifierItem",
    }


def test_watcher_property_lists_items(bus):
    watcher, events = _watcher(bus)
    app = FakeApp(bus())
    app.register()
    assert pump_until(lambda: events)
    client = bus()
    replies = []
    client.call(WATCHER_NAME, "/StatusNotifierWatcher", "org.freedesktop.DBus.Properties",
                "GetAll", GLib.Variant("(s)", ("org.kde.StatusNotifierWatcher",)), None,
                Gio.DBusCallFlags.NONE, 2000, None,
                lambda c, r: replies.append(c.call_finish(r).unpack()[0]))
    assert pump_until(lambda: replies)
    assert replies[0]["RegisteredStatusNotifierItems"] == [app.name + "/StatusNotifierItem"]
    assert replies[0]["IsStatusNotifierHostRegistered"] is True
    assert replies[0]["ProtocolVersion"] == 0


def test_reregistration_is_ignored_and_vanished_app_removed(bus):
    watcher, events = _watcher(bus)
    app = FakeApp(bus())
    app.register()
    assert pump_until(lambda: len(events) == 1)
    app.register()
    pump_until(lambda: False, timeout=0.3)
    assert len(events) == 1
    item = watcher.get_item_for_identifier(events[0][1])
    removed = []
    item.connect("removed", lambda _i: removed.append(True))
    app.conn.close_sync(None)
    assert pump_until(lambda: events[-1][0] == "removed")
    assert removed == [True]
    assert watcher.get_items() == []


def test_new_signals_refresh_properties(bus):
    watcher, events = _watcher(bus)
    app = FakeApp(bus())
    app.register()
    assert pump_until(lambda: events)
    item = watcher.get_item_for_identifier(events[0][1])
    seen = []
    item.connect("icon-changed", lambda _i: seen.append("icon"))
    item.connect("changed", lambda _i: seen.append("changed"))
    app.props["IconName"] = "other"
    app.emit("NewIcon")
    assert pump_until(lambda: seen == ["icon", "changed"])
    assert item.get_icon_name() == "other"
    app.props["Title"] = "Renamed"
    app.emit("NewTitle")
    assert pump_until(lambda: seen[-1:] == ["changed"] and item.get_title() == "Renamed")


def test_item_methods_reach_the_app(bus):
    watcher, events = _watcher(bus)
    app = FakeApp(bus())
    app.register()
    assert pump_until(lambda: events)
    item = watcher.get_item_for_identifier(events[0][1])
    item.activate(10, 20)
    item.secondary_activate(1, 2)
    item.context_menu(3, 4)
    item.scroll(-1, "vertical")
    assert pump_until(lambda: len(app.calls) == 4)
    assert app.calls == [("Activate", (10, 20)), ("SecondaryActivate", (1, 2)),
                         ("ContextMenu", (3, 4)), ("Scroll", (-1, "vertical"))]


def test_host_of_another_watcher(bus):
    """Another watcher owns the name: the tray shows that watcher's items."""
    other = bus()
    items = []
    hosts = []
    iface = Gio.DBusNodeInfo.new_for_xml(WATCHER_XML).interfaces[0]

    def method(_c, sender, _p, _i, name, params, invocation):
        if name == "RegisterStatusNotifierHost":
            hosts.append(params.unpack()[0])
        invocation.return_value(None)

    other.register_object("/StatusNotifierWatcher", iface, method,
                          lambda *_: GLib.Variant("as", items), None)
    Gio.bus_own_name_on_connection(other, WATCHER_NAME, Gio.BusNameOwnerFlags.NONE, None, None)
    assert pump_until(lambda: _owned(other))

    early = FakeApp(bus())
    items.append(early.name + "/StatusNotifierItem")
    watcher = Watcher(bus())
    added, removed = [], []
    watcher.connect("item-added", lambda _w, i: added.append(i))
    watcher.connect("item-removed", lambda _w, i: removed.append(i))
    assert pump_until(lambda: added == [items[0]])
    assert not watcher.is_owner
    assert hosts and hosts[0].startswith("org.kde.StatusNotifierHost-")

    late = FakeApp(bus(), path="/org/ayatana/NotificationItem/late")
    late_id = late.name + "/org/ayatana/NotificationItem/late"
    other.emit_signal(None, "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher",
                      "StatusNotifierItemRegistered", GLib.Variant("(s)", (late_id,)))
    assert pump_until(lambda: late_id in added)
    other.emit_signal(None, "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher",
                      "StatusNotifierItemUnregistered", GLib.Variant("(s)", (late_id,)))
    assert pump_until(lambda: removed == [late_id])

    # The other watcher quits: this one takes the name over and keeps its items
    other.close_sync(None)
    assert pump_until(lambda: watcher.is_owner)
    assert watcher.get_items() == [items[0]]


def test_pixmap_to_pixbuf_converts_argb_and_scales():
    red = bytes([255, 255, 0, 0]) * 4  # opaque red, ARGB
    pixbuf = pixmap_to_pixbuf(Pixmap(2, 2, red), 0)
    assert (pixbuf.get_width(), pixbuf.get_height(), pixbuf.get_has_alpha()) == (2, 2, True)
    assert pixbuf.get_pixels()[:4] == bytes([255, 0, 0, 255])
    scaled = pixmap_to_pixbuf(Pixmap(2, 2, red), 16, GdkPixbuf.InterpType.NEAREST)
    assert (scaled.get_width(), scaled.get_height()) == (16, 16)
    assert pixmap_to_pixbuf(Pixmap(2, 2, bytes(3)), 16) is None
