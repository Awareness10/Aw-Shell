"""Bluetooth service backed by BlueZ.

State is read reactively from BlueZ over D-Bus (org.freedesktop.DBus.ObjectManager),
while actions (power, scan, pair, trust, connect, disconnect) are delegated to
`bluetoothctl`, which handles agent registration, pairing and error reporting
far more reliably than GnomeBluetooth.
"""

import re
from collections.abc import Callable

from fabric.core.service import Property, Service, Signal
from gi.repository import Gio, GLib
from loguru import logger

BLUEZ = "org.bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
DEVICE_IFACE = "org.bluez.Device1"
BATTERY_IFACE = "org.bluez.Battery1"

MAC_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$", re.IGNORECASE)

SCAN_SECONDS = 30
ACTION_TIMEOUT_SECONDS = 30


def _prop(proxy: Gio.DBusProxy | None, name: str, default=None):
    if proxy is None:
        return default
    value = proxy.get_cached_property(name)
    return default if value is None else value.unpack()


def _run(argv: list[str], callback: Callable[[bool, str], None] | None = None,
         timeout: int = ACTION_TIMEOUT_SECONDS) -> Gio.Subprocess | None:
    """Run a command asynchronously; callback(success, output) on the main loop."""
    try:
        proc = Gio.Subprocess.new(
            argv,
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
            | Gio.SubprocessFlags.STDIN_PIPE,
        )
    except GLib.Error as e:
        logger.error(f"[Bluetooth] Failed to spawn {argv}: {e.message}")
        if callback:
            callback(False, e.message)
        return None

    timeout_id = GLib.timeout_add_seconds(timeout, lambda: (proc.force_exit(), False)[1])

    def on_done(p: Gio.Subprocess, res: Gio.AsyncResult):
        GLib.source_remove(timeout_id)
        try:
            _, out, _ = p.communicate_utf8_finish(res)
        except GLib.Error as e:
            out = e.message
        ok = p.get_if_exited() and p.get_exit_status() == 0
        if not ok:
            logger.warning(f"[Bluetooth] `{' '.join(argv)}` failed: {(out or '').strip()[-300:]}")
        if callback:
            callback(ok, out or "")

    # Closing stdin immediately keeps bluetoothctl in non-interactive mode.
    proc.communicate_utf8_async("", None, on_done)
    return proc


def _run_chain(commands: list[list[str]], callback: Callable[[bool], None] | None = None):
    """Run commands sequentially, stopping at the first failure."""
    def step(i: int):
        if i >= len(commands):
            if callback:
                callback(True)
            return

        def done(ok: bool, _out: str):
            if ok:
                step(i + 1)
            elif callback:
                callback(False)

        _run(commands[i], done)

    step(0)


