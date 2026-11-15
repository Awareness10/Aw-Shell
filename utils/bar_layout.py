"""Where the bar sits and how it's styled, from the layout settings.

Toolkit-free, so it can be tested without GTK (tests/test_bar_layout.py).
"""

from dataclasses import dataclass

_ANCHORS = {
    "Top": "left top right",
    "Bottom": "left bottom right",
}
# Vertical bars: (position) -> (centered anchor, full-height anchor)
_SIDE_ANCHORS = {
    "Left": ("left", "left top bottom"),
    "Right": ("right", "top right bottom"),
}
_THEME_CLASSES = {"Pills": "pills", "Dense": "dense", "Edge": "edge"}
_POSITION_CLASSES = {"Top": "top", "Bottom": "bottom", "Left": "left", "Right": "right"}


@dataclass(frozen=True)
class BarLayout:
    vertical: bool
    # Vertical and centered: every widget in one centered column
    centered: bool
    anchor: str
    margin: str
    # Theme class on bar-inner (and the embedded dock)
    style: str
    # Position class on bar-inner
    position_class: str
    # "invert" style class on the bar's widgets
    invert: bool
    # The dock is part of a horizontal bar
    embed_dock: bool


def bar_layout(bar_position, centered_bar, bar_theme, panel_theme) -> BarLayout:
    vertical = bar_position in _SIDE_ANCHORS
    if vertical:
        centered_anchor, full_anchor = _SIDE_ANCHORS[bar_position]
        anchor = centered_anchor if centered_bar else full_anchor
    else:
        anchor = _ANCHORS.get(bar_position, _ANCHORS["Top"])

    if bar_theme == "Edge":
        margin = "-8px -8px -8px -8px"
    elif vertical:
        margin = "-4px -8px -4px -4px"
    elif bar_position == "Bottom":
        margin = "-8px -4px -4px -4px"
    else:
        margin = "-4px -4px -8px -4px"

    style = _THEME_CLASSES.get(bar_theme, "pills")
    if style == "edge" and vertical and centered_bar:
        style = "edgecenter"

    embed = bar_position == "Bottom" or (
        panel_theme == "Panel" and bar_position in ("Top", "Bottom")
    )
    return BarLayout(
        vertical=vertical,
        centered=bool(vertical and centered_bar),
        anchor=anchor,
        margin=margin,
        style=style,
        position_class=_POSITION_CLASSES.get(bar_position, "top"),
        invert=bar_theme in ("Dense", "Edge"),
        embed_dock=embed and not vertical,
    )
