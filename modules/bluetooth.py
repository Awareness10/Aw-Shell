from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow

import modules.icons as icons
from services.bluetooth import BluetoothClient, BluetoothDevice


class BluetoothDeviceSlot(CenterBox):
    def __init__(self, device: BluetoothDevice, **kwargs):
        super().__init__(name="bluetooth-device", **kwargs)
        self.device = device
        self._handlers = [
            self.device.connect("changed", self.on_changed),
            self.device.connect("removed", lambda *_: self.destroy()),
        ]
        self.connect("destroy", lambda *_: [self.device.disconnect(h) for h in self._handlers])

        self.icon = Image(icon_name=device.icon_name + "-symbolic", size=16)
        self.name_label = Label(label=device.name, h_expand=True, h_align="start", ellipsization="end")
        self.battery_label = Label(name="bluetooth-battery", visible=False)
        self.battery_label.set_no_show_all(True)
        self.connection_label = Label(name="bluetooth-connection", markup=icons.bluetooth_disconnected)
        self.connect_button = Button(
            name="bluetooth-connect",
            label="Connect",
            on_clicked=lambda *_: self.device.toggle_connection(),
        )

        self.start_children = [
            Box(
                spacing=8,
                h_expand=True,
                h_align="fill",
                children=[self.icon, self.name_label, self.battery_label, self.connection_label],
            )
        ]
        self.end_children = self.connect_button

        self.on_changed()

    def on_changed(self, *_):
        device = self.device
        self.name_label.set_label(device.name)
        self.icon.set_from_icon_name(device.icon_name + "-symbolic", 16)

        battery = device.battery_percentage
        self.battery_label.set_visible(battery >= 0)
        if battery >= 0:
            self.battery_label.set_label(f"{battery}%")

        self.connection_label.set_markup(
            icons.bluetooth_connected if device.connected else icons.bluetooth_disconnected
        )

        if device.connecting:
            if device.connected:
                label = "Disconnecting..."
            elif device.paired:
                label = "Connecting..."
            else:
                label = "Pairing..."
        elif device.failed:
            label = "Failed"
        elif device.connected:
            label = "Disconnect"
        elif device.paired:
            label = "Connect"
        else:
            label = "Pair"
        self.connect_button.set_label(label)
        self.connect_button.set_sensitive(not device.connecting)

        if device.connected:
            self.connect_button.add_style_class("connected")
        else:
            self.connect_button.remove_style_class("connected")


class BluetoothConnections(Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="bluetooth",
            spacing=4,
            orientation="vertical",
            **kwargs,
        )

        self.widgets = kwargs["widgets"]

        self.buttons = self.widgets.buttons.bluetooth_button
        self.bt_status_text = self.buttons.bluetooth_status_text
        self.bt_status_button = self.buttons.bluetooth_status_button
        self.bt_icon = self.buttons.bluetooth_icon
        self.bt_label = self.buttons.bluetooth_label
        self.bt_menu_button = self.buttons.bluetooth_menu_button
        self.bt_menu_label = self.buttons.bluetooth_menu_label

        self.slots: dict[str, BluetoothDeviceSlot] = {}

        self.scan_label = Label(name="bluetooth-scan-label", markup=icons.radar)
        self.scan_button = Button(
            name="bluetooth-scan",
            child=self.scan_label,
            tooltip_text="Scan for Bluetooth devices",
            on_clicked=lambda *_: self.client.toggle_scan()
        )
        self.back_button = Button(
            name="bluetooth-back",
            child=Label(name="bluetooth-back-label", markup=icons.chevron_left),
            on_clicked=lambda *_: self.widgets.show_notif()
        )

        self.paired_box = Box(spacing=2, orientation="vertical")
        self.available_box = Box(spacing=2, orientation="vertical")

        content_box = Box(spacing=4, orientation="vertical")
        content_box.add(self.paired_box)
        content_box.add(Label(name="bluetooth-section", label="Available"))
        content_box.add(self.available_box)

        self.children = [
            CenterBox(
                name="bluetooth-header",
                start_children=self.back_button,
                center_children=Label(name="bluetooth-text", label="Bluetooth Devices"),
                end_children=self.scan_button
            ),
            ScrolledWindow(
                name="bluetooth-devices",
                min_content_size=(-1, -1),
                child=content_box,
                v_expand=True,
                propagate_width=False,
                propagate_height=False,
            ),
        ]

        self.client = BluetoothClient()
        self.client.connect("device-added", self.on_device_added)
        self.client.connect("device-removed", self.on_device_removed)
        self.client.connect("notify::enabled", lambda *_: self.status_label())
        self.client.connect("notify::available", lambda *_: self.status_label())
        self.client.connect("notify::scanning", lambda *_: self.update_scan_label())

        self.status_label()
        self.update_scan_label()

    def status_label(self):
        widgets = [self.bt_status_button, self.bt_status_text, self.bt_icon,
                   self.bt_label, self.bt_menu_button, self.bt_menu_label]
        if self.client.enabled:
            self.bt_status_text.set_label("Enabled")
            for i in widgets:
                i.remove_style_class("disabled")
            self.bt_icon.set_markup(icons.bluetooth)
        else:
            self.bt_status_text.set_label("Disabled" if self.client.available else "Unavailable")
            for i in widgets:
                i.add_style_class("disabled")
            self.bt_icon.set_markup(icons.bluetooth_off)

    def on_device_added(self, client: BluetoothClient, path: str):
        if not (device := client.get_device(path)):
            return
        slot = BluetoothDeviceSlot(device)
        slot.set_no_show_all(True)
        self.slots[path] = slot
        device.connect("changed", lambda *_: self.place_slot(path))
        self.place_slot(path)

    def on_device_removed(self, _client, path: str):
        self.slots.pop(path, None)

    def place_slot(self, path: str):
        """Put a slot in the paired or available list, moving it if pairing state changed."""
        if not (slot := self.slots.get(path)):
            return
        device = slot.device
        target = self.paired_box if device.paired else self.available_box
        parent = slot.get_parent()
        if parent is not target:
            if parent is not None:
                parent.remove(slot)
            target.add(slot)
        # Hide anonymous devices (mostly BLE beacons) from the available list.
        slot.set_visible(device.paired or device.connected or device.has_name)

    def update_scan_label(self):
        if self.client.scanning:
            self.scan_label.add_style_class("scanning")
            self.scan_button.add_style_class("scanning")
            self.scan_button.set_tooltip_text("Stop scanning for Bluetooth devices")
        else:
            self.scan_label.remove_style_class("scanning")
            self.scan_button.remove_style_class("scanning")
            self.scan_button.set_tooltip_text("Scan for Bluetooth devices")