class BluetoothDevice(Service):
    @Signal
    def changed(self) -> None: ...

    @Signal
    def removed(self) -> None: ...

    def __init__(self, obj_path: str, proxy: Gio.DBusProxy, client: "BluetoothClient", **kwargs):
        super().__init__(**kwargs)
        self.obj_path = obj_path
        self._proxy = proxy
        self._battery: Gio.DBusProxy | None = None
        self._client = client
        self._busy = False
        self._error = False
        self._error_timer = 0

    # -- properties --------------------------------------------------------

    @Property(str, "readable")
    def address(self) -> str:
        return _prop(self._proxy, "Address", "")

    @Property(str, "readable")
    def name(self) -> str:
        return _prop(self._proxy, "Alias") or _prop(self._proxy, "Name") or self.address

    @property
    def has_name(self) -> bool:
        return bool(_prop(self._proxy, "Name"))

    @Property(str, "readable")
    def icon_name(self) -> str:
        return _prop(self._proxy, "Icon") or "bluetooth"

    @Property(bool, "readable", default_value=False)
    def connected(self) -> bool:
        return bool(_prop(self._proxy, "Connected", False))

    @Property(bool, "readable", default_value=False)
    def paired(self) -> bool:
        return bool(_prop(self._proxy, "Paired", False)) or bool(_prop(self._proxy, "Bonded", False))

    @Property(bool, "readable", default_value=False)
    def trusted(self) -> bool:
        return bool(_prop(self._proxy, "Trusted", False))

    @Property(bool, "readable", default_value=False)
    def connecting(self) -> bool:
        return self._busy

    @Property(bool, "readable", default_value=False)
    def failed(self) -> bool:
        return self._error

    @Property(int, "readable")
    def battery_percentage(self) -> int:
        return int(_prop(self._battery, "Percentage", -1))

    # -- actions -----------------------------------------------------------

    def toggle_connection(self):
        if self._busy:
            return
        if self.connected:
            self.disconnect_device()
        else:
            self.connect_device()

    def connect_device(self):
        addr = self.address
        if not MAC_RE.match(addr):
            return
        if self.paired:
            commands = [["bluetoothctl", "connect", addr]]
            if not self.trusted:
                commands.insert(0, ["bluetoothctl", "trust", addr])
        else:
            # New device: must be pairable, paired and trusted before it
            # will connect (and auto-reconnect later).
            commands = [
                ["bluetoothctl", "pairable", "on"],
                ["bluetoothctl", "pair", addr],
                ["bluetoothctl", "trust", addr],
                ["bluetoothctl", "connect", addr],
            ]
        self._start(commands)

    def disconnect_device(self):
        addr = self.address
        if MAC_RE.match(addr):
            self._start([["bluetoothctl", "disconnect", addr]])

    def forget(self):
        addr = self.address
        if MAC_RE.match(addr):
            self._start([["bluetoothctl", "remove", addr]])

    def _start(self, commands: list[list[str]]):
        self._busy = True
        self._set_error(False)
        self.emit("changed")

        def done(ok: bool):
            self._busy = False
            if not ok:
                self._set_error(True)
            logger.info(f"[Bluetooth] {commands[-1][1]} {self.address}: {'ok' if ok else 'failed'}")
            self.emit("changed")

        _run_chain(commands, done)

    def _set_error(self, value: bool):
        if self._error_timer:
            GLib.source_remove(self._error_timer)
            self._error_timer = 0
        self._error = value
        if value:
            def clear():
                self._error_timer = 0
                self._error = False
                self.emit("changed")
                return False
            self._error_timer = GLib.timeout_add_seconds(3, clear)

    # -- called by client ---------------------------------------------------

    def _set_battery(self, proxy: Gio.DBusProxy | None):
        self._battery = proxy
        self.emit("changed")

    def _close(self):
        if self._error_timer:
            GLib.source_remove(self._error_timer)
            self._error_timer = 0
        self.emit("removed")


