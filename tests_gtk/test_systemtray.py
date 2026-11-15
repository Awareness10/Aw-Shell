"""Tray items must show on every bar, not only the first monitor's.

Each bar builds its own SystemTray. A process can only serve one
org.kde.StatusNotifierWatcher, so trays must share it; a second watcher never
receives RegisterStatusNotifierItem and its tray stays empty.
"""

import time
from types import SimpleNamespace

from conftest import pump
from gi.repository import Gio, GLib

SNI_XML = """<node><interface name="org.kde.StatusNotifierItem">
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<signal name="NewTitle"/>
<property name="Menu" type="o" access="read"/>
<property name="IconPixmap" type="a(iiay)" access="read"/>
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


def _register_fake_item(title: str, calls: list | None = None,
                        **props) -> Gio.DBusConnection:
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
              "Status": "Active", "Category": "ApplicationStatus", "Menu": "/",
              "IconPixmap": [], **props}
    interface = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
    signatures = {p.name: p.signature for p in interface.properties}

    def method(_c, _s, _p, _i, name, params, invocation):
        if calls is not None:
            calls.append((name, params.unpack()))
        invocation.return_value(None)

    conn.register_object(
        "/StatusNotifierItem", interface, method,
        lambda _c, _s, _p, _i, prop: GLib.Variant(signatures[prop], values[prop]), None,
    )
    conn.values = values  # tests change them, then emit a New* signal
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


def _click(tray, title: str, button: int):
    identifier, btn = next((i, b) for i, b in tray.buttons_by_id.items()
                           if b.get_tooltip_text() == title)
    event = SimpleNamespace(button=button, x_root=12.0, y_root=34.0)
    tray.on_button_click(btn, tray.items_by_id[identifier], event)


def test_clicks_activate_and_open_the_context_menu():
    """Left click: Activate; right click without a dbusmenu: ContextMenu."""
    from modules.systemtray import SystemTray

    tray = SystemTray()
    calls = []
    conn = _register_fake_item("clicks", calls)
    try:
        assert _pump_until(lambda: _shows(tray, "clicks"))
        _click(tray, "clicks", 1)
        _click(tray, "clicks", 2)  # middle: nothing, as before
        _click(tray, "clicks", 3)
        assert _pump_until(lambda: len(calls) == 2), calls
        assert calls == [("Activate", (12, 34)), ("ContextMenu", (12, 34))]
    finally:
        conn.close_sync(None)
        tray.destroy()
        pump()


def test_item_with_a_dbusmenu_gets_a_gtk_menu():
    from gi.repository import DbusmenuGtk3, Gtk

    from modules import systemtray

    tray = systemtray.SystemTray()
    conn = _register_fake_item("with-menu", Menu="/MenuBar")
    try:
        assert _pump_until(lambda: _shows(tray, "with-menu"))
        item = next(i for i in tray.items_by_id.values() if i.get_title() == "with-menu")
        menu = systemtray._get_menu(item)
        assert isinstance(menu, DbusmenuGtk3.Menu) and isinstance(menu, Gtk.Menu)
        assert systemtray._get_menu(item) is menu  # built once, shared by every tray
        conn.close_sync(None)
        assert _pump_until(lambda: item not in systemtray._menus)
    finally:
        if not conn.is_closed():
            conn.close_sync(None)
        tray.destroy()
        pump()


def test_icon_from_pixmap():
    from modules.systemtray import SystemTray

    tray = SystemTray(pixel_size=20)
    red = bytes([255, 255, 0, 0]) * (24 * 24)  # opaque red, ARGB
    conn = _register_fake_item("pixmap", IconName="", IconPixmap=[(24, 24, red)])
    try:
        assert _pump_until(lambda: _shows(tray, "pixmap"))
        btn = next(b for b in tray.get_children() if b.get_tooltip_text() == "pixmap")
        pixbuf = btn.get_image().get_pixbuf()
        assert (pixbuf.get_width(), pixbuf.get_height()) == (20, 20)
        assert pixbuf.get_pixels()[:4] == bytes([255, 0, 0, 255])
    finally:
        conn.close_sync(None)
        tray.destroy()
        pump()


def test_new_title_updates_the_tooltip():
    from modules.systemtray import SystemTray

    tray = SystemTray()
    conn = _register_fake_item("old-title")
    try:
        assert _pump_until(lambda: _shows(tray, "old-title"))
        conn.values["Title"] = "new-title"
        conn.emit_signal(None, "/StatusNotifierItem", "org.kde.StatusNotifierItem",
                         "NewTitle", None)
        assert _pump_until(lambda: _shows(tray, "new-title"))
    finally:
        conn.close_sync(None)
        tray.destroy()
        pump()
