"""System tray backend: StatusNotifierWatcher/host and items over Gio D-Bus.

Implements the (KDE/freedesktop) StatusNotifierItem protocol in Python so the
tray needs no compiled library:

- Watcher owns org.kde.StatusNotifierWatcher (/StatusNotifierWatcher), takes
  item registrations and drops items whose bus name vanishes. When another
  watcher already owns the name it acts as a host of that watcher instead
  (and takes the name over if that watcher goes away).
- Item wraps one org.kde.StatusNotifierItem: cached properties, refreshed on
  the item's New* signals, and the Activate/ContextMenu/... methods.
- pick_pixmap / pixmap_to_pixbuf turn the IconPixmap property (ARGB32 in
  network byte order) into a GdkPixbuf.

No GTK widgets here; modules/systemtray.py builds the buttons and menus.
"""

import itertools
import os
from collections import namedtuple

from gi.repository import GdkPixbuf, Gio, GLib, GObject
from loguru import logger

WATCHER_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
WATCHER_IFACE = "org.kde.StatusNotifierWatcher"
ITEM_IFACE = "org.kde.StatusNotifierItem"
DEFAULT_ITEM_PATH = "/StatusNotifierItem"
CALL_TIMEOUT_MS = 5000

WATCHER_XML = """<node>
  <interface name="org.kde.StatusNotifierWatcher">
    <method name="RegisterStatusNotifierItem"><arg name="service" type="s" direction="in"/></method>
    <method name="RegisterStatusNotifierHost"><arg name="service" type="s" direction="in"/></method>
    <property name="RegisteredStatusNotifierItems" type="as" access="read"/>
    <property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
    <property name="ProtocolVersion" type="i" access="read"/>
    <signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
    <signal name="StatusNotifierItemUnregistered"><arg type="s"/></signal>
    <signal name="StatusNotifierHostRegistered"/>
    <signal name="StatusNotifierHostUnregistered"/>
  </interface>
</node>"""

Pixmap = namedtuple("Pixmap", "width height data")
Tooltip = namedtuple("Tooltip", "icon_name icon_pixmaps title description")


# ── Pure helpers ──

def parse_registration(service: str, sender: str) -> tuple[str, str]:
    """(bus name, object path) for a RegisterStatusNotifierItem call.

    Items register either with their bus name (path defaults to
    /StatusNotifierItem) or with an object path on the sender's connection
    (libappindicator/Ayatana: /org/ayatana/NotificationItem/<id>). Some send
    "<bus name>/<path>".
    """
    if not service:
        return sender, DEFAULT_ITEM_PATH
    if service.startswith("/"):
        return sender, service
    if "/" in service:
        name, path = service.split("/", 1)
        return name or sender, "/" + path
    return service, DEFAULT_ITEM_PATH


def parse_identifier(identifier: str) -> tuple[str, str]:
    """(bus name, object path) from a RegisteredStatusNotifierItems entry,
    "<bus name><path>" or a bare bus name (KDE's watcher for name-only items)."""
    if "/" in identifier:
        name, path = identifier.split("/", 1)
        return name, "/" + path
    return identifier, DEFAULT_ITEM_PATH


def _to_pixmaps(value) -> list[Pixmap]:
    pixmaps = []
    for entry in value or []:
        try:
            width, height, data = entry
            pixmaps.append(Pixmap(int(width), int(height), bytes(data)))
        except (TypeError, ValueError):
            continue
    return pixmaps


def pick_pixmap(pixmaps, size: int) -> Pixmap | None:
    """The smallest usable pixmap at least size x size, else the largest one."""
    usable = [p for p in pixmaps or [] if p.width > 0 and p.height > 0
              and len(p.data) >= p.width * p.height * 4]
    if not usable:
        return None
    big_enough = [p for p in usable if p.width >= size and p.height >= size]
    if big_enough:
        return min(big_enough, key=lambda p: p.width * p.height)
    return max(usable, key=lambda p: p.width * p.height)


