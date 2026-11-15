"""utils/dock_layout.py against the logic it replaced in Dock.__init__ (copied
below as the oracle), for every combination of the layout settings."""

import itertools

import pytest

from utils.dock_layout import dock_hidden, dock_layout

POSITIONS = ["Top", "Bottom", "Left", "Right", "Diagonal"]
THEMES = ["Pills", "Dense", "Edge", "Weird"]


def _old(integrated_mode, BAR_POSITION, DOCK_THEME):
    VERTICAL = BAR_POSITION in ["Left", "Right"]
    margin = None
    if not integrated_mode:
        actual_dock_is_horizontal = not VERTICAL
        if actual_dock_is_horizontal:
            anchor_to_set = "bottom"
            revealer_transition_type = "slide-up"
            main_box_orientation_val = "v"
            main_box_h_align_val = "center"
            dock_wrapper_orientation_val = "h"
        else:
            if BAR_POSITION == "Left":
                anchor_to_set = "right"
                revealer_transition_type = "slide-left"
            elif BAR_POSITION == "Right":
                anchor_to_set = "left"
                revealer_transition_type = "slide-right"
            else:
                anchor_to_set = "right"
                revealer_transition_type = "slide-left"
            main_box_orientation_val = "h"
            main_box_h_align_val = "end" if anchor_to_set == "right" else "start"
            dock_wrapper_orientation_val = "v"
        match BAR_POSITION:
            case "Top":
                margin = "-8px 0px 0px 0px"
            case "Bottom":
                margin = "0px 0px 0px 0px"
            case "Left":
                margin = "0px 0px 0px -8px"
            case "Right":
                margin = "0px -8px 0px 0px"
            case _:
                margin = "0px 0px 0px 0px"
    else:
        actual_dock_is_horizontal = True
        dock_wrapper_orientation_val = "h"
        anchor_to_set = "bottom"
        revealer_transition_type = "slide-up"
        main_box_orientation_val = "v"
        main_box_h_align_val = "center"

    classes = ["left"] if BAR_POSITION == "Right" else []
    if integrated_mode:
        classes.append("integrated")
    else:
        if dock_wrapper_orientation_val == "v":
            classes.append("vertical")
        match DOCK_THEME:
            case "Pills":
                classes.append("pills")
            case "Dense":
                classes.append("dense")
            case "Edge":
                classes.append("edge")
            case _:
                classes.append("pills")
    return dict(horizontal=actual_dock_is_horizontal, anchor=anchor_to_set,
                transition=revealer_transition_type, main_orientation=main_box_orientation_val,
                main_h_align=main_box_h_align_val, orientation=dock_wrapper_orientation_val,
                margin=margin, classes=tuple(classes), activator_first=BAR_POSITION != "Right",
                hide_corners=DOCK_THEME in ["Edge", "Dense"])


@pytest.mark.parametrize("integrated, position, theme",
                         list(itertools.product([False, True], POSITIONS, THEMES)))
def test_matches_the_old_logic(integrated, position, theme):
    assert vars(dock_layout(integrated, position, theme)) == _old(integrated, position, theme)


@pytest.mark.parametrize("position, panel_theme, enabled",
                         list(itertools.product(POSITIONS, ["Notch", "Panel"], [False, True])))
def test_hidden_matches_the_old_logic(position, panel_theme, enabled):
    should_be_embedded = (position == "Bottom") or (
        panel_theme == "Panel" and position in ["Top", "Bottom"])
    assert dock_hidden(position, panel_theme, enabled) == (should_be_embedded or not enabled)
