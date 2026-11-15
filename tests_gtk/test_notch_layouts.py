"""A real Notch built under each kind of layout setting.

EXPECTED was recorded from modules/notch.py as of v1.3.0, before the layout
and __init__ refactor; the notch must still come out the same.
"""

from unittest.mock import MagicMock

import pytest

import config.data as data

LAYOUTS = {
    # name: (panel_theme, bar_position, panel_position, bar_theme)
    "notch-top-pills": ("Notch", "Top", "Center", "Pills"),
    "notch-top-dense": ("Notch", "Top", "Center", "Dense"),
    "notch-bottom-edge": ("Notch", "Bottom", "Center", "Edge"),
    "notch-left-pills": ("Notch", "Left", "Center", "Pills"),
    "panel-top-start": ("Panel", "Top", "Start", "Pills"),
    "panel-bottom-end": ("Panel", "Bottom", "End", "Dense"),
    "panel-left-start": ("Panel", "Left", "Start", "Edge"),
    "panel-right-center": ("Panel", "Right", "Center", "Pills"),
}


def snapshot(notch, run_pending):
    def classes(widget):
        return sorted(widget.get_style_context().list_classes())

    shot = {
        "anchor": [str(edge) for edge in notch.anchor],
        "margin": list(notch.margin),
        "exclusivity": str(notch.exclusivity),
        "transition": notch.notch_revealer.get_transition_type().value_nick,
        "revealed": notch.notch_revealer.get_reveal_child(),
        "stack": classes(notch.stack),
        "notch_box": classes(notch.notch_box),
        "complete": notch.notch_complete.get_orientation().value_nick,
        "wrap": [list(c.get_size_request()) for c in notch.notch_wrap.get_children()],
        "hover_box": hasattr(notch, "hover_eventbox"),
        "corners": [notch.corner_left.get_visible(), notch.corner_right.get_visible()],
        "sizes": [list(w.get_size_request()) for w in (
            notch.compact, notch.launcher, notch.tmux, notch.cliphist, notch.dashboard)],
    }
    # Open and close with the bar hidden: margins and bar revealers
    notch.bar = MagicMock(name="bar")
    notch.bar.get_visible.return_value = False
    notch._open_notch_internal("overview")
    run_pending()
    shot["open_margin"] = list(notch.margin)
    shot["open_bar_revealers"] = notch.bar.revealer_right.set_reveal_child.call_args.args[0]
    notch._open_notch_internal("overview")
    run_pending()
    shot["closed_margin"] = list(notch.margin)
    shot["closed_revealed"] = notch.notch_revealer.get_reveal_child()
    return shot


