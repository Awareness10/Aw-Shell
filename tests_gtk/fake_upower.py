"""Minimal fake UPower daemon for the sandbox's private bus.

Runs as its own process (a D-Bus service can't answer blocking calls made
from its own thread). Exposes a laptop battery at 80%, discharging.
Usage: python fake_upower.py  (prints "ready" once the name is owned)
"""

from gi.repository import Gio, GLib

NAME = "org.freedesktop.UPower"
PATH = "/org/freedesktop/UPower"
DEVICE_IFACE = NAME + ".Device"
DISPLAY_DEVICE = PATH + "/devices/DisplayDevice"
BATTERY = PATH + "/devices/battery_BAT0"

BATTERY_PROPS = {
    "Type": GLib.Variant("u", 2),  # battery
    "PowerSupply": GLib.Variant("b", True),
    "IsPresent": GLib.Variant("b", True),
    "IsRechargeable": GLib.Variant("b", True),
    "Online": GLib.Variant("b", False),
    "Percentage": GLib.Variant("d", 80.0),
    "State": GLib.Variant("u", 2),  # discharging
    "TimeToEmpty": GLib.Variant("x", 5400),
    "TimeToFull": GLib.Variant("x", 0),
    "Energy": GLib.Variant("d", 40.0),
    "EnergyFull": GLib.Variant("d", 50.0),
    "EnergyRate": GLib.Variant("d", 8.0),
    "IconName": GLib.Variant("s", "battery-good-symbolic"),
    "Model": GLib.Variant("s", "Test Battery"),
    "Vendor": GLib.Variant("s", "Aw-Shell"),
    "NativePath": GLib.Variant("s", "BAT0"),
    "WarningLevel": GLib.Variant("u", 1),
}

UPOWER_PROPS = {
    "OnBattery": GLib.Variant("b", True),
    "LidIsPresent": GLib.Variant("b", True),
    "LidIsClosed": GLib.Variant("b", False),
}

INTROSPECTION = Gio.DBusNodeInfo.new_for_xml(f"""
<node>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get">
      <arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{{sv}}" direction="out"/>
    </method>
  </interface>
  <interface name="{NAME}">
    <method name="EnumerateDevices"><arg type="ao" direction="out"/></method>
    <method name="GetDisplayDevice"><arg type="o" direction="out"/></method>
    <method name="GetCriticalAction"><arg type="s" direction="out"/></method>
  </interface>
</node>
""")
PROPERTIES_IFACE, UPOWER_IFACE = INTROSPECTION.interfaces


def _properties(props):
    def handle(connection, sender, path, interface, method, params, invocation):
        if method == "Get":
            _iface, prop = params.unpack()
            if prop not in props:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.InvalidArgs", f"No such property {prop}")
                return
            invocation.return_value(GLib.Variant("(v)", (props[prop],)))
        else:
            invocation.return_value(GLib.Variant("(a{sv})", (props,)))
    return handle


def _upower(connection, sender, path, interface, method, params, invocation):
    replies = {
        "EnumerateDevices": GLib.Variant("(ao)", ([BATTERY],)),
        "GetDisplayDevice": GLib.Variant("(o)", (DISPLAY_DEVICE,)),
        "GetCriticalAction": GLib.Variant("(s)", ("PowerOff",)),
    }
    invocation.return_value(replies[method])


def main():
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    bus.register_object(PATH, UPOWER_IFACE, _upower, None, None)
    bus.register_object(PATH, PROPERTIES_IFACE, _properties(UPOWER_PROPS), None, None)
    for path in (DISPLAY_DEVICE, BATTERY):
        bus.register_object(path, PROPERTIES_IFACE, _properties(BATTERY_PROPS), None, None)
    loop = GLib.MainLoop()
    Gio.bus_own_name_on_connection(
        bus, NAME, Gio.BusNameOwnerFlags.NONE,
        lambda *_: print("ready", flush=True),  # owns the name while alive
        lambda *_: loop.quit(),
    )
    loop.run()


if __name__ == "__main__":
    main()
