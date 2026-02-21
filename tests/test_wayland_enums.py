"""Tests for widgets/wayland.py — ensure enum aliases are C-registered GtkLayerShell types.

Regression tests for the PyGObject 3.50+ crash where custom GObject.GEnum
subclasses fail to register GTypes, causing TypeError on @Property declarations.
"""

import pytest

# GtkLayerShell requires a Wayland display, so we mock gi.repository at import time
# to test the module's enum aliasing logic without a running compositor.
from unittest.mock import MagicMock, patch
import sys


@pytest.fixture
def mock_gi_modules():
    """Set up mock gi modules so wayland.py can be imported without GTK/Wayland."""
    # Save originals
    saved = {}
    modules_to_mock = [
        "gi", "gi.repository", "gi.repository.Gdk", "gi.repository.Gtk",
        "gi.repository.GtkLayerShell", "cairo",
        "fabric", "fabric.core", "fabric.core.service",
        "fabric.utils", "fabric.utils.helpers",
        "fabric.widgets", "fabric.widgets.window",
        "loguru",
    ]
    for mod in modules_to_mock:
        saved[mod] = sys.modules.get(mod)

    # Create mocks
    mock_gi = MagicMock()

    # Create realistic GtkLayerShell enum mocks with proper members
    mock_layer = MagicMock(name="GtkLayerShell.Layer")
    mock_layer.BACKGROUND = 0
    mock_layer.BOTTOM = 1
    mock_layer.TOP = 2
    mock_layer.OVERLAY = 3
    mock_layer.ENTRY_NUMBER = 4
    mock_layer.__gtype__ = MagicMock()  # C-registered enums have __gtype__

    mock_kb = MagicMock(name="GtkLayerShell.KeyboardMode")
    mock_kb.NONE = 0
    mock_kb.EXCLUSIVE = 1
    mock_kb.ON_DEMAND = 2
    mock_kb.ENTRY_NUMBER = 3
    mock_kb.__gtype__ = MagicMock()

    mock_edge = MagicMock(name="GtkLayerShell.Edge")
    mock_edge.LEFT = 0
    mock_edge.RIGHT = 1
    mock_edge.TOP = 2
    mock_edge.BOTTOM = 3
    mock_edge.ENTRY_NUMBER = 4
    mock_edge.__gtype__ = MagicMock()

    mock_gls = MagicMock()
    mock_gls.Layer = mock_layer
    mock_gls.KeyboardMode = mock_kb
    mock_gls.Edge = mock_edge

    mock_gi.require_version = MagicMock()
    mock_gi.repository = MagicMock()
    mock_gi.repository.GtkLayerShell = mock_gls

    # Mock fabric
    mock_fabric = MagicMock()
    mock_property = MagicMock()
    mock_fabric.core.service.Property = mock_property

    mock_window = MagicMock()
    mock_fabric.widgets.window.Window = mock_window

    mock_helpers = MagicMock()
    mock_fabric.utils.helpers.extract_css_values = MagicMock()
    mock_fabric.utils.helpers.get_enum_member = MagicMock()

    # Install mocks
    sys.modules["gi"] = mock_gi
    sys.modules["gi.repository"] = mock_gi.repository
    sys.modules["gi.repository.Gdk"] = MagicMock()
    sys.modules["gi.repository.Gtk"] = MagicMock()
    sys.modules["gi.repository.GtkLayerShell"] = mock_gls
    sys.modules["cairo"] = MagicMock()
    sys.modules["fabric"] = mock_fabric
    sys.modules["fabric.core"] = mock_fabric.core
    sys.modules["fabric.core.service"] = mock_fabric.core.service
    sys.modules["fabric.utils"] = mock_fabric.utils
    sys.modules["fabric.utils.helpers"] = mock_fabric.utils.helpers
    sys.modules["fabric.widgets"] = mock_fabric.widgets
    sys.modules["fabric.widgets.window"] = mock_fabric.widgets.window
    sys.modules["loguru"] = MagicMock()

    # Remove cached wayland module so it reimports with our mocks
    sys.modules.pop("widgets.wayland", None)

    yield {
        "gls": mock_gls,
        "layer": mock_layer,
        "kb": mock_kb,
        "edge": mock_edge,
    }

    # Restore originals
    for mod in modules_to_mock:
        if saved[mod] is not None:
            sys.modules[mod] = saved[mod]
        else:
            sys.modules.pop(mod, None)
    sys.modules.pop("widgets.wayland", None)


