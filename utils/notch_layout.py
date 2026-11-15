"""Where the notch sits and how it moves, from the layout settings.

Toolkit-free, so it can be tested without GTK (tests/test_notch_layout.py).
"""

from dataclasses import dataclass

ZERO_MARGIN = "0px 0px 0px 0px"

# Top margin of a notch under a top bar, per bar theme: tucks it into the bar
_TOP_MARGINS = {
    "Pills": "-40px 0px 0px 0px",
    "Dense": "-46px 0px 0px 0px",
    "Edge": "-46px 0px 0px 0px",
}
_DEFAULT_TOP_MARGIN = "-40px 8px 8px 8px"

# Panel theme: (vertical, bar position) -> (edge, revealer transition,
# (anchor added for Start, anchor added for End)). Center sits mid-edge.
_PANEL_EDGES = {
    (True, "Left"): ("left", "slide-right", ("top", "bottom")),
    (True, "Right"): ("right", "slide-left", ("top", "bottom")),
    (False, "Top"): ("top", "slide-down", ("left", "right")),
    (False, "Bottom"): ("bottom", "slide-up", ("left", "right")),
}

# Width of the spacers beside the notch on a vertical bar, per bar theme
_VERT_COMP_SIZES = {"Pills": 38, "Dense": 50, "Edge": 44}
_DEFAULT_VERT_COMP_SIZE = 38


@dataclass(frozen=True)
class NotchLayout:
    is_panel_vertical: bool
    anchor: str
    revealer_transition: str
    margin: str
    exclusivity: str
    # "invert" style class on the notch content stack
    invert: bool
    # Narrow, tall view sizes (side and corner panels)
    narrow_views: bool
    # Spacer width beside the notch on a vertical bar; None: no spacers
    vert_comp_size: int | None
    # Margin close_notch sets while the bar is hidden at the top
    hidden_bar_margin: str
    # Bar side revealers stay shown whatever view opens
    keep_bar_revealers: bool


def top_margin(bar_theme: str) -> str:
    return _TOP_MARGINS.get(bar_theme, _DEFAULT_TOP_MARGIN)


def _anchor(panel_theme, bar_position, panel_position, is_panel_vertical):
    if panel_theme == "Panel":
        edge = _PANEL_EDGES.get((bool(is_panel_vertical), bar_position))
        if edge is not None:
            side, transition, (start, end) = edge
            corner = {"Start": start, "End": end}.get(panel_position)
            return (f"{side} {corner}" if corner else side), transition
    return "top", "slide-down"


def notch_layout(
    panel_theme: str,
    bar_position: str,
    panel_position: str,
    vertical: bool,
    bar_theme: str,
) -> NotchLayout:
    is_panel = panel_theme == "Panel"
    is_panel_vertical = vertical if is_panel else False
    anchor, transition = _anchor(panel_theme, bar_position, panel_position, is_panel_vertical)

    if is_panel or vertical or bar_position == "Bottom":
        margin = ZERO_MARGIN
    else:
        margin = top_margin(bar_theme)

    vert_comp_size = None
    if vertical:
        vert_comp_size = 1 if is_panel_vertical else _VERT_COMP_SIZES.get(
            bar_theme, _DEFAULT_VERT_COMP_SIZE
        )

    return NotchLayout(
        is_panel_vertical=is_panel_vertical,
        anchor=anchor,
        revealer_transition=transition,
        margin=margin,
        exclusivity="none" if panel_theme == "Notch" else "normal",
        invert=(not vertical and bar_theme in ("Dense", "Edge") and bar_position != "Bottom"),
        narrow_views=bool(is_panel_vertical or (is_panel and panel_position in ("Start", "End"))),
        vert_comp_size=vert_comp_size,
        hidden_bar_margin=top_margin(bar_theme),
        keep_bar_revealers=(
            (is_panel and bar_position in ("Top", "Bottom"))
            or (panel_theme == "Notch" and bar_position == "Bottom")
        ),
    )
