"""Minimal HID++ 2.0 client for Logitech battery readings.

The kernel's hidpp driver misreports some mice while they charge over the
cable (UPower sees 1% and calls the mouse a keyboard), so ask the device
directly over hidraw, the same way Solaar does.
"""

import os
import select
import time
from typing import NamedTuple, Optional

REPORT_SHORT = 0x10
REPORT_LONG = 0x11
LONG_LENGTH = 20
# hid-logitech-dj rewrites this to the paired slot for receiver devices
DEVICE_INDEX = 0xFF
SOFTWARE_ID = 0x0A
ERROR_FEATURE_INDEX = 0xFF

FEATURE_ROOT = 0x0000
FEATURE_DEVICE_NAME = 0x0005
FEATURE_BATTERY_STATUS = 0x1000  # older HID++ 2.0 devices
FEATURE_UNIFIED_BATTERY = 0x1004

FN_GET_DEVICE_TYPE = 2
FN_GET_LEVEL_STATUS = 0  # BATTERY_STATUS
FN_GET_BATTERY_STATUS = 1  # UNIFIED_BATTERY

POINTER_KINDS = {3, 5}  # mouse, trackball
# "charge complete" (3) counts as not charging, like UPower's fully-charged
UNIFIED_CHARGING = {1, 2}  # charging, slow charging
LEVEL_CHARGING = {1, 2, 4}  # recharging, almost full, slow recharge

# Idle mice behind a receiver can take most of a second to answer
TIMEOUT_SECONDS = 2.0


class NoReply(Exception):
    """The device didn't answer, e.g. asleep or behind a receiver that
    doesn't pass raw writes through."""


class Battery(NamedTuple):
    percentage: int
    charging: bool


def hidraw_for_power_supply(name: str) -> Optional[str]:
    """Map a power_supply name like hidpp_battery_1 to its /dev/hidrawN."""
    try:
        nodes = os.listdir(f"/sys/class/power_supply/{name}/device/hidraw")
    except OSError:
        return None
    return f"/dev/{nodes[0]}" if nodes else None


def _request(fd: int, feature_index: int, function: int, params: bytes = b"") -> Optional[bytes]:
    header = bytes([REPORT_LONG, DEVICE_INDEX, feature_index, (function << 4) | SOFTWARE_ID])
    os.write(fd, (header + params).ljust(LONG_LENGTH, b"\0"))

    deadline = time.monotonic() + TIMEOUT_SECONDS
    while (remaining := deadline - time.monotonic()) > 0:
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            break
        try:
            reply = os.read(fd, 64)
        except BlockingIOError:
            continue
        # The node also carries regular input reports; skip anything that isn't our reply
        if len(reply) < 5 or reply[0] not in (REPORT_SHORT, REPORT_LONG):
            continue
        if reply[2] == ERROR_FEATURE_INDEX and reply[3] == feature_index and reply[4] == header[3]:
            return None
        if reply[2] == feature_index and reply[3] == header[3]:
            return reply[4:]
    raise NoReply


def _feature_index(fd: int, feature: int) -> Optional[int]:
    """The feature's slot on this device, or None if it lacks the feature."""
    reply = _request(fd, FEATURE_ROOT, 0, feature.to_bytes(2, "big"))
    if not reply or reply[0] == 0:
        return None
    return reply[0]


def _call(fd: int, feature: int, function: int) -> Optional[bytes]:
    """The function's reply, or None if the device lacks the feature or
    rejects the call. Raises NoReply if it doesn't answer at all."""
    index = _feature_index(fd, feature)
    return None if index is None else _request(fd, index, function)


def _open(path: str) -> Optional[int]:
    try:
        return os.open(path, os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return None


def is_pointer(path: str) -> Optional[bool]:
    """Whether the device is a mouse or trackball; None if it can't tell."""
    fd = _open(path)
    if fd is None:
        return None
    try:
        reply = _call(fd, FEATURE_DEVICE_NAME, FN_GET_DEVICE_TYPE)
    except (OSError, NoReply):
        return None
    finally:
        os.close(fd)
    return None if not reply else reply[0] in POINTER_KINDS


def _unified_battery(fd: int) -> Optional[Battery]:
    reply = _call(fd, FEATURE_UNIFIED_BATTERY, FN_GET_BATTERY_STATUS)
    # A 0% state of charge means the device only reports coarse levels
    if not reply or reply[0] == 0:
        return None
    return Battery(min(reply[0], 100), reply[2] in UNIFIED_CHARGING)


def _level_battery(fd: int) -> Optional[Battery]:
    reply = _call(fd, FEATURE_BATTERY_STATUS, FN_GET_LEVEL_STATUS)
    if not reply or reply[0] == 0:
        return None
    return Battery(min(reply[0], 100), reply[2] in LEVEL_CHARGING)


def read_battery(path: str) -> Optional[Battery]:
    fd = _open(path)
    if fd is None:
        return None
    try:
        return _unified_battery(fd) or _level_battery(fd)
    except (OSError, NoReply):
        return None
    finally:
        os.close(fd)
