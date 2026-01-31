"""Tests for utils/layout.py - Layout computation functions.

These functions read from config.data globals. We need to mock the entire
config package to avoid circular import issues
(config.__init__ -> data -> settings_constants -> data).
"""

import sys
import types
import pytest


# Create mock config.data module before importing layout
_mock_data = types.ModuleType("config.data")
_mock_data.BAR_POSITION = "Top"
_mock_data.BAR_THEME = "Pills"
_mock_data.PANEL_THEME = "Notch"
_mock_data.PANEL_POSITION = "Center"

# Install mocks to prevent circular import
_mock_config = types.ModuleType("config")
sys.modules["config"] = _mock_config
sys.modules["config.data"] = _mock_data

import utils.layout as layout  # noqa: E402


def set_config(**kwargs):
    """Set config.data attributes for a test."""
    defaults = {
        "BAR_POSITION": "Top",
        "BAR_THEME": "Pills",
        "PANEL_THEME": "Notch",
        "PANEL_POSITION": "Center",
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(_mock_data, k, v)


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to defaults before each test."""
    set_config()
    yield


# =========================================================================
# is_vertical_bar
# =========================================================================

class TestIsVerticalBar:

    def test_top_is_not_vertical(self):
        set_config(BAR_POSITION="Top")
        assert layout.is_vertical_bar() is False

    def test_bottom_is_not_vertical(self):
        set_config(BAR_POSITION="Bottom")
        assert layout.is_vertical_bar() is False

    def test_left_is_vertical(self):
        set_config(BAR_POSITION="Left")
        assert layout.is_vertical_bar() is True

    def test_right_is_vertical(self):
        set_config(BAR_POSITION="Right")
        assert layout.is_vertical_bar() is True


# =========================================================================
# is_panel_vertical
# =========================================================================

class TestIsPanelVertical:

    def test_notch_never_vertical(self):
        set_config(PANEL_THEME="Notch", BAR_POSITION="Left")
        assert layout.is_panel_vertical() is False

    def test_panel_left_is_vertical(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Left")
        assert layout.is_panel_vertical() is True

    def test_panel_top_not_vertical(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Top")
        assert layout.is_panel_vertical() is False


# =========================================================================
# get_panel_anchor
# =========================================================================

class TestGetPanelAnchor:

    def test_notch_always_top(self):
        set_config(PANEL_THEME="Notch")
        assert layout.get_panel_anchor() == "top"

    def test_panel_top_center(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Top", PANEL_POSITION="Center")
        assert layout.get_panel_anchor() == "top"

    def test_panel_top_start(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Top", PANEL_POSITION="Start")
        assert layout.get_panel_anchor() == "top left"

    def test_panel_top_end(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Top", PANEL_POSITION="End")
        assert layout.get_panel_anchor() == "top right"

    def test_panel_bottom_center(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Bottom", PANEL_POSITION="Center")
        assert layout.get_panel_anchor() == "bottom"

    def test_panel_left_center(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Left", PANEL_POSITION="Center")
        assert layout.get_panel_anchor() == "left"

    def test_panel_right_start(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Right", PANEL_POSITION="Start")
        assert layout.get_panel_anchor() == "right top"


# =========================================================================
# get_revealer_transition
# =========================================================================

class TestGetRevealerTransition:

    def test_notch_slide_down(self):
        set_config(PANEL_THEME="Notch")
        assert layout.get_revealer_transition() == "slide-down"

    def test_panel_top_slide_down(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Top")
        assert layout.get_revealer_transition() == "slide-down"

    def test_panel_bottom_slide_up(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Bottom")
        assert layout.get_revealer_transition() == "slide-up"

    def test_panel_left_slide_right(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Left")
        assert layout.get_revealer_transition() == "slide-right"

    def test_panel_right_slide_left(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Right")
        assert layout.get_revealer_transition() == "slide-left"


# =========================================================================
# get_notch_margin
# =========================================================================

class TestGetNotchMargin:

    def test_panel_theme_zero_margin(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Top", BAR_THEME="Pills")
        assert layout.get_notch_margin() == "0px 0px 0px 0px"

    def test_vertical_bar_zero_margin(self):
        set_config(PANEL_THEME="Notch", BAR_POSITION="Left", BAR_THEME="Pills")
        assert layout.get_notch_margin() == "0px 0px 0px 0px"

    def test_bottom_bar_zero_margin(self):
        set_config(PANEL_THEME="Notch", BAR_POSITION="Bottom", BAR_THEME="Pills")
        assert layout.get_notch_margin() == "0px 0px 0px 0px"

    def test_top_pills_margin(self):
        set_config(PANEL_THEME="Notch", BAR_POSITION="Top", BAR_THEME="Pills")
        assert layout.get_notch_margin() == "-40px 0px 0px 0px"

    def test_top_dense_margin(self):
        set_config(PANEL_THEME="Notch", BAR_POSITION="Top", BAR_THEME="Dense")
        assert layout.get_notch_margin() == "-46px 0px 0px 0px"


# =========================================================================
# get_bar_anchor
# =========================================================================

class TestGetBarAnchor:

    def test_top(self):
        set_config(BAR_POSITION="Top")
        anchor, margin = layout.get_bar_anchor()
        assert anchor == "left top right"

    def test_bottom(self):
        set_config(BAR_POSITION="Bottom")
        anchor, margin = layout.get_bar_anchor()
        assert anchor == "left bottom right"

    def test_left(self):
        set_config(BAR_POSITION="Left")
        anchor, margin = layout.get_bar_anchor()
        assert anchor == "left top bottom"

    def test_right(self):
        set_config(BAR_POSITION="Right")
        anchor, margin = layout.get_bar_anchor()
        assert anchor == "right top bottom"


# =========================================================================
# get_vert_comp_size
# =========================================================================

class TestGetVertCompSize:

    def test_panel_vertical_returns_1(self):
        set_config(PANEL_THEME="Panel", BAR_POSITION="Left", BAR_THEME="Pills")
        assert layout.get_vert_comp_size() == 1

    def test_pills_returns_38(self):
        set_config(PANEL_THEME="Notch", BAR_POSITION="Top", BAR_THEME="Pills")
        assert layout.get_vert_comp_size() == 38

    def test_dense_returns_50(self):
        set_config(PANEL_THEME="Notch", BAR_POSITION="Top", BAR_THEME="Dense")
        assert layout.get_vert_comp_size() == 50

    def test_edge_returns_44(self):
        set_config(PANEL_THEME="Notch", BAR_POSITION="Top", BAR_THEME="Edge")
        assert layout.get_vert_comp_size() == 44


# =========================================================================
# should_invert_style
# =========================================================================

class TestShouldInvertStyle:

    def test_top_dense_inverts(self):
        set_config(BAR_POSITION="Top", BAR_THEME="Dense")
        assert layout.should_invert_style() is True

    def test_top_pills_no_invert(self):
        set_config(BAR_POSITION="Top", BAR_THEME="Pills")
        assert layout.should_invert_style() is False

    def test_bottom_dense_no_invert(self):
        set_config(BAR_POSITION="Bottom", BAR_THEME="Dense")
        assert layout.should_invert_style() is False

    def test_left_dense_no_invert(self):
        set_config(BAR_POSITION="Left", BAR_THEME="Dense")
        assert layout.should_invert_style() is False

    def test_top_edge_inverts(self):
        set_config(BAR_POSITION="Top", BAR_THEME="Edge")
        assert layout.should_invert_style() is True
