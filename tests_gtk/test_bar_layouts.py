"""A real Bar built under each kind of layout setting.

EXPECTED was recorded from modules/bar.py before the layout and __init__
refactor (wave 2); the bar must still come out the same.
"""

import pytest

from config.shell_settings import settings as shell_settings

LAYOUTS = {
    # name: settings
    "top-pills": dict(BAR_POSITION="Top", BAR_THEME="Pills"),
    "top-edge-panel": dict(BAR_POSITION="Top", BAR_THEME="Edge", PANEL_THEME="Panel"),
    "bottom-dense": dict(BAR_POSITION="Bottom", BAR_THEME="Dense"),
    "left-edge-centered": dict(BAR_POSITION="Left", BAR_THEME="Edge", CENTERED_BAR=True),
    "left-dense": dict(BAR_POSITION="Left", BAR_THEME="Dense"),
    "right-pills": dict(BAR_POSITION="Right", BAR_THEME="Pills"),
    "top-runes-12h": dict(BAR_POSITION="Top", BAR_THEME="Pills", BAR_WORKSPACE_SHOW_NUMBER=True,
                          BAR_WORKSPACE_USE_RUNES=True, DATETIME_12H_FORMAT=True,
                          BAR_HIDE_SPECIAL_WORKSPACE=True),
}
DEFAULTS = dict(PANEL_THEME="Notch", CENTERED_BAR=False, BAR_WORKSPACE_SHOW_NUMBER=False,
                BAR_WORKSPACE_USE_RUNES=False, DATETIME_12H_FORMAT=False,
                BAR_HIDE_SPECIAL_WORKSPACE=False)


def _describe(widget):
    text = ""
    child = widget.get_child() if hasattr(widget, "get_child") else None
    if type(widget).__name__ == "DateTime":
        child = None  # the clock's text changes every minute
    if child is not None and hasattr(child, "get_label"):
        text = child.get_label() or ""
    return f"{type(widget).__name__}#{widget.get_name()}{':' + text if text else ''}"


def _children(box):
    if box is None:
        return None
    return [_describe(c) for c in box.get_children()]


def _walk(widget):
    yield widget
    if hasattr(widget, "get_children"):
        for child in widget.get_children():
            yield from _walk(child)


def _box(workspaces):
    return next(w for w in _walk(workspaces) if w is not workspaces and hasattr(w, "get_spacing"))


def _buttons(workspaces):
    return [w for w in _walk(workspaces) if type(w).__name__ == "WorkspaceButton"]


def snapshot(bar):
    def classes(widget):
        return sorted(widget.get_style_context().list_classes())

    inner = bar.bar_inner
    start = inner.start_children[0] if inner.start_children else None
    end = inner.end_children[0] if inner.end_children else None
    center = inner.center_children[0] if inner.center_children else None
    themed = [bar.button_apps, bar.button_overview, bar.button_power, bar.button_tools,
              bar.language, bar.date_time, bar.ws_container, bar.weather, bar.network,
              bar.battery, bar.metrics, bar.systray, bar.control, bar.recording]
    return {
        "anchor": [str(edge) for edge in bar.anchor],
        "margin": list(bar.margin),
        "inner": classes(inner),
        "orientation": inner.get_orientation().value_nick,
        "start": _children(start),
        "center": _describe(center) if center is not None else None,
        "center_children": _children(center) if hasattr(center, "get_children") else None,
        "end": _children(end),
        "revealers": [_children(bar.revealer_left.get_child()),
                      _children(bar.revealer_right.get_child())],
        "invert": [w.get_style_context().has_class("invert") for w in themed],
        "dock": bar.integrated_dock_widget is not None,
        "dock_classes": classes(bar.integrated_dock_widget) if bar.integrated_dock_widget else None,
        "workspaces": _children(bar.ws_container),
        "workspaces_num": classes(bar.workspaces_num) + [_box(bar.workspaces_num).get_spacing()],
        "ws_buttons": [b.get_label() for b in _buttons(bar.workspaces_num)][:3],
        "ws_vertical": classes(_buttons(bar.workspaces)[0]),
        "time_format": list(bar.date_time.formatters),
        "date_time": classes(bar.date_time),
        "language": bar.lang_label.get_label(),
    }


