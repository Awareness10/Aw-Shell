from typing import Tuple
import config.data as data


def is_vertical_bar() -> bool:
    return data.BAR_POSITION in ("Left", "Right")


def is_panel_vertical() -> bool:
    return data.PANEL_THEME == "Panel" and is_vertical_bar()


def get_panel_anchor() -> str:
    if data.PANEL_THEME == "Notch":
        return "top"

    if is_panel_vertical():
        if data.BAR_POSITION == "Left":
            base = "left"
            position_map = {"Start": "left top", "Center": "left", "End": "left bottom"}
        else:
            base = "right"
            position_map = {"Start": "right top", "Center": "right", "End": "right bottom"}
        return position_map.get(data.PANEL_POSITION, base)
    else:
        if data.BAR_POSITION == "Top":
            base = "top"
            position_map = {"Start": "top left", "Center": "top", "End": "top right"}
        else:
            base = "bottom"
            position_map = {"Start": "bottom left", "Center": "bottom", "End": "bottom right"}
        return position_map.get(data.PANEL_POSITION, base)


def get_revealer_transition() -> str:
    if data.PANEL_THEME == "Notch":
        return "slide-down"

    if is_panel_vertical():
        return "slide-right" if data.BAR_POSITION == "Left" else "slide-left"
    else:
        return "slide-down" if data.BAR_POSITION == "Top" else "slide-up"


def get_notch_margin() -> str:
    if data.PANEL_THEME == "Panel":
        return "0px 0px 0px 0px"

    if is_vertical_bar() or data.BAR_POSITION == "Bottom":
        return "0px 0px 0px 0px"

    margin_map = {
        "Pills": "-40px 0px 0px 0px",
        "Dense": "-46px 0px 0px 0px",
        "Edge": "-46px 0px 0px 0px",
    }
    return margin_map.get(data.BAR_THEME, "-40px 8px 8px 8px")


def get_bar_anchor() -> Tuple[str, str]:
    position_map = {
        "Top": ("left top right", "0px 8px -40px 8px"),
        "Bottom": ("left bottom right", "-40px 8px 0px 8px"),
        "Left": ("left top bottom", "8px -40px 8px 0px"),
        "Right": ("right top bottom", "8px 0px 8px -40px"),
    }
    return position_map.get(data.BAR_POSITION, ("left top right", "0px 8px -40px 8px"))


def get_vert_comp_size() -> int:
    if is_panel_vertical():
        return 1
    return {"Pills": 38, "Dense": 50, "Edge": 44}.get(data.BAR_THEME, 38)


def should_invert_style() -> bool:
    return (
        not is_vertical_bar()
        and data.BAR_THEME in ("Dense", "Edge")
        and data.BAR_POSITION != "Bottom"
    )