def argb_to_rgba(data: bytes, width: int, height: int) -> bytes:
    """ARGB32 in network byte order (A, R, G, B per pixel) -> RGBA bytes."""
    n = width * height * 4
    src = bytes(data[:n])
    if width <= 0 or height <= 0 or len(src) < n:
        raise ValueError(f"pixmap data is {len(src)} bytes, {width}x{height} needs {n}")
    out = bytearray(n)
    out[0::4] = src[1::4]
    out[1::4] = src[2::4]
    out[2::4] = src[3::4]
    out[3::4] = src[0::4]
    return bytes(out)


def pixmap_to_pixbuf(pixmap: Pixmap, size: int = 0,
                     interp=GdkPixbuf.InterpType.HYPER) -> GdkPixbuf.Pixbuf | None:
    """A GdkPixbuf of the pixmap, scaled to size x size unless size is 0."""
    try:
        rgba = argb_to_rgba(pixmap.data, pixmap.width, pixmap.height)
    except ValueError as e:
        logger.debug(f"[Tray] Bad pixmap: {e}")
        return None
    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(rgba), GdkPixbuf.Colorspace.RGB, True, 8,
        pixmap.width, pixmap.height, pixmap.width * 4,
    )
    if size > 0 and (pixmap.width != size or pixmap.height != size):
        return pixbuf.scale_simple(size, size, interp)
    return pixbuf


# ── Item ──

_ICON_SIGNALS = {"NewIcon", "NewAttentionIcon", "NewOverlayIcon"}
_OTHER_SIGNALS = {"NewTitle", "NewToolTip", "NewStatus", "NewMenu"}