EXPECTED = {'top-pills': {'anchor': ['2', '1', '0'],
               'margin': [-4, -4, -8, -4],
               'inner': ['pills', 'top', 'vertical'],
               'orientation': 'vertical',
               'start': ["Button#button-bar:<span font-family='tabler-icons' "
                         "font-weight='normal'>&#xf1fd;</span>",
                         'Box#workspaces-container',
                         "Button#button-bar:<span font-family='tabler-icons' "
                         "font-weight='normal'>&#xefe6;</span>",
                         'Box#boxed-revealer'],
               'center': None,
               'center_children': None,
               'end': ['Box#boxed-revealer',
                       'Battery#metrics-small',
                       'SystemTray#systray',
                       'RecordingIndicator#recording-indicator',
                       "Button#button-bar:<span font-family='tabler-icons' "
                       "font-weight='normal'>&#xebca;</span>",
                       'Button#language:ENG',
                       'DateTime#date-time',
                       "Button#button-bar:<span font-family='tabler-icons' "
                       "font-weight='normal'>&#xeb0d;</span>"],
               'revealers': [["Weather#weather:<span font-family='tabler-icons' "
                              "font-weight='normal'>&#xeca3;</span>",
                              'Systemprofiles#systemprofiles',
                              'NetworkApplet#button-bar'],
                             ['MetricsSmall#metrics-small', 'ControlSmall#control-small']],
               'invert': [False,
                          False,
                          False,
                          False,
                          False,
                          False,
                          False,
                          False,
                          False,
                          False,
                          False,
                          False,
                          False,
                          False],
               'dock': False,
               'dock_classes': None,
               'workspaces': ['HyprlandWorkspaces#widgets+hyprland+HyprlandWorkspaces'],
               'workspaces_num': [0],
               'ws_buttons': ['1', '2', '3'],
               'ws_vertical': ['active'],
               'time_format': ['%H:%M'],
               'date_time': ['text-button'],
               'language': 'ENG'},
 'top-edge-panel': {'anchor': ['2', '1', '0'],
                    'margin': [-8, -8, -8, -8],
                    'inner': ['edge', 'top', 'vertical'],
                    'orientation': 'vertical',
                    'start': ["Button#button-bar:<span font-family='tabler-icons' "
                              "font-weight='normal'>&#xf1fd;</span>",
                              'Box#workspaces-container',
                              "Button#button-bar:<span font-family='tabler-icons' "
                              "font-weight='normal'>&#xefe6;</span>",
                              'Box#boxed-revealer'],
                    'center': 'Box#dock',
                    'center_children': ['Box#viewport'],
                    'end': ['Box#boxed-revealer',
                            'Battery#metrics-small',
                            'SystemTray#systray',
                            'RecordingIndicator#recording-indicator',
                            "Button#button-bar:<span font-family='tabler-icons' "
                            "font-weight='normal'>&#xebca;</span>",
                            'Button#language:ENG',
                            'DateTime#date-time',
                            "Button#button-bar:<span font-family='tabler-icons' "
                            "font-weight='normal'>&#xeb0d;</span>"],
                    'revealers': [["Weather#weather:<span font-family='tabler-icons' "
                                   "font-weight='normal'>&#xeca3;</span>",
                                   'Systemprofiles#systemprofiles',
                                   'NetworkApplet#button-bar'],
                                  ['MetricsSmall#metrics-small', 'ControlSmall#control-small']],
                    'invert': [True,
                               True,
                               True,
                               True,
                               True,
                               True,
                               True,
                               True,
                               True,
                               True,
                               True,
                               True,
                               True,
                               True],
                    'dock': True,
                    'dock_classes': ['edge', 'horizontal', 'integrated', 'invert'],
                    'workspaces': ['HyprlandWorkspaces#widgets+hyprland+HyprlandWorkspaces'],
                    'workspaces_num': [0],
                    'ws_buttons': ['1', '2', '3'],
                    'ws_vertical': ['active'],
                    'time_format': ['%H:%M'],
                    'date_time': ['invert', 'text-button'],
                    'language': 'ENG'},
 'bottom-dense': {'anchor': ['1', '3', '0'],
                  'margin': [-8, -4, -4, -4],
                  'inner': ['bottom', 'dense', 'vertical'],
                  'orientation': 'vertical',
                  'start': ["Button#button-bar:<span font-family='tabler-icons' "
                            "font-weight='normal'>&#xf1fd;</span>",
                            'Box#workspaces-container',
                            "Button#button-bar:<span font-family='tabler-icons' "
                            "font-weight='normal'>&#xefe6;</span>",
                            'Box#boxed-revealer'],
                  'center': 'Box#dock',
                  'center_children': ['Box#viewport'],
                  'end': ['Box#boxed-revealer',
                          'Battery#metrics-small',
                          'SystemTray#systray',
                          'RecordingIndicator#recording-indicator',
                          "Button#button-bar:<span font-family='tabler-icons' "
                          "font-weight='normal'>&#xebca;</span>",
                          'Button#language:ENG',
                          'DateTime#date-time',
                          "Button#button-bar:<span font-family='tabler-icons' "
                          "font-weight='normal'>&#xeb0d;</span>"],
                  'revealers': [["Weather#weather:<span font-family='tabler-icons' "
                                 "font-weight='normal'>&#xeca3;</span>",
                                 'Systemprofiles#systemprofiles',
                                 'NetworkApplet#button-bar'],
                                ['MetricsSmall#metrics-small', 'ControlSmall#control-small']],
                  'invert': [True,
                             True,
                             True,
                             True,
                             True,
                             True,
                             True,
                             True,
                             True,
                             True,
                             True,
                             True,
                             True,
                             True],
                  'dock': True,
                  'dock_classes': ['dense', 'horizontal', 'integrated', 'invert'],
                  'workspaces': ['HyprlandWorkspaces#widgets+hyprland+HyprlandWorkspaces'],
                  'workspaces_num': [0],
                  'ws_buttons': ['1', '2', '3'],
                  'ws_vertical': ['active'],
                  'time_format': ['%H:%M'],
                  'date_time': ['invert', 'text-button'],
                  'language': 'ENG'},
 'left-edge-centered': {'anchor': ['0'],
                        'margin': [-8, -8, -8, -8],
                        'inner': ['edgecenter', 'horizontal', 'left', 'vertical'],
                        'orientation': 'horizontal',
                        'start': None,
                        'center': 'Box#fabric+widgets+box+Box',
                        'center_children': ["Button#button-bar:<span font-family='tabler-icons' "
                                            "font-weight='normal'>&#xf1fd;</span>",
                                            'SystemTray#systray',
                                            'ControlSmall#control-small',
                                            'Systemprofiles#systemprofiles',
                                            'NetworkApplet#button-bar',
                                            'RecordingIndicator#recording-indicator',
                                            "Button#button-bar:<span font-family='tabler-icons' "
                                            "font-weight='normal'>&#xebca;</span>",
                                            "Button#button-bar:<span font-family='tabler-icons' "
                                            "font-weight='normal'>&#xefe6;</span>",
                                            'Box#workspaces-container',
                                            "Weather#weather:<span font-family='tabler-icons' "
                                            "font-weight='normal'>&#xeca3;</span>",
                                            'Battery#metrics-small',
                                            'MetricsSmall#metrics-small',
                                            "Button#language:<span font-family='tabler-icons' "
                                            "font-weight='normal'>&#xebd6;</span>",
                                            'DateTime#date-time',
                                            "Button#button-bar:<span font-family='tabler-icons' "
                                            "font-weight='normal'>&#xeb0d;</span>"],
                        'end': None,
                        'revealers': [[], []],
                        'invert': [True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True,
                                   True],
                        'dock': False,
                        'dock_classes': None,
                        'workspaces': ['HyprlandWorkspaces#widgets+hyprland+HyprlandWorkspaces'],
                        'workspaces_num': [0],
                        'ws_buttons': ['1', '2', '3'],
                        'ws_vertical': ['active', 'vertical'],
                        'time_format': ['%H\n%M'],
                        'date_time': ['invert', 'text-button', 'vertical'],
                        'language': "<span font-family='tabler-icons' "
                                    "font-weight='normal'>&#xebd6;</span>"},
 'left-dense': {'anchor': ['2', '3', '0'],
                'margin': [-4, -8, -4, -4],
                'inner': ['dense', 'horizontal', 'left', 'vertical'],
                'orientation': 'horizontal',
                'start': ["Button#button-bar:<span font-family='tabler-icons' "
                          "font-weight='normal'>&#xf1fd;</span>",
                          'SystemTray#systray',
                          'ControlSmall#control-small',
                          'Systemprofiles#systemprofiles',
                          'NetworkApplet#button-bar',
                          'RecordingIndicator#recording-indicator',
                          "Button#button-bar:<span font-family='tabler-icons' "
                          "font-weight='normal'>&#xebca;</span>"],
                'center': 'Box#fabric+widgets+box+Box',
                'center_children': ["Button#button-bar:<span font-family='tabler-icons' "
                                    "font-weight='normal'>&#xefe6;</span>",
                                    'Box#workspaces-container',
                                    "Weather#weather:<span font-family='tabler-icons' "
                                    "font-weight='normal'>&#xeca3;</span>"],
                'end': ['Battery#metrics-small',
                        'MetricsSmall#metrics-small',
                        "Button#language:<span font-family='tabler-icons' "
                        "font-weight='normal'>&#xebd6;</span>",
                        'DateTime#date-time',
                        "Button#button-bar:<span font-family='tabler-icons' "
                        "font-weight='normal'>&#xeb0d;</span>"],
                'revealers': [[], []],
                'invert': [True,
                           True,
                           True,
                           True,
                           True,
                           True,
                           True,
                           True,
                           True,
                           True,
                           True,
                           True,
                           True,
                           True],
                'dock': False,
                'dock_classes': None,
                'workspaces': ['HyprlandWorkspaces#widgets+hyprland+HyprlandWorkspaces'],
                'workspaces_num': [0],
                'ws_buttons': ['1', '2', '3'],
                'ws_vertical': ['active', 'vertical'],
                'time_format': ['%H\n%M'],
                'date_time': ['invert', 'text-button', 'vertical'],
                'language': "<span font-family='tabler-icons' "
                            "font-weight='normal'>&#xebd6;</span>"},
 'right-pills': {'anchor': ['2', '1', '3'],
                 'margin': [-4, -8, -4, -4],
                 'inner': ['horizontal', 'pills', 'right', 'vertical'],
                 'orientation': 'horizontal',
                 'start': ["Button#button-bar:<span font-family='tabler-icons' "
                           "font-weight='normal'>&#xf1fd;</span>",
                           'SystemTray#systray',
                           'ControlSmall#control-small',
                           'Systemprofiles#systemprofiles',
                           'NetworkApplet#button-bar',
                           'RecordingIndicator#recording-indicator',
                           "Button#button-bar:<span font-family='tabler-icons' "
                           "font-weight='normal'>&#xebca;</span>"],
                 'center': 'Box#fabric+widgets+box+Box',
                 'center_children': ["Button#button-bar:<span font-family='tabler-icons' "
                                     "font-weight='normal'>&#xefe6;</span>",
                                     'Box#workspaces-container',
                                     "Weather#weather:<span font-family='tabler-icons' "
                                     "font-weight='normal'>&#xeca3;</span>"],
                 'end': ['Battery#metrics-small',
                         'MetricsSmall#metrics-small',
                         "Button#language:<span font-family='tabler-icons' "
                         "font-weight='normal'>&#xebd6;</span>",
                         'DateTime#date-time',
                         "Button#button-bar:<span font-family='tabler-icons' "
                         "font-weight='normal'>&#xeb0d;</span>"],
                 'revealers': [[], []],
                 'invert': [False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False],
                 'dock': False,
                 'dock_classes': None,
                 'workspaces': ['HyprlandWorkspaces#widgets+hyprland+HyprlandWorkspaces'],
                 'workspaces_num': [0],
                 'ws_buttons': ['1', '2', '3'],
                 'ws_vertical': ['active', 'vertical'],
                 'time_format': ['%H\n%M'],
                 'date_time': ['text-button', 'vertical'],
                 'language': "<span font-family='tabler-icons' "
                             "font-weight='normal'>&#xebd6;</span>"},
 'top-runes-12h': {'anchor': ['2', '1', '0'],
                   'margin': [-4, -4, -8, -4],
                   'inner': ['pills', 'top', 'vertical'],
                   'orientation': 'vertical',
                   'start': ["Button#button-bar:<span font-family='tabler-icons' "
                             "font-weight='normal'>&#xf1fd;</span>",
                             'Box#workspaces-container',
                             "Button#button-bar:<span font-family='tabler-icons' "
                             "font-weight='normal'>&#xefe6;</span>",
                             'Box#boxed-revealer'],
                   'center': None,
                   'center_children': None,
                   'end': ['Box#boxed-revealer',
                           'Battery#metrics-small',
                           'SystemTray#systray',
                           'RecordingIndicator#recording-indicator',
                           "Button#button-bar:<span font-family='tabler-icons' "
                           "font-weight='normal'>&#xebca;</span>",
                           'Button#language:ENG',
                           'DateTime#date-time',
                           "Button#button-bar:<span font-family='tabler-icons' "
                           "font-weight='normal'>&#xeb0d;</span>"],
                   'revealers': [["Weather#weather:<span font-family='tabler-icons' "
                                  "font-weight='normal'>&#xeca3;</span>",
                                  'Systemprofiles#systemprofiles',
                                  'NetworkApplet#button-bar'],
                                 ['MetricsSmall#metrics-small', 'ControlSmall#control-small']],
                   'invert': [False,
                              False,
                              False,
                              False,
                              False,
                              False,
                              False,
                              False,
                              False,
                              False,
                              False,
                              False,
                              False,
                              False],
                   'dock': False,
                   'dock_classes': None,
                   'workspaces': ['HyprlandWorkspaces#widgets+hyprland+HyprlandWorkspaces'],
                   'workspaces_num': ['runic', 4],
                   'ws_buttons': ['ᚠ', 'ᚢ', 'ᚦ'],
                   'ws_vertical': ['active'],
                   'time_format': ['%I:%M %p'],
                   'date_time': ['text-button'],
                   'language': 'ENG'}}


@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_layout(layout, monkeypatch, run_pending):
    from modules.bar import Bar

    settings = DEFAULTS | LAYOUTS[layout]
    for name, value in settings.items():
        monkeypatch.setattr(shell_settings, name.lower(), value)
    bar = Bar(monitor_id=0)
    run_pending()
    try:
        shot = snapshot(bar)
    finally:
        bar.destroy()
        run_pending()
    assert shot == EXPECTED[layout]
