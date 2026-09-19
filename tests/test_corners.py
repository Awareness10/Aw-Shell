"""Tests for modules/corners.py — screen corners are placed per monitor."""

import importlib
import sys
import types
from unittest.mock import patch

import pytest


class _Widget:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def add(self, *args):
        pass

    def show_all(self):
        pass


@pytest.fixture
def corners_module():
    """Import modules.corners with fabric widgets and WaylandWindow stubbed."""
    stubs = {}
    for name, attr in [
        ("fabric.widgets.box", "Box"),
        ("fabric.widgets.button", "Button"),
        ("fabric.widgets.centerbox", "CenterBox"),
        ("fabric.widgets.shapes", "Corner"),
        ("widgets.wayland", "WaylandWindow"),
    ]:
        mod = types.ModuleType(name)
        setattr(mod, attr, type(attr, (_Widget,), {}))
        stubs[name] = mod
    stubs["fabric.widgets"] = types.ModuleType("fabric.widgets")
    with patch.dict(sys.modules, stubs):
        sys.modules.pop("modules.corners", None)
        yield importlib.import_module("modules.corners")
    sys.modules.pop("modules.corners", None)


def test_corners_placed_on_given_monitor(corners_module):
    assert corners_module.Corners(monitor_id=1).kwargs["monitor"] == 1


def test_corners_default_to_first_monitor(corners_module):
    assert corners_module.Corners().kwargs["monitor"] == 0
