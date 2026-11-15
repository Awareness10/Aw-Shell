"""Characterization tests for utils/notch_layout.py.

The oracle below is the layout logic copied verbatim (only `data.X` turned
into parameters) from `Notch.__init__` / `close_notch` / `_open_notch_internal`
in modules/notch.py as of v1.3.0, before it moved into notch_layout(). Every
combination of the settings, plus an unknown value for each, must give the
same result.
"""

import itertools

import pytest

from utils.notch_layout import NotchLayout, notch_layout

PANEL_THEMES = ["Notch", "Panel", "Unknown"]
BAR_POSITIONS = ["Top", "Bottom", "Left", "Right", "Unknown"]
PANEL_POSITIONS = ["Start", "Center", "End", "Unknown"]
BAR_THEMES = ["Pills", "Dense", "Edge", "Unknown"]
VERTICALS = [False, True]  # independent of bar_position, to cover odd configs too


def old_layout(PANEL_THEME, BAR_POSITION, PANEL_POSITION, VERTICAL, BAR_THEME):  # noqa: N803, C901
    """The pre-refactor code, verbatim."""
    is_panel_vertical = False
    if PANEL_THEME == "Panel":
        is_panel_vertical = VERTICAL

    anchor_val = "top"
    revealer_transition_type = "slide-down"

    if PANEL_THEME == "Notch":
        anchor_val = "top"
        revealer_transition_type = "slide-down"
    elif PANEL_THEME == "Panel":
        if is_panel_vertical:
            if BAR_POSITION == "Left":
                match PANEL_POSITION:
                    case "Start":
                        anchor_val = "left top"
                        revealer_transition_type = "slide-right"
                    case "Center":
                        anchor_val = "left"
                        revealer_transition_type = "slide-right"
                    case "End":
                        anchor_val = "left bottom"
                        revealer_transition_type = "slide-right"
                    case _:
                        anchor_val = "left"
                        revealer_transition_type = "slide-right"
            elif BAR_POSITION == "Right":
                match PANEL_POSITION:
                    case "Start":
                        anchor_val = "right top"
                        revealer_transition_type = "slide-left"
                    case "Center":
                        anchor_val = "right"
                        revealer_transition_type = "slide-left"
                    case "End":
                        anchor_val = "right bottom"
                        revealer_transition_type = "slide-left"
                    case _:
                        anchor_val = "right"
                        revealer_transition_type = "slide-left"
        else:
            if BAR_POSITION == "Top":
                match PANEL_POSITION:
                    case "Start":
                        anchor_val = "top left"
                        revealer_transition_type = "slide-down"
                    case "Center":
                        anchor_val = "top"
                        revealer_transition_type = "slide-down"
                    case "End":
                        anchor_val = "top right"
                        revealer_transition_type = "slide-down"
                    case _:
                        anchor_val = "top"
                        revealer_transition_type = "slide-down"
            elif BAR_POSITION == "Bottom":
                match PANEL_POSITION:
                    case "Start":
                        anchor_val = "bottom left"
                        revealer_transition_type = "slide-up"
                    case "Center":
                        anchor_val = "bottom"
                        revealer_transition_type = "slide-up"
                    case "End":
                        anchor_val = "bottom right"
                        revealer_transition_type = "slide-up"
                    case _:
                        anchor_val = "bottom"
                        revealer_transition_type = "slide-up"

    default_top_anchor_margin_str = "-40px 8px 8px 8px"
    pills_margin_top_str = "-40px 0px 0px 0px"
    dense_edge_margin_top_str = "-46px 0px 0px 0px"
    current_margin_str = ""

    if PANEL_THEME == "Panel":
        current_margin_str = "0px 0px 0px 0px"
    else:
        if VERTICAL:
            current_margin_str = "0px 0px 0px 0px"
        else:
            if BAR_POSITION == "Bottom":
                current_margin_str = "0px 0px 0px 0px"
            else:
                match BAR_THEME:
                    case "Pills":
                        current_margin_str = pills_margin_top_str
                    case "Dense" | "Edge":
                        current_margin_str = dense_edge_margin_top_str
                    case _:
                        current_margin_str = default_top_anchor_margin_str

    exclusivity = "none" if PANEL_THEME == "Notch" else "normal"

    # Notch-content stack style class
    invert = (not VERTICAL and BAR_THEME in ["Dense", "Edge"]) and BAR_POSITION not in ["Bottom"]

    # Size requests: narrow/tall views for side and corner panels
    narrow_views = bool(is_panel_vertical or (
        PANEL_POSITION in ["Start", "End"] and PANEL_THEME == "Panel"
    ))

    # Spacers beside the notch on a vertical bar
    vert_comp_size = None
    if VERTICAL:
        vert_comp_size = {
            "Pills": 38,
            "Dense": 50,
            "Edge": 44,
        }.get(BAR_THEME, 38)
        if is_panel_vertical:
            vert_comp_size = 1

    # close_notch, when the bar is hidden and at the top
    if BAR_THEME == "Pills":
        hidden_bar_margin = "-40px 0px 0px 0px"
    elif BAR_THEME in ["Dense", "Edge"]:
        hidden_bar_margin = "-46px 0px 0px 0px"
    else:
        hidden_bar_margin = "-40px 8px 8px 8px"

    # _open_notch_internal: bar side revealers stay shown whatever the view
    keep_bar_revealers = bool(
        BAR_POSITION in ["Top", "Bottom"]
        and PANEL_THEME == "Panel"
        or BAR_POSITION in ["Bottom"]
        and PANEL_THEME == "Notch"
    )

    return NotchLayout(
        is_panel_vertical=is_panel_vertical,
        anchor=anchor_val,
        revealer_transition=revealer_transition_type,
        margin=current_margin_str,
        exclusivity=exclusivity,
        invert=invert,
        narrow_views=narrow_views,
        vert_comp_size=vert_comp_size,
        hidden_bar_margin=hidden_bar_margin,
        keep_bar_revealers=keep_bar_revealers,
    )


COMBOS = list(
    itertools.product(PANEL_THEMES, BAR_POSITIONS, PANEL_POSITIONS, VERTICALS, BAR_THEMES)
)


@pytest.mark.parametrize("combo", COMBOS, ids=["-".join(map(str, c)) for c in COMBOS])
def test_matches_old_logic(combo):
    panel_theme, bar_position, panel_position, vertical, bar_theme = combo
    assert notch_layout(
        panel_theme=panel_theme,
        bar_position=bar_position,
        panel_position=panel_position,
        vertical=vertical,
        bar_theme=bar_theme,
    ) == old_layout(*combo)


def test_all_combinations_covered():
    assert len(COMBOS) == 3 * 5 * 4 * 2 * 4


@pytest.mark.parametrize(
    ("combo", "anchor", "transition"),
    [
        (("Notch", "Top", "Center", False, "Pills"), "top", "slide-down"),
        (("Panel", "Left", "Start", True, "Pills"), "left top", "slide-right"),
        (("Panel", "Right", "End", True, "Dense"), "right bottom", "slide-left"),
        (("Panel", "Top", "End", False, "Edge"), "top right", "slide-down"),
        (("Panel", "Bottom", "Start", False, "Pills"), "bottom left", "slide-up"),
    ],
)
def test_known_anchors(combo, anchor, transition):
    layout = notch_layout(*combo)
    assert (layout.anchor, layout.revealer_transition) == (anchor, transition)