class Item(GObject.Object):
    """One org.kde.StatusNotifierItem.

    Signals: ready (properties loaded), changed (any property refreshed),
    icon-changed (icon refreshed; changed follows), removed (the item left
    the bus or failed to load).
    """

    __gsignals__ = {
        "ready": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "icon-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "removed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, connection: Gio.DBusConnection, bus_name: str, object_path: str):
        super().__init__()
        self._conn = connection
        self.bus_name = bus_name
        self.object_path = object_path
        self.identifier = bus_name + object_path
        self._props: dict = {}
        self._is_ready = False
        self._is_removed = False
        self._fetching = False
        self._refetch = False
        self._pending_icon = False
        self._pending_other = False
        self._subscription = 0
        self.owner = bus_name if bus_name.startswith(":") else ""
        self._watch = Gio.bus_watch_name_on_connection(
            connection, bus_name, Gio.BusNameWatcherFlags.NONE,
            None, self._on_name_vanished,
        )
        if bus_name.startswith(":"):
            self._start(bus_name)
        else:
            # Signals carry the sender's unique name; match on that
            connection.call(
                "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                "GetNameOwner", GLib.Variant("(s)", (bus_name,)), GLib.VariantType("(s)"),
                Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None, self._on_owner,
            )

    def _on_owner(self, conn, result):
        try:
            owner = conn.call_finish(result).unpack()[0]
        except GLib.Error as e:
            logger.warning(f"[Tray] No owner for {self.bus_name}: {e.message}")
            self.mark_removed()
            return
        self._start(owner)

    def _start(self, owner: str):
        if self._is_removed:
            return
        self.owner = owner
        self._subscription = self._conn.signal_subscribe(
            owner, ITEM_IFACE, None, self.object_path, None,
            Gio.DBusSignalFlags.NONE, self._on_item_signal,
        )
        self._fetch()

    # Properties

    def _fetch(self):
        if self._fetching:
            self._refetch = True
            return
        self._fetching = True
        self._conn.call(
            self.bus_name, self.object_path, "org.freedesktop.DBus.Properties", "GetAll",
            GLib.Variant("(s)", (ITEM_IFACE,)), GLib.VariantType("(a{sv})"),
            Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None, self._on_props,
        )

    def _on_props(self, conn, result):
        self._fetching = False
        if self._is_removed:
            return
        try:
            self._props = conn.call_finish(result).unpack()[0]
        except GLib.Error as e:
            if not self._is_ready:
                logger.warning(f"[Tray] Can't load item {self.identifier}: {e.message}")
                self.mark_removed()
                return
            logger.debug(f"[Tray] Can't refresh item {self.identifier}: {e.message}")
        if self._refetch:  # a signal came in while this call was out
            self._refetch = False
            self._fetch()
            return
        if not self._is_ready:
            self._is_ready = True
            self._pending_icon = self._pending_other = False
            self.emit("ready")
            return
        icon, other = self._pending_icon, self._pending_other
        self._pending_icon = self._pending_other = False
        if icon:
            self.emit("icon-changed")
        if icon or other:
            self.emit("changed")

    def _on_item_signal(self, _conn, _sender, _path, _iface, signal, params):
        if signal in _ICON_SIGNALS:
            self._pending_icon = True
        elif signal in _OTHER_SIGNALS:
            self._pending_other = True
            if signal == "NewStatus" and params is not None:
                self._props["Status"] = params.unpack()[0]
        else:
            return
        self._fetch()

    def _on_name_vanished(self, *_):
        self.mark_removed()

    def mark_removed(self):
        """The item is gone: stop listening and emit removed (once)."""
        if self._is_removed:
            return
        self._is_removed = True
        if self._subscription:
            self._conn.signal_unsubscribe(self._subscription)
            self._subscription = 0
        if self._watch:
            Gio.bus_unwatch_name(self._watch)
            self._watch = 0
        self.emit("removed")

    def is_ready(self) -> bool:
        return self._is_ready

    def is_removed(self) -> bool:
        return self._is_removed

    def _str(self, key: str) -> str:
        value = self._props.get(key)
        return value if isinstance(value, str) else ""

    def get_identifier(self) -> str:
        return self.identifier

    def get_bus_name(self) -> str:
        return self.bus_name

    def get_bus_path(self) -> str:
        return self.object_path

    def get_id(self) -> str:
        return self._str("Id")

    def get_category(self) -> str:
        return self._str("Category")

    def get_title(self) -> str:
        return self._str("Title")

    def get_status(self) -> str:
        return self._str("Status")

    def get_window_id(self) -> int:
        value = self._props.get("WindowId")
        return value if isinstance(value, int) else 0

    def get_icon_name(self) -> str:
        return self._str("IconName")

    def get_icon_theme_path(self) -> str:
        return self._str("IconThemePath")

    def get_icon_pixmaps(self) -> list[Pixmap]:
        return _to_pixmaps(self._props.get("IconPixmap"))

    def get_attention_icon_name(self) -> str:
        return self._str("AttentionIconName")

    def get_attention_icon_pixmaps(self) -> list[Pixmap]:
        return _to_pixmaps(self._props.get("AttentionIconPixmap"))

    def get_tooltip(self) -> Tooltip | None:
        value = self._props.get("ToolTip")
        try:
            icon_name, pixmaps, title, description = value
        except (TypeError, ValueError):
            return None
        return Tooltip(icon_name, _to_pixmaps(pixmaps), title, description)

    def get_menu_path(self) -> str:
        """The com.canonical.dbusmenu object path, or "" without a menu."""
        path = self._str("Menu")
        return "" if path in ("", "/") else path

    def get_item_is_menu(self) -> bool:
        return bool(self._props.get("ItemIsMenu", False))

    # Methods (asynchronous; errors are logged)

    def _call(self, method: str, params: GLib.Variant):
        def done(conn, result):
            try:
                conn.call_finish(result)
            except GLib.Error as e:
                logger.debug(f"[Tray] {method} on {self.identifier} failed: {e.message}")

        self._conn.call(
            self.bus_name, self.object_path, ITEM_IFACE, method, params, None,
            Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None, done,
        )

    def activate(self, x: int, y: int):
        self._call("Activate", GLib.Variant("(ii)", (int(x), int(y))))

    def secondary_activate(self, x: int, y: int):
        self._call("SecondaryActivate", GLib.Variant("(ii)", (int(x), int(y))))

    def context_menu(self, x: int, y: int):
        self._call("ContextMenu", GLib.Variant("(ii)", (int(x), int(y))))

    def scroll(self, delta: int, orientation: str):
        """orientation: "vertical" or "horizontal"."""
        self._call("Scroll", GLib.Variant("(is)", (int(delta), orientation)))