EXPECTED = {'notch-top-pills': {'anchor': ['2'],
                     'margin': [-40, 0, 0, 0],
                     'exclusivity': 'WaylandWindowExclusivity.NONE',
                     'transition': 'slide-down',
                     'revealed': True,
                     'stack': [],
                     'notch_box': ['notch', 'vertical'],
                     'complete': 'horizontal',
                     'wrap': [[-1, -1]],
                     'hover_box': True,
                     'corners': [True, True],
                     'sizes': [[260, 40], [480, 244], [480, 244], [480, 244], [1093, 472]],
                     'open_margin': [0, 8, 8, 8],
                     'open_bar_revealers': False,
                     'closed_margin': [-40, 0, 0, 0],
                     'closed_revealed': True},
 'notch-top-dense': {'anchor': ['2'],
                     'margin': [-46, 0, 0, 0],
                     'exclusivity': 'WaylandWindowExclusivity.NONE',
                     'transition': 'slide-down',
                     'revealed': True,
                     'stack': ['invert'],
                     'notch_box': ['notch', 'vertical'],
                     'complete': 'horizontal',
                     'wrap': [[-1, -1]],
                     'hover_box': True,
                     'corners': [True, True],
                     'sizes': [[260, 40], [480, 244], [480, 244], [480, 244], [1093, 472]],
                     'open_margin': [0, 8, 8, 8],
                     'open_bar_revealers': False,
                     'closed_margin': [-46, 0, 0, 0],
                     'closed_revealed': True},
 'notch-bottom-edge': {'anchor': ['2'],
                       'margin': [0, 0, 0, 0],
                       'exclusivity': 'WaylandWindowExclusivity.NONE',
                       'transition': 'slide-down',
                       'revealed': True,
                       'stack': [],
                       'notch_box': ['notch', 'vertical'],
                       'complete': 'horizontal',
                       'wrap': [[-1, -1]],
                       'hover_box': True,
                       'corners': [True, True],
                       'sizes': [[260, 40], [480, 244], [480, 244], [480, 244], [1093, 472]],
                       'open_margin': [0, 0, 0, 0],
                       'open_bar_revealers': True,
                       'closed_margin': [0, 0, 0, 0],
                       'closed_revealed': True},
 'notch-left-pills': {'anchor': ['2'],
                      'margin': [0, 0, 0, 0],
                      'exclusivity': 'WaylandWindowExclusivity.NONE',
                      'transition': 'slide-down',
                      'revealed': True,
                      'stack': [],
                      'notch_box': ['notch', 'vertical'],
                      'complete': 'horizontal',
                      'wrap': [[38, 1], [-1, -1], [38, 1]],
                      'hover_box': True,
                      'corners': [True, True],
                      'sizes': [[260, 40], [480, 244], [480, 244], [480, 244], [1093, 472]],
                      'open_margin': [0, 0, 0, 0],
                      'open_bar_revealers': False,
                      'closed_margin': [0, 0, 0, 0],
                      'closed_revealed': True},
 'panel-top-start': {'anchor': ['2', '0'],
                     'margin': [0, 0, 0, 0],
                     'exclusivity': 'WaylandWindowExclusivity.NORMAL',
                     'transition': 'slide-down',
                     'revealed': False,
                     'stack': ['panel', 'start', 'top'],
                     'notch_box': ['panel', 'vertical'],
                     'complete': 'horizontal',
                     'wrap': [[-1, -1]],
                     'hover_box': False,
                     'corners': [False, False],
                     'sizes': [[260, 40], [320, 635], [320, 635], [320, 635], [410, 900]],
                     'open_margin': [0, 8, 8, 8],
                     'open_bar_revealers': True,
                     'closed_margin': [-40, 0, 0, 0],
                     'closed_revealed': False},
 'panel-bottom-end': {'anchor': ['1', '3'],
                      'margin': [0, 0, 0, 0],
                      'exclusivity': 'WaylandWindowExclusivity.NORMAL',
                      'transition': 'slide-up',
                      'revealed': False,
                      'stack': ['bottom', 'end', 'panel'],
                      'notch_box': ['panel', 'vertical'],
                      'complete': 'horizontal',
                      'wrap': [[-1, -1]],
                      'hover_box': False,
                      'corners': [False, False],
                      'sizes': [[260, 40], [320, 635], [320, 635], [320, 635], [410, 900]],
                      'open_margin': [0, 0, 0, 0],
                      'open_bar_revealers': True,
                      'closed_margin': [0, 0, 0, 0],
                      'closed_revealed': False},
 'panel-left-start': {'anchor': ['2', '0'],
                      'margin': [0, 0, 0, 0],
                      'exclusivity': 'WaylandWindowExclusivity.NORMAL',
                      'transition': 'slide-right',
                      'revealed': False,
                      'stack': ['left', 'panel', 'start'],
                      'notch_box': ['panel', 'vertical'],
                      'complete': 'vertical',
                      'wrap': [[1, 1], [-1, -1], [1, 1]],
                      'hover_box': False,
                      'corners': [False, False],
                      'sizes': [[260, 40], [320, 635], [320, 635], [320, 635], [410, 900]],
                      'open_margin': [0, 0, 0, 0],
                      'open_bar_revealers': False,
                      'closed_margin': [0, 0, 0, 0],
                      'closed_revealed': False},
 'panel-right-center': {'anchor': ['1'],
                        'margin': [0, 0, 0, 0],
                        'exclusivity': 'WaylandWindowExclusivity.NORMAL',
                        'transition': 'slide-left',
                        'revealed': False,
                        'stack': ['center', 'panel', 'right'],
                        'notch_box': ['panel', 'vertical'],
                        'complete': 'vertical',
                        'wrap': [[1, 1], [-1, -1], [1, 1]],
                        'hover_box': False,
                        'corners': [False, False],
                        'sizes': [[260, 40], [320, 635], [320, 635], [320, 635], [410, 900]],
                        'open_margin': [0, 0, 0, 0],
                        'open_bar_revealers': False,
                        'closed_margin': [0, 0, 0, 0],
                        'closed_revealed': False}}


@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_layout(layout, monkeypatch, run_pending):
    from modules.notch import Notch

    panel_theme, bar_position, panel_position, bar_theme = LAYOUTS[layout]
    monkeypatch.setattr(data, "PANEL_THEME", panel_theme)
    monkeypatch.setattr(data, "BAR_POSITION", bar_position)
    monkeypatch.setattr(data, "VERTICAL", bar_position in ["Left", "Right"])
    monkeypatch.setattr(data, "PANEL_POSITION", panel_position)
    monkeypatch.setattr(data, "BAR_THEME", bar_theme)

    notch = Notch(monitor_id=0)
    run_pending()
    try:
        shot = snapshot(notch, run_pending)
    finally:
        notch.destroy()
        run_pending()
    assert shot == EXPECTED[layout]
