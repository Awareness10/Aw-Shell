"""Where the dock sits and how it's styled, from the layout settings.

Toolkit-free, so it can be tested without GTK (tests/test_dock_layout.py).
"""

from dataclasses import dataclass

# Vertical bar position -> (dock anchor, revealer transition)
_SIDE = {"Left": ("right", "slide-left"), "Right": ("left", "slide-right")}
_MARGINS = {
    "Top": "-8px 0px 0px 0px",
    "Left": "0px 0px 0px -8px",
    "Right": "0px -8px 0px 0px",
}
_THEMES = {"Pills": "pills", "Dense": "dense", "Edge": "edge"}


@dataclass(frozen=True)
class DockLayout:
    horizontal: bool
    anchor: str
    transition: str
    # Orientation of the box holding the hover strip and the dock ("v"/"h")
    main_orientation: str
    main_h_align: str
    # Orientation of the dock itself ("h"/"v")
    orientation: str
    # Window margin; None in the bar
    margin: str | None
    # Style classes on the dock box, in order
    classes: tuple
    # The hover strip comes before the dock (after it for a right bar)
    activator_first: bool
    # Corners hidden (Edge and Dense themes)
    hide_corners: bool


def dock_layout(integrated, bar_position, dock_theme) -> DockLayout:
    base_classes = ("left",) if bar_position == "Right" else ()
    if integrated:
        return DockLayout(True, "bottom", "slide-up", "v", "center", "h", None,
                          base_classes + ("integrated",), bar_position != "Right",
                          dock_theme in ("Edge", "Dense"))
    if bar_position in _SIDE:
        anchor, transition = _SIDE[bar_position]
        horizontal, main_orientation, orientation = False, "h", "v"
        main_h_align = "end" if anchor == "right" else "start"
    else:
        anchor, transition = "bottom", "slide-up"
        horizontal, main_orientation, orientation, main_h_align = True, "v", "h", "center"
    classes = base_classes + (() if horizontal else ("vertical",)) + \
        (_THEMES.get(dock_theme, "pills"),)
    return DockLayout(horizontal, anchor, transition, main_orientation, main_h_align,
                      orientation, _MARGINS.get(bar_position, "0px 0px 0px 0px"), classes,
                      bar_position != "Right", dock_theme in ("Edge", "Dense"))


def dock_hidden(bar_position, panel_theme, dock_enabled) -> bool:
    """The standalone dock stays hidden when the bar carries it or it's off."""
    embedded = bar_position == "Bottom" or (
        panel_theme == "Panel" and bar_position in ("Top", "Bottom")
    )
    return embedded or not dock_enabled
