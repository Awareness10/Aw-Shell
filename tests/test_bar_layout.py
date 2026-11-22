"""utils/bar_layout.py against the logic it replaced in Bar.__init__ (copied
below as the oracle), for every combination of the layout settings."""

import itertools

import pytest

from utils.bar_layout import bar_layout

POSITIONS = ["Top", "Bottom", "Left", "Right", "Diagonal"]
THEMES = ["Pills", "Dense", "Edge", "Weird"]
PANEL_THEMES = ["Notch", "Panel", "Other"]


def _old(BAR_POSITION, CENTERED_BAR, BAR_THEME, PANEL_THEME):
    """modules/bar.py before the refactor, verbatim apart from self./data."""
    VERTICAL = BAR_POSITION in ["Left", "Right"]  # config/data.py
    match BAR_POSITION:
        case "Top":
            anchor_var = "left top right"
        case "Bottom":
            anchor_var = "left bottom right"
        case "Left":
            anchor_var = "left" if CENTERED_BAR else "left top bottom"
        case "Right":
            anchor_var = "right" if CENTERED_BAR else "top right bottom"
        case _:
            anchor_var = "left top right"

    if VERTICAL:
        match BAR_THEME:
            case "Edge":
                margin_var = "-8px -8px -8px -8px"
            case _:
                margin_var = "-4px -8px -4px -4px"
    else:
        match BAR_THEME:
            case "Edge":
                margin_var = "-8px -8px -8px -8px"
            case _:
                if BAR_POSITION == "Bottom":
                    margin_var = "-8px -4px -4px -4px"
                else:
                    margin_var = "-4px -4px -8px -4px"

    should_embed_dock = (
        BAR_POSITION == "Bottom"
        or (PANEL_THEME == "Panel" and BAR_POSITION in ["Top", "Bottom"])
    )
    embed = should_embed_dock and not VERTICAL
    is_centered_bar = VERTICAL and CENTERED_BAR

    match BAR_THEME:
        case "Pills":
            style = "pills"
        case "Dense":
            style = "dense"
        case "Edge":
            if VERTICAL and CENTERED_BAR:
                style = "edgecenter"
            else:
                style = "edge"
        case _:
            style = "pills"

    invert = BAR_THEME == "Dense" or BAR_THEME == "Edge"

    match BAR_POSITION:
        case "Top":
            position_class = "top"
        case "Bottom":
            position_class = "bottom"
        case "Left":
            position_class = "left"
        case "Right":
            position_class = "right"
        case _:
            position_class = "top"

    return dict(vertical=VERTICAL, centered=bool(is_centered_bar), anchor=anchor_var,
                margin=margin_var, style=style, position_class=position_class,
                invert=invert, embed_dock=embed)


@pytest.mark.parametrize(
    "position, centered, theme, panel_theme",
    list(itertools.product(POSITIONS, [False, True], THEMES, PANEL_THEMES)),
)
def test_matches_the_old_logic(position, centered, theme, panel_theme):
    assert vars(bar_layout(position, centered, theme, panel_theme)) == \
        _old(position, centered, theme, panel_theme)
