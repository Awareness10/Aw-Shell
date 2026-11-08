"""MouseBattery picks the mouse out of UPower's devices, prefers the HID++
reading for Logitech mice, and keeps looking for one that turns up later."""

import pytest

import modules.controls as controls
from modules.controls import MouseBattery
from modules.hidpp import Battery

LAPTOP = ("/bat0", {"Type": 2, "IsPresent": True, "Percentage": 80.0, "NativePath": "BAT0"})
BT_MOUSE = ("/bt", {"Type": 5, "IsPresent": True, "Percentage": 55.0, "State": 2,
                    "Model": "MX Anywhere", "NativePath": "/org/bluez/hci0/dev_X"})
# How UPower lists a Logitech mouse on its charging cable
WIRED_LOGITECH = ("/hidpp", {"Type": 6, "IsPresent": True, "Percentage": 1.0, "State": 1,
                             "Model": "PRO X Wireless", "NativePath": "hidpp_battery_1"})


@pytest.fixture
def hidpp(monkeypatch):
    fake = {"pointer": True, "battery": Battery(16, True), "kind_queries": 0}

    def is_pointer(path):
        fake["kind_queries"] += 1
        return fake["pointer"]

    monkeypatch.setattr(controls.hidpp, "hidraw_for_power_supply",
                        lambda name: "/dev/hidraw4" if name.startswith("hidpp") else None)
    monkeypatch.setattr(controls.hidpp, "is_pointer", is_pointer)
    monkeypatch.setattr(controls.hidpp, "read_battery", lambda path: fake["battery"])
    return fake


@pytest.fixture
def ring(sandbox):
    widget = MouseBattery()
    yield widget
    widget.destroy()


def test_hidden_without_a_mouse(ring):
    # The sandbox's UPower only has a laptop battery
    assert not ring.get_visible()
    assert ring._find_reading(ring._present_devices()) is None


def test_reads_any_upower_mouse(ring, hidpp):
    assert ring._find_reading([LAPTOP, BT_MOUSE]) == (55.0, False, "MX Anywhere")


def test_wired_logitech_uses_hidpp(ring, hidpp):
    assert ring._find_reading([LAPTOP, WIRED_LOGITECH]) == (16, True, "PRO X Wireless")


def test_logitech_keyboard_is_skipped_and_remembered(ring, hidpp):
    hidpp["pointer"] = False
    assert ring._find_reading([WIRED_LOGITECH]) is None
    assert ring._find_reading([WIRED_LOGITECH]) is None
    assert hidpp["kind_queries"] == 1


def test_unanswered_kind_query_is_retried(ring, hidpp):
    hidpp["pointer"] = None
    assert ring._find_reading([WIRED_LOGITECH]) is None
    hidpp["pointer"] = True
    assert ring._find_reading([WIRED_LOGITECH]) == (16, True, "PRO X Wireless")


def test_falls_back_to_upower_when_hidpp_is_silent(ring, hidpp):
    hidpp["battery"] = None
    assert ring._find_reading([WIRED_LOGITECH]) == (1.0, True, "PRO X Wireless")


def test_shows_a_mouse_that_appears_later(ring, hidpp):
    assert not ring.get_visible()
    ring._finish_update(ring._find_reading([LAPTOP, BT_MOUSE]))
    assert ring.get_visible()
    assert ring.get_tooltip_text() == "MX Anywhere: 55%"
    ring._finish_update(None)
    assert not ring.get_visible()


def test_divider_follows_battery_visibility(sandbox):
    from modules.controls import ControlSmall, DeviceBattery

    small = ControlSmall()
    try:
        divider = next(c for c in small.get_children() if c.get_name() == "control-small-divider")
        batteries = [c for c in small.get_children() if isinstance(c, DeviceBattery)]
        for battery in batteries:
            battery._show_reading(None)
        assert not divider.get_visible()
        batteries[0]._show_reading((55.0, False, "MX Anywhere"))
        assert divider.get_visible()
        batteries[0]._show_reading(None)
        assert not divider.get_visible()
    finally:
        small.destroy()


def test_battery_ring_is_closed_unlike_knobs(ring):
    assert ring.progress_bar.end_angle - ring.progress_bar.start_angle == 360
    assert controls.VolumeSmall.END_ANGLE - controls.VolumeSmall.START_ANGLE < 360
