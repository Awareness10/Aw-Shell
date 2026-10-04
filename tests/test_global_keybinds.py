"""The "Toggle Bar" keybind: hide/show every bar, move notch and docks with it."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

import utils.global_keybinds as gk


@pytest.fixture(autouse=True)
def fresh_singleton():
    gk.GlobalKeybindHandler._instance = None
    gk._global_keybind_handler_instance = None
    yield
    gk.GlobalKeybindHandler._instance = None
    gk._global_keybind_handler_instance = None


@pytest.fixture
def docks():
    """modules.dock.Dock stand-in; toggle_bar imports it lazily."""
    instances = [MagicMock(name="dock0"), MagicMock(name="dock1")]
    module = types.ModuleType("modules.dock")
    module.Dock = types.SimpleNamespace(_instances=instances)
    with patch.dict(sys.modules, {"modules.dock": module}):
        yield instances


def _bar(visible):
    bar = MagicMock(name="bar")
    bar.get_visible.return_value = visible
    return bar


def _manager(components):
    """components: {monitor_id: {"bar": ..., "notch": ...}}"""
    manager = MagicMock(name="monitor_manager")
    manager.get_monitors.return_value = [{"id": i} for i in components]
    manager.get_instance.side_effect = lambda mid, name: components[mid].get(name)
    return manager


def _handler(manager):
    handler = gk.get_global_keybind_handler()
    handler.set_monitor_manager(manager)
    return handler


def test_without_monitor_manager_does_nothing():
    assert gk.get_global_keybind_handler().toggle_bar() is False


def test_hiding_bar_forces_occlusion(docks):
    bar, notch = _bar(visible=True), MagicMock(name="notch")
    assert _handler(_manager({0: {"bar": bar, "notch": notch}})).toggle_bar() is True

    bar.set_visible.assert_called_once_with(False)
    notch.force_occlusion.assert_called_once_with()
    notch.restore_from_occlusion.assert_not_called()
    for dock in docks:
        dock.force_occlusion.assert_called_once_with()


def test_showing_bar_restores_from_occlusion(docks):
    bar, notch = _bar(visible=False), MagicMock(name="notch")
    assert _handler(_manager({0: {"bar": bar, "notch": notch}})).toggle_bar() is True

    bar.set_visible.assert_called_once_with(True)
    notch.restore_from_occlusion.assert_called_once_with()
    notch.force_occlusion.assert_not_called()
    for dock in docks:
        dock.restore_from_occlusion.assert_called_once_with()


def test_every_monitor_toggles(docks):
    left, right = _bar(visible=True), _bar(visible=True)
    manager = _manager({
        0: {"bar": left, "notch": MagicMock()},
        1: {"bar": right, "notch": MagicMock()},
    })
    _handler(manager).toggle_bar()
    left.set_visible.assert_called_once_with(False)
    right.set_visible.assert_called_once_with(False)


def test_monitor_without_bar_or_notch_is_skipped(docks):
    bar, notch = _bar(visible=True), MagicMock(name="notch")
    manager = _manager({
        0: {"bar": None, "notch": notch},  # bar disabled on this monitor
        1: {"bar": bar, "notch": None},
    })
    assert _handler(manager).toggle_bar() is True
    bar.set_visible.assert_not_called()
    notch.force_occlusion.assert_not_called()


def test_error_reports_failure(docks):
    bar = _bar(visible=True)
    bar.set_visible.side_effect = RuntimeError("widget destroyed")
    manager = _manager({0: {"bar": bar, "notch": MagicMock()}})
    assert _handler(manager).toggle_bar() is False


def test_handler_is_a_singleton():
    assert gk.get_global_keybind_handler() is gk.get_global_keybind_handler()
    assert gk.GlobalKeybindHandler() is gk.get_global_keybind_handler()


def test_init_connects_monitor_manager():
    manager = MagicMock(name="monitor_manager")
    with patch("utils.monitor_manager.get_monitor_manager", return_value=manager):
        handler = gk.init_global_keybind_objects()
    assert handler is gk.get_global_keybind_handler()
    assert handler._monitor_manager is manager
