from gi.repository import Gio, GLib


class UPowerManager():

    def __init__(self):
        self.UPOWER_NAME = "org.freedesktop.UPower"
        self.UPOWER_PATH = "/org/freedesktop/UPower"

        self.DBUS_PROPERTIES = "org.freedesktop.DBus.Properties"
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def _call(self, path, interface, method, *args, signature=None):
        """Call a method on UPower and return its reply as plain Python
        values: the single value for one-value replies, else a tuple.
        Raises GLib.Error on D-Bus errors (UPower not running, ...)."""
        parameters = GLib.Variant(signature, args) if signature else None
        reply = self.bus.call_sync(
            self.UPOWER_NAME, path, interface, method, parameters,
            None, Gio.DBusCallFlags.NONE, -1, None,
        ).unpack()
        return reply[0] if len(reply) == 1 else reply

    def _get(self, path, interface, prop):
        return self._call(path, self.DBUS_PROPERTIES, "Get", interface, prop, signature="(ss)")

    def detect_devices(self):
        devices = self._call(self.UPOWER_PATH, self.UPOWER_NAME, 'EnumerateDevices')
        return devices

    def get_display_device(self):
        dispdev = self._call(self.UPOWER_PATH, self.UPOWER_NAME, 'GetDisplayDevice')
        return dispdev

    def get_critical_action(self):
        critical_action = self._call(self.UPOWER_PATH, self.UPOWER_NAME, 'GetCriticalAction')
        return critical_action

    def get_device_percentage(self, battery):
        return self._get(battery, self.UPOWER_NAME + ".Device", "Percentage")

    def get_full_device_information(self, battery):
        # Use GetAll to retrieve all properties in a single DBus call
        all_properties = self._call(battery, self.DBUS_PROPERTIES, "GetAll", self.UPOWER_NAME + ".Device", signature="(s)")
        
        # Extract properties with default values for missing keys
        information_table = {
            'HasHistory': all_properties.get('HasHistory', False),
            'HasStatistics': all_properties.get('HasStatistics', False), 
            'IsPresent': all_properties.get('IsPresent', False),
            'IsRechargeable': all_properties.get('IsRechargeable', False),
            'Online': all_properties.get('Online', False),
            'PowerSupply': all_properties.get('PowerSupply', False),
            'Capacity': all_properties.get('Capacity', 0.0),
            'Energy': all_properties.get('Energy', 0.0),
            'EnergyEmpty': all_properties.get('EnergyEmpty', 0.0),
            'EnergyFull': all_properties.get('EnergyFull', 0.0),
            'EnergyFullDesign': all_properties.get('EnergyFullDesign', 0.0),
            'EnergyRate': all_properties.get('EnergyRate', 0.0),
            'Luminosity': all_properties.get('Luminosity', 0.0),
            'Percentage': all_properties.get('Percentage', 0.0),
            'Temperature': all_properties.get('Temperature', 0.0),
            'Voltage': all_properties.get('Voltage', 0.0),
            'TimeToEmpty': all_properties.get('TimeToEmpty', 0),
            'TimeToFull': all_properties.get('TimeToFull', 0),
            'IconName': all_properties.get('IconName', ''),
            'Model': all_properties.get('Model', ''),
            'NativePath': all_properties.get('NativePath', ''),
            'Serial': all_properties.get('Serial', ''),
            'Vendor': all_properties.get('Vendor', ''),
            'State': all_properties.get('State', 0),
            'Technology': all_properties.get('Technology', 0),
            'Type': all_properties.get('Type', 0),
            'WarningLevel': all_properties.get('WarningLevel', 0),
            'UpdateTime': all_properties.get('UpdateTime', 0)
        }

        return information_table

    def is_lid_present(self):
        is_lid_present = bool(self._get(self.UPOWER_PATH, self.UPOWER_NAME, 'LidIsPresent'))
        return is_lid_present

    def is_lid_closed(self):
        is_lid_closed = bool(self._get(self.UPOWER_PATH, self.UPOWER_NAME, 'LidIsClosed'))
        return is_lid_closed

    def on_battery(self):
        on_battery = bool(self._get(self.UPOWER_PATH, self.UPOWER_NAME, 'OnBattery'))
        return on_battery

    def has_wakeup_capabilities(self):
        has_wakeup_capabilities = bool(self._get(self.UPOWER_PATH + "/Wakeups", self.UPOWER_NAME + '.Wakeups', 'HasCapability'))
        return has_wakeup_capabilities

    def get_wakeups_data(self):
        data = self._call(self.UPOWER_PATH + "/Wakeups", self.UPOWER_NAME + '.Wakeups', 'GetData')
        return data

    def get_wakeups_total(self):
        data = self._call(self.UPOWER_PATH + "/Wakeups", self.UPOWER_NAME + '.Wakeups', 'GetTotal')
        return data

    def is_loading(self, battery):
        state = int(self._get(battery, self.UPOWER_NAME + ".Device", "State"))

        if (state == 1):
            return True
        else:
            return False

    def get_state(self, battery):
        state = int(self._get(battery, self.UPOWER_NAME + ".Device", "State"))

        if (state == 0):
            return "Unknown"
        elif (state == 1):
            return "Loading"
        elif (state == 2):
            return "Discharging"
        elif (state == 3):
            return "Empty"
        elif (state == 4):
            return "Fully charged"
        elif (state == 5):
            return "Pending charge"
        elif (state == 6):
            return "Pending discharge"