# ── Watcher ──

_host_counter = itertools.count(1)


class Watcher(GObject.Object):
    """The StatusNotifierWatcher (or a host of another one) and its items.

    Signals: item-added(identifier), item-removed(identifier). Items are
    added once their properties have loaded.
    """

    __gsignals__ = {
        "item-added": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "item-removed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, connection: Gio.DBusConnection | None = None):
        """connection: the bus to serve (default: the session bus)."""
        super().__init__()
        self._conn = None
        self._items: dict[str, Item] = {}
        self._pending: dict[str, Item] = {}
        self._hosts: set[str] = set()
        self._registration = 0
        self.is_owner = False
        self._host_name = None
        self._host_name_id = 0
        self._host_subscriptions: list[int] = []
        if connection is not None:
            self._on_bus_acquired(connection, WATCHER_NAME)
            self._owner_id = Gio.bus_own_name_on_connection(
                connection, WATCHER_NAME, Gio.BusNameOwnerFlags.NONE,
                self._on_name_acquired, self._on_name_lost,
            )
        else:
            self._owner_id = Gio.bus_own_name(
                Gio.BusType.SESSION, WATCHER_NAME, Gio.BusNameOwnerFlags.NONE,
                self._on_bus_acquired, self._on_name_acquired, self._on_name_lost,
            )

    # Items

    def get_items(self) -> list[str]:
        return list(self._items)

    def get_item_for_identifier(self, identifier: str) -> Item | None:
        return self._items.get(identifier)

    def _add_item(self, bus_name: str, object_path: str) -> str:
        identifier = bus_name + object_path
        if identifier in self._items or identifier in self._pending:
            return identifier  # already known (apps re-register after a watcher change)
        item = Item(self._conn, bus_name, object_path)
        if item.is_removed():  # vanished during construction
            return identifier
        self._pending[identifier] = item
        item.connect("ready", self._on_item_ready)
        item.connect("removed", self._on_item_removed)
        return identifier

    def _on_item_ready(self, item: Item):
        if self._pending.get(item.identifier) is not item:
            return
        del self._pending[item.identifier]
        self._items[item.identifier] = item
        self.emit("item-added", item.identifier)
        self._emit_dbus("StatusNotifierItemRegistered", GLib.Variant("(s)", (item.identifier,)))

    def _on_item_removed(self, item: Item):
        identifier = item.identifier
        if self._pending.get(identifier) is item:
            del self._pending[identifier]
        elif self._items.get(identifier) is item:
            del self._items[identifier]
            self.emit("item-removed", identifier)
            self._emit_dbus("StatusNotifierItemUnregistered", GLib.Variant("(s)", (identifier,)))

    def _remove_identifier(self, identifier: str):
        item = self._items.get(identifier) or self._pending.get(identifier)
        if item is not None:
            item.mark_removed()

    # Serving org.kde.StatusNotifierWatcher

    def _emit_dbus(self, signal: str, params: GLib.Variant | None = None):
        if not self.is_owner or self._conn is None:
            return
        try:
            self._conn.emit_signal(None, WATCHER_PATH, WATCHER_IFACE, signal, params)
        except GLib.Error as e:
            logger.debug(f"[Tray] Can't emit {signal}: {e.message}")

    def _on_bus_acquired(self, conn, _name):
        self._conn = conn
        interface = Gio.DBusNodeInfo.new_for_xml(WATCHER_XML).interfaces[0]
        try:
            self._registration = conn.register_object(
                WATCHER_PATH, interface, self._on_method_call, self._on_get_property, None,
            )
        except GLib.Error as e:
            logger.error(f"[Tray] Can't export {WATCHER_PATH}: {e.message}")

    def _on_name_acquired(self, conn, _name):
        logger.info("[Tray] Serving org.kde.StatusNotifierWatcher")
        self._conn = conn
        self._stop_host_mode()
        self.is_owner = True
        self._emit_dbus("StatusNotifierHostRegistered")

    def _on_name_lost(self, conn, _name):
        self.is_owner = False
        if conn is None or conn.is_closed():
            logger.warning("[Tray] No session bus connection; the system tray stays empty")
            return
        self._conn = conn
        logger.info("[Tray] Another StatusNotifierWatcher runs; acting as its host")
        self._start_host_mode()

    def _on_method_call(self, _conn, sender, _path, _iface, method, params, invocation):
        if method == "RegisterStatusNotifierItem":
            service = params.unpack()[0]
            bus_name, object_path = parse_registration(service, sender)
            if not Gio.dbus_is_name(bus_name) or not GLib.Variant.is_object_path(object_path):
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.InvalidArgs", f"Invalid service: {service}")
                return
            self._add_item(bus_name, object_path)
            invocation.return_value(None)
        elif method == "RegisterStatusNotifierHost":
            self._hosts.add(params.unpack()[0])
            invocation.return_value(None)
            self._emit_dbus("StatusNotifierHostRegistered")
        else:
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.UnknownMethod", f"No method {method}")

    def _on_get_property(self, _conn, _sender, _path, _iface, prop):
        if prop == "RegisteredStatusNotifierItems":
            return GLib.Variant("as", list(self._items))
        if prop == "IsStatusNotifierHostRegistered":
            return GLib.Variant("b", True)  # this process is a host
        if prop == "ProtocolVersion":
            return GLib.Variant("i", 0)
        return None

    # Host of another watcher

    def _start_host_mode(self):
        if self._host_subscriptions:
            return
        conn = self._conn
        for signal, handler in (("StatusNotifierItemRegistered", self._on_remote_registered),
                                ("StatusNotifierItemUnregistered", self._on_remote_unregistered)):
            self._host_subscriptions.append(conn.signal_subscribe(
                None, WATCHER_IFACE, signal, WATCHER_PATH, None,
                Gio.DBusSignalFlags.NONE, handler,
            ))
        self._host_name = f"org.kde.StatusNotifierHost-{os.getpid()}-{next(_host_counter)}"
        self._host_name_id = Gio.bus_own_name_on_connection(
            conn, self._host_name, Gio.BusNameOwnerFlags.NONE, None, None)
        conn.call(
            WATCHER_NAME, WATCHER_PATH, WATCHER_IFACE, "RegisterStatusNotifierHost",
            GLib.Variant("(s)", (self._host_name,)), None, Gio.DBusCallFlags.NONE,
            CALL_TIMEOUT_MS, None, self._on_host_registered,
        )

    def _on_host_registered(self, conn, result):
        try:
            conn.call_finish(result)
        except GLib.Error as e:
            logger.warning(f"[Tray] RegisterStatusNotifierHost failed: {e.message}")
        conn.call(
            WATCHER_NAME, WATCHER_PATH, "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", (WATCHER_IFACE, "RegisteredStatusNotifierItems")),
            GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None,
            self._on_remote_items,
        )

    def _on_remote_items(self, conn, result):
        try:
            identifiers = conn.call_finish(result).unpack()[0]
        except GLib.Error as e:
            logger.warning(f"[Tray] Can't list the watcher's items: {e.message}")
            return
        if self.is_owner:
            return
        for identifier in identifiers:
            self._add_item(*parse_identifier(identifier))

    def _on_remote_registered(self, _conn, _sender, _path, _iface, _signal, params):
        if not self.is_owner:
            self._add_item(*parse_identifier(params.unpack()[0]))

    def _on_remote_unregistered(self, _conn, _sender, _path, _iface, _signal, params):
        if not self.is_owner:
            self._remove_identifier("".join(parse_identifier(params.unpack()[0])))

    def _stop_host_mode(self):
        for subscription in self._host_subscriptions:
            self._conn.signal_unsubscribe(subscription)
        self._host_subscriptions.clear()
        if self._host_name_id:
            Gio.bus_unown_name(self._host_name_id)
            self._host_name_id = 0