class BluetoothClient(Service):
    @Signal
    def changed(self) -> None: ...

    @Signal
    def device_added(self, address: str) -> None: ...

    @Signal
    def device_removed(self, address: str) -> None: ...

    def __init__(self, on_device_added: Callable | None = None, **kwargs):
        super().__init__(**kwargs)
        self._adapter: Gio.DBusProxy | None = None
        self._devices: dict[str, BluetoothDevice] = {}  # keyed by object path
        self._scan_proc: Gio.Subprocess | None = None
        self._manager: Gio.DBusObjectManagerClient | None = None

        if on_device_added:
            self.connect("device-added", on_device_added)

        Gio.DBusObjectManagerClient.new_for_bus(
            Gio.BusType.SYSTEM,
            Gio.DBusObjectManagerClientFlags.NONE,
            BLUEZ,
            "/",
            None,  # get_proxy_type_func
            None,  # get_proxy_type_user_data
            None,  # cancellable
            self._on_manager_ready,
        )

    # -- properties --------------------------------------------------------

    @Property(bool, "readable", default_value=False)
    def enabled(self) -> bool:
        return bool(_prop(self._adapter, "Powered", False))

    @Property(bool, "readable", default_value=False)
    def scanning(self) -> bool:
        return bool(_prop(self._adapter, "Discovering", False))

    @Property(bool, "readable", default_value=False)
    def available(self) -> bool:
        return self._adapter is not None

    @property
    def devices(self) -> list[BluetoothDevice]:
        return list(self._devices.values())

    @property
    def connected_devices(self) -> list[BluetoothDevice]:
        return [d for d in self._devices.values() if d.connected]

    def get_device(self, key: str) -> BluetoothDevice | None:
        """Look up a device by object path or MAC address."""
        if dev := self._devices.get(key):
            return dev
        return next((d for d in self._devices.values() if d.address == key), None)

    # -- actions -----------------------------------------------------------

    def toggle_power(self):
        self.set_power(not self.enabled)

    def set_power(self, on: bool):
        if on:
            _run_chain([
                ["rfkill", "unblock", "bluetooth"],
                ["bluetoothctl", "power", "on"],
            ])
        else:
            self.stop_scan()
            _run(["bluetoothctl", "power", "off"])

    def toggle_scan(self):
        if self._scan_proc is not None or self.scanning:
            self.stop_scan()
        else:
            self.start_scan()

    def start_scan(self):
        if not self.enabled or self._scan_proc is not None:
            return
        # BlueZ ties discovery to the D-Bus client that started it, so keep a
        # bluetoothctl process alive for the duration of the scan.
        def done(_ok: bool, _out: str):
            self._scan_proc = None
            self.notify("scanning")

        self._scan_proc = _run(
            ["bluetoothctl", "--timeout", str(SCAN_SECONDS), "scan", "on"],
            done,
            timeout=SCAN_SECONDS + 5,
        )
        self.notify("scanning")

    def stop_scan(self):
        if self._scan_proc is not None:
            self._scan_proc.send_signal(15)
        elif self.scanning:
            _run(["bluetoothctl", "scan", "off"])

    # -- D-Bus plumbing ----------------------------------------------------

    def _on_manager_ready(self, _source, res: Gio.AsyncResult):
        try:
            self._manager = Gio.DBusObjectManagerClient.new_for_bus_finish(res)
        except GLib.Error as e:
            logger.error(f"[Bluetooth] Could not connect to BlueZ: {e.message}")
            return

        self._manager.connect("interface-added", lambda _m, obj, iface: self._add_interface(obj, iface))
        self._manager.connect("interface-removed", lambda _m, obj, iface: self._remove_interface(obj, iface))
        self._manager.connect("object-added", lambda _m, obj: self._add_object(obj))
        self._manager.connect("object-removed", lambda _m, obj: self._remove_object(obj))
        self._manager.connect("interface-proxy-properties-changed", self._on_properties_changed)

        for obj in self._manager.get_objects():
            self._add_object(obj)
        self._notify_adapter()

    def _add_object(self, obj: Gio.DBusObject):
        for iface in obj.get_interfaces():
            self._add_interface(obj, iface)

    def _remove_object(self, obj: Gio.DBusObject):
        for iface in obj.get_interfaces():
            self._remove_interface(obj, iface)

    def _add_interface(self, obj: Gio.DBusObject, iface: Gio.DBusProxy):
        name = iface.get_interface_name()
        path = obj.get_object_path()
        if name == ADAPTER_IFACE:
            if self._adapter is None:
                self._adapter = iface
                self._notify_adapter()
        elif name == DEVICE_IFACE:
            if path in self._devices:
                return
            device = BluetoothDevice(path, iface, self)
            battery = obj.get_interface(BATTERY_IFACE)
            if battery is not None:
                device._set_battery(battery)
            self._devices[path] = device
            self.emit("device-added", path)
            self.emit("changed")
        elif name == BATTERY_IFACE:
            if device := self._devices.get(path):
                device._set_battery(iface)

    def _remove_interface(self, obj: Gio.DBusObject, iface: Gio.DBusProxy):
        name = iface.get_interface_name()
        path = obj.get_object_path()
        if name == ADAPTER_IFACE and self._adapter is not None \
                and self._adapter.get_object_path() == path:
            self._adapter = None
            self._scan_proc = None
            self._notify_adapter()
        elif name == DEVICE_IFACE:
            if device := self._devices.pop(path, None):
                device._close()
                self.emit("device-removed", path)
                self.emit("changed")
        elif name == BATTERY_IFACE:
            if device := self._devices.get(path):
                device._set_battery(None)

    def _on_properties_changed(self, _manager, _obj, iface: Gio.DBusProxy, changed: GLib.Variant, _invalidated):
        name = iface.get_interface_name()
        if name == ADAPTER_IFACE and iface is self._adapter:
            self._notify_adapter()
        elif name in (DEVICE_IFACE, BATTERY_IFACE):
            if device := self._devices.get(iface.get_object_path()):
                device.emit("changed")
            self.emit("changed")

    def _notify_adapter(self):
        for prop in ("available", "enabled", "scanning"):
            self.notify(prop)
        self.emit("changed")
