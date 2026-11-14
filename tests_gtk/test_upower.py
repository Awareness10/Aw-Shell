"""UPowerManager returns plain Python values from the sandbox's fake UPower."""

import pytest
from gi.repository import GLib

from modules.upower.upower import UPowerManager

BATTERY = "/org/freedesktop/UPower/devices/battery_BAT0"


def test_reads_devices_and_properties(sandbox):
    upower = UPowerManager()
    assert upower.detect_devices() == [BATTERY]
    assert upower.get_display_device() == "/org/freedesktop/UPower/devices/DisplayDevice"
    assert upower.get_critical_action() == "PowerOff"
    assert upower.get_device_percentage(BATTERY) == 80.0
    assert upower.on_battery() is True
    assert upower.is_lid_present() is True and upower.is_lid_closed() is False
    assert upower.get_state(BATTERY) == "Discharging"
    assert upower.is_loading(BATTERY) is False

    info = upower.get_full_device_information(BATTERY)
    assert info["Percentage"] == 80.0 and info["TimeToEmpty"] == 5400
    assert info["Model"] == "Test Battery" and info["IsPresent"] is True
    assert info["Capacity"] == 0.0  # missing from the device: default


def test_errors_without_upower(no_upower):
    upower = UPowerManager()
    with pytest.raises(GLib.Error):
        upower.get_display_device()
