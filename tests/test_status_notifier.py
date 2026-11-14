"""The toolkit-free parts of services/status_notifier.py: registration strings,
pixmap choice and ARGB -> RGBA. D-Bus behaviour: tests_gtk/test_status_notifier.py."""

import sys
import types
from unittest.mock import MagicMock

import pytest

# tests/conftest.py mocks gi without GObject; the service subclasses GObject.Object
if not hasattr(sys.modules["gi.repository"], "GObject"):
    _gobject = types.ModuleType("gi.repository.GObject")
    _gobject.Object = object
    _gobject.SignalFlags = MagicMock()
    sys.modules["gi.repository"].GObject = _gobject
    sys.modules["gi.repository.GObject"] = _gobject

from services.status_notifier import (  # noqa: E402
    Pixmap,
    argb_to_rgba,
    parse_identifier,
    parse_registration,
    pick_pixmap,
)


@pytest.mark.parametrize("service, expected", [
    ("/StatusNotifierItem", (":1.5", "/StatusNotifierItem")),
    ("/org/ayatana/NotificationItem/nm", (":1.5", "/org/ayatana/NotificationItem/nm")),
    ("org.kde.StatusNotifierItem-12-1", ("org.kde.StatusNotifierItem-12-1", "/StatusNotifierItem")),
    (":1.9", (":1.9", "/StatusNotifierItem")),
    ("org.example.App/Tray", ("org.example.App", "/Tray")),
    ("", (":1.5", "/StatusNotifierItem")),
])
def test_parse_registration(service, expected):
    assert parse_registration(service, ":1.5") == expected


@pytest.mark.parametrize("identifier, expected", [
    (":1.30/StatusNotifierItem", (":1.30", "/StatusNotifierItem")),
    (":1.7/org/ayatana/NotificationItem/x", (":1.7", "/org/ayatana/NotificationItem/x")),
    ("org.kde.StatusNotifierItem-1-1", ("org.kde.StatusNotifierItem-1-1", "/StatusNotifierItem")),
])
def test_parse_identifier(identifier, expected):
    assert parse_identifier(identifier) == expected


def _pm(size: int) -> Pixmap:
    return Pixmap(size, size, bytes(size * size * 4))


def test_pick_pixmap_smallest_big_enough():
    assert pick_pixmap([_pm(64), _pm(16), _pm(24), _pm(32)], 20).width == 24
    assert pick_pixmap([_pm(20)], 20).width == 20


def test_pick_pixmap_falls_back_to_largest():
    assert pick_pixmap([_pm(8), _pm(16)], 20).width == 16


def test_pick_pixmap_skips_broken_and_empty():
    assert pick_pixmap([], 20) is None
    assert pick_pixmap(None, 20) is None
    assert pick_pixmap([Pixmap(32, 32, bytes(10)), Pixmap(0, 0, b"")], 20) is None
    assert pick_pixmap([Pixmap(32, 32, bytes(10)), _pm(16)], 20).width == 16


def test_argb_to_rgba():
    argb = bytes([0x80, 0x10, 0x20, 0x30, 0xFF, 0x01, 0x02, 0x03])
    assert argb_to_rgba(argb, 2, 1) == bytes([0x10, 0x20, 0x30, 0x80, 0x01, 0x02, 0x03, 0xFF])


def test_argb_to_rgba_ignores_trailing_bytes_and_rejects_short_data():
    assert argb_to_rgba(bytes([1, 2, 3, 4, 9]), 1, 1) == bytes([2, 3, 4, 1])
    with pytest.raises(ValueError):
        argb_to_rgba(bytes(7), 2, 1)
