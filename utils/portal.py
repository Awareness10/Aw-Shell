"""File picker through xdg-desktop-portal.

The picker runs in the portal's own process, so it gets the user's GTK
theme rather than the shell's stylesheet, and the shell keeps running
while it's open.
"""

import secrets
from collections.abc import Callable

from gi.repository import Gio, GLib

PORTAL = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"


def pick_file(title: str, on_done: Callable[[str | None], None]) -> None:
    """Ask for one local file; on_done gets its path, or None if cancelled."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except GLib.Error as e:
        print(f"File picker: no session bus: {e.message}")
        on_done(None)
        return

    # Listen on the request path before asking, so a quick answer isn't missed
    token = f"aw_shell_{secrets.token_hex(8)}"
    sender = bus.get_unique_name().lstrip(":").replace(".", "_")
    request_path = f"{PORTAL_PATH}/request/{sender}/{token}"
    subscription = 0

    def on_response(_bus, _sender, _path, _iface, _signal, params):
        bus.signal_unsubscribe(subscription)
        code, results = params.unpack()
        uris = results.get("uris", []) if code == 0 else []
        on_done(Gio.File.new_for_uri(uris[0]).get_path() if uris else None)

    subscription = bus.signal_subscribe(
        PORTAL, "org.freedesktop.portal.Request", "Response", request_path,
        None, Gio.DBusSignalFlags.NONE, on_response,
    )

    def on_called(_bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error as e:
            bus.signal_unsubscribe(subscription)
            print(f"File picker: the portal failed: {e.message}")
            on_done(None)

    options = {"handle_token": GLib.Variant("s", token), "modal": GLib.Variant("b", True)}
    bus.call(
        PORTAL, PORTAL_PATH, "org.freedesktop.portal.FileChooser", "OpenFile",
        GLib.Variant("(ssa{sv})", ("", title, options)), GLib.VariantType("(o)"),
        Gio.DBusCallFlags.NONE, -1, None, on_called,
    )