class TestWaylandEnumAliases:
    """Regression: enums must be GtkLayerShell C-registered types, not custom Python GEnum."""

    def test_layer_is_gtklayershell_layer(self, mock_gi_modules):
        from widgets.wayland import Layer
        assert Layer is mock_gi_modules["layer"], \
            "Layer should alias GtkLayerShell.Layer, not a custom Python enum"

    def test_keyboard_mode_is_gtklayershell_keyboard_mode(self, mock_gi_modules):
        from widgets.wayland import KeyboardMode
        assert KeyboardMode is mock_gi_modules["kb"], \
            "KeyboardMode should alias GtkLayerShell.KeyboardMode"

    def test_edge_is_gtklayershell_edge(self, mock_gi_modules):
        from widgets.wayland import Edge
        assert Edge is mock_gi_modules["edge"], \
            "Edge should alias GtkLayerShell.Edge"

    def test_no_custom_genum_subclass(self, mock_gi_modules):
        """Ensure Layer/KeyboardMode/Edge are NOT defined as class statements."""
        import widgets.wayland as wmod
        import inspect
        source = inspect.getsource(wmod)
        # These patterns would indicate custom GEnum subclasses (the broken pattern)
        assert "class Layer(" not in source, \
            "Layer must not be a custom class — use GtkLayerShell.Layer alias"
        assert "class KeyboardMode(" not in source, \
            "KeyboardMode must not be a custom class — use GtkLayerShell.KeyboardMode alias"
        assert "class Edge(" not in source, \
            "Edge must not be a custom class — use GtkLayerShell.Edge alias"

    def test_enums_have_expected_members(self, mock_gi_modules):
        """Sanity check that the aliases expose the members we use."""
        from widgets.wayland import Layer, KeyboardMode, Edge
        # Layer
        assert hasattr(Layer, "TOP")
        assert hasattr(Layer, "BOTTOM")
        assert hasattr(Layer, "OVERLAY")
        assert hasattr(Layer, "BACKGROUND")
        # KeyboardMode
        assert hasattr(KeyboardMode, "NONE")
        assert hasattr(KeyboardMode, "EXCLUSIVE")
        assert hasattr(KeyboardMode, "ON_DEMAND")
        # Edge
        assert hasattr(Edge, "TOP")
        assert hasattr(Edge, "BOTTOM")
        assert hasattr(Edge, "LEFT")
        assert hasattr(Edge, "RIGHT")


class TestWaylandSourceCode:
    """Source-level checks to prevent regressions in wayland.py."""

    def test_no_gobject_import(self):
        """Ensure wayland.py doesn't import GObject (used for broken custom GEnum)."""
        import os, re
        wayland_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "widgets", "wayland.py"
        )
        with open(wayland_path) as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Check for 'import GObject' or 'from gi.repository import ... GObject'
            if re.search(r'\bimport\b.*\bGObject\b', stripped):
                pytest.fail(
                    f"wayland.py:{i}: imports GObject — custom GEnum subclasses "
                    f"are broken in PyGObject 3.50+:\n  {stripped}"
                )

    def test_uses_gtklayershell_enum_aliases(self):
        """Verify the enum aliases pattern is present in the source."""
        import os
        wayland_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "widgets", "wayland.py"
        )
        with open(wayland_path) as f:
            source = f.read()
        assert "Layer = GtkLayerShell.Layer" in source
        assert "KeyboardMode = GtkLayerShell.KeyboardMode" in source
        assert "Edge = GtkLayerShell.Edge" in source
