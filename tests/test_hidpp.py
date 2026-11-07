"""modules/hidpp.py: reads a Logitech device's battery and kind over HID++ 2.0,
skipping unrelated input reports and falling back to None on errors."""

import os
import socket
import threading
import time

import pytest

import modules.hidpp as hidpp

BATTERY_INDEX = 6
LEVEL_INDEX = 4
NAME_INDEX = 3
FEATURES = {hidpp.FEATURE_UNIFIED_BATTERY: BATTERY_INDEX, hidpp.FEATURE_DEVICE_NAME: NAME_INDEX}


class FakeDevice:
    """A hidraw node backed by a socketpair; answers HID++ requests the way a
    mouse does, after first sending a regular mouse-movement report."""

    def __init__(self, battery=(16, 0x04, 1, 1), level=(50, 30, 0), kind=3, features=FEATURES):
        self.host, self.device = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.battery, self.level, self.kind, self.features = bytes(battery), bytes(level), kind, features
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while request := self.device.recv(64):
            index, fn_sw = request[2], request[3]
            function = fn_sw >> 4
            self.device.send(bytes([0x02, 0x00, 0x05, 0x00]))  # pointer motion
            if index == 0:
                feature = int.from_bytes(request[4:6], "big")
                payload = bytes([self.features.get(feature, 0)])
            elif index == BATTERY_INDEX and function == hidpp.FN_GET_BATTERY_STATUS:
                payload = self.battery
            elif index == LEVEL_INDEX and function == hidpp.FN_GET_LEVEL_STATUS:
                payload = self.level
            elif index == NAME_INDEX and function == hidpp.FN_GET_DEVICE_TYPE:
                payload = bytes([self.kind])
            else:
                self.device.send(bytes([0x11, 0xFF, 0xFF, index, fn_sw, 0x02]).ljust(20, b"\0"))
                continue
            self.device.send((bytes([0x11, 0xFF, index, fn_sw]) + payload).ljust(20, b"\0"))

    def close(self):
        self.host.close()
        self.device.close()


@pytest.fixture
def device(monkeypatch):
    devices = []

    def make(**kwargs):
        fake = FakeDevice(**kwargs)
        devices.append(fake)
        monkeypatch.setattr(hidpp, "_open", lambda path: os.dup(fake.host.fileno()))
        return fake

    yield make
    for fake in devices:
        fake.close()


def test_reads_percentage_while_charging(device):
    device(battery=(16, 0x04, 1, 1))
    assert hidpp.read_battery("/dev/hidraw4") == hidpp.Battery(16, True)


def test_reads_percentage_while_discharging(device):
    device(battery=(73, 0x04, 0, 0))
    assert hidpp.read_battery("/dev/hidraw4") == hidpp.Battery(73, False)


def test_charge_complete_is_not_charging(device):
    device(battery=(100, 0x08, 3, 1))
    assert hidpp.read_battery("/dev/hidraw4") == hidpp.Battery(100, False)


def test_level_only_devices_fall_back(device):
    device(battery=(0, 0x04, 0, 0))
    assert hidpp.read_battery("/dev/hidraw4") is None


def test_missing_battery_feature_falls_back(device):
    device(features={hidpp.FEATURE_DEVICE_NAME: NAME_INDEX})
    assert hidpp.read_battery("/dev/hidraw4") is None


@pytest.mark.parametrize("status, charging", [(0, False), (1, True), (2, True), (3, False), (4, True)])
def test_older_mice_use_battery_status(device, status, charging):
    device(level=(60, 50, status), features={hidpp.FEATURE_BATTERY_STATUS: LEVEL_INDEX})
    assert hidpp.read_battery("/dev/hidraw4") == hidpp.Battery(60, charging)


def test_unknown_kind_is_none(device):
    device(features={hidpp.FEATURE_UNIFIED_BATTERY: BATTERY_INDEX})
    assert hidpp.is_pointer("/dev/hidraw4") is None


@pytest.mark.parametrize("kind, expected", [(3, True), (5, True), (0, False)])
def test_is_pointer(device, kind, expected):
    device(kind=kind)
    assert hidpp.is_pointer("/dev/hidraw4") is expected


def test_unopenable_node_is_none(monkeypatch):
    monkeypatch.setattr(hidpp, "_open", lambda path: None)
    assert hidpp.read_battery("/dev/hidraw4") is None
    assert hidpp.is_pointer("/dev/hidraw4") is None


def test_silent_device_times_out(monkeypatch):
    host, other = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    monkeypatch.setattr(hidpp, "TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(hidpp, "_open", lambda path: os.dup(host.fileno()))
    try:
        start = time.monotonic()
        assert hidpp.read_battery("/dev/hidraw4") is None
        assert hidpp.is_pointer("/dev/hidraw4") is None
        # Gives up after the first unanswered request instead of trying every feature
        assert time.monotonic() - start < 0.3
    finally:
        host.close()
        other.close()


def test_hidraw_for_power_supply(monkeypatch):
    monkeypatch.setattr(os, "listdir", lambda path: ["hidraw4"])
    assert hidpp.hidraw_for_power_supply("hidpp_battery_1") == "/dev/hidraw4"


def test_hidraw_for_missing_power_supply(monkeypatch):
    def missing(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(os, "listdir", missing)
    assert hidpp.hidraw_for_power_supply("hidpp_battery_9") is None
