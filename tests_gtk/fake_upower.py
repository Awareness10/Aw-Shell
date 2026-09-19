"""Minimal fake UPower daemon for the sandbox's private bus.

Runs as its own process (a D-Bus service can't answer blocking calls made
from its own thread). Exposes a laptop battery at 80%, discharging.
Usage: python fake_upower.py  (prints "ready" once the name is owned)
"""

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

NAME = "org.freedesktop.UPower"
PATH = "/org/freedesktop/UPower"
DEVICE_IFACE = NAME + ".Device"
DISPLAY_DEVICE = PATH + "/devices/DisplayDevice"
BATTERY = PATH + "/devices/battery_BAT0"

BATTERY_PROPS = {
    "Type": dbus.UInt32(2),  # battery
    "PowerSupply": True,
    "IsPresent": True,
    "IsRechargeable": True,
    "Online": False,
    "Percentage": dbus.Double(80.0),
    "State": dbus.UInt32(2),  # discharging
    "TimeToEmpty": dbus.Int64(5400),
    "TimeToFull": dbus.Int64(0),
    "Energy": dbus.Double(40.0),
    "EnergyFull": dbus.Double(50.0),
    "EnergyRate": dbus.Double(8.0),
    "IconName": "battery-good-symbolic",
    "Model": "Test Battery",
    "Vendor": "Aw-Shell",
    "NativePath": "BAT0",
    "WarningLevel": dbus.UInt32(1),
}


class Device(dbus.service.Object):
    def __init__(self, bus, path, props):
        super().__init__(bus, path)
        self.props = props

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return self.props[prop]

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self.props


class UPower(dbus.service.Object):
    @dbus.service.method(NAME, out_signature="ao")
    def EnumerateDevices(self):
        return [dbus.ObjectPath(BATTERY)]

    @dbus.service.method(NAME, out_signature="o")
    def GetDisplayDevice(self):
        return dbus.ObjectPath(DISPLAY_DEVICE)

    @dbus.service.method(NAME, out_signature="s")
    def GetCriticalAction(self):
        return "PowerOff"

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return {"OnBattery": True, "LidIsPresent": True, "LidIsClosed": False}[prop]


def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    UPower(bus, PATH)
    Device(bus, DISPLAY_DEVICE, BATTERY_PROPS)
    Device(bus, BATTERY, BATTERY_PROPS)
    _name = dbus.service.BusName(NAME, bus)  # noqa: F841 - owns the name while alive
    print("ready", flush=True)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
