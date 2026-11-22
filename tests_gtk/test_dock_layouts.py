"""A real Dock built under each kind of layout setting, its buttons for a set
of pinned and running apps, and its hover show/hide.

EXPECTED was recorded from modules/dock.py before the wave 2 refactor; the
dock must still come out the same.
"""

import json
import time

import pytest

from config.shell_settings import settings as shell_settings

LAYOUTS = {
    "bottom-bar-pills": dict(BAR_POSITION="Top", DOCK_THEME="Pills"),
    "top-bar-dense": dict(BAR_POSITION="Top", DOCK_THEME="Dense"),
    "left-bar-edge": dict(BAR_POSITION="Left", DOCK_THEME="Edge"),
    "right-bar-pills": dict(BAR_POSITION="Right", DOCK_THEME="Pills"),
    "always-show": dict(BAR_POSITION="Top", DOCK_THEME="Pills", DOCK_ALWAYS_SHOW=True),
    "embedded-bottom": dict(BAR_POSITION="Bottom", DOCK_THEME="Pills"),
    "disabled": dict(BAR_POSITION="Top", DOCK_THEME="Pills", DOCK_ENABLED=False),
}
DEFAULTS = dict(PANEL_THEME="Notch", DOCK_ENABLED=True, DOCK_ALWAYS_SHOW=False)
PINNED = ["kitty", "ghost-app"]  # old format: read_config migrates it


@pytest.fixture
def dock_file(tmp_path, monkeypatch):
    path = tmp_path / "dock.json"
    path.write_text(json.dumps({"pinned_apps": PINNED}))
    monkeypatch.setattr("modules.dock.DOCK_FILE", path)
    return path


def snapshot(dock):
    def classes(widget):
        return sorted(widget.get_style_context().list_classes())

    shot = {
        "anchor": [str(edge) for edge in dock.anchor],
        "margin": list(dock.margin),
        "exclusivity": str(dock.exclusivity),
        "visible": dock.get_visible(),
        "wrapper": classes(dock.wrapper),
        "orientation": dock.wrapper.get_orientation().value_nick,
        "view_orientation": dock.view.get_orientation().value_nick,
        "transition": dock.dock_revealer.get_transition_type().value_nick,
        "main": [type(c).__name__ for c in dock.main_box.get_children()],
        "main_orientation": dock.main_box.get_orientation().value_nick,
        "main_h_align": dock.main_box.get_halign().value_nick,
        "full": [c.get_name() for c in dock.dock_full.get_children()],
        "full_classes": classes(dock.dock_full),
        "corners": [c.get_visible() for c in (dock.corner_left, dock.corner_right,
                                               dock.corner_top, dock.corner_bottom)],
        "activator": list(dock.hover_activator.get_size_request()),
        "buttons": [[c.get_name(), c.get_tooltip_text(), classes(c)]
                    for c in dock.view.get_children()],
    }
    return shot


EXPECTED = {'bottom-bar-pills': {'anchor': ['3'],
                      'margin': [-8, 0, 0, 0],
                      'exclusivity': 'WaylandWindowExclusivity.NONE',
                      'visible': True,
                      'wrapper': ['horizontal', 'pills'],
                      'orientation': 'horizontal',
                      'view_orientation': 'horizontal',
                      'transition': 'slide-up',
                      'main': ['EventBox', 'Revealer'],
                      'main_orientation': 'vertical',
                      'main_h_align': 'center',
                      'full': ['dock-corner-left',
                               'fabric+widgets+eventbox+EventBox',
                               'dock-corner-right'],
                      'full_classes': ['horizontal', 'occluded'],
                      'corners': [True, True, True, True],
                      'activator': [-1, 1],
                      'buttons': [['dock-app-button', 'Test Window', ['instance']],
                                  ['dock-app-button', 'ghost-app', []]]},
 'top-bar-dense': {'anchor': ['3'],
                   'margin': [-8, 0, 0, 0],
                   'exclusivity': 'WaylandWindowExclusivity.NONE',
                   'visible': True,
                   'wrapper': ['dense', 'horizontal'],
                   'orientation': 'horizontal',
                   'view_orientation': 'horizontal',
                   'transition': 'slide-up',
                   'main': ['EventBox', 'Revealer'],
                   'main_orientation': 'vertical',
                   'main_h_align': 'center',
                   'full': ['dock-corner-left',
                            'fabric+widgets+eventbox+EventBox',
                            'dock-corner-right'],
                   'full_classes': ['horizontal', 'occluded'],
                   'corners': [False, False, False, False],
                   'activator': [-1, 1],
                   'buttons': [['dock-app-button', 'Test Window', ['instance']],
                               ['dock-app-button', 'ghost-app', []]]},
 'left-bar-edge': {'anchor': ['1'],
                   'margin': [0, 0, 0, -8],
                   'exclusivity': 'WaylandWindowExclusivity.NONE',
                   'visible': True,
                   'wrapper': ['edge', 'vertical'],
                   'orientation': 'vertical',
                   'view_orientation': 'vertical',
                   'transition': 'slide-left',
                   'main': ['EventBox', 'Revealer'],
                   'main_orientation': 'horizontal',
                   'main_h_align': 'end',
                   'full': ['dock-corner-top',
                            'fabric+widgets+eventbox+EventBox',
                            'dock-corner-bottom'],
                   'full_classes': ['occluded', 'vertical'],
                   'corners': [False, False, False, False],
                   'activator': [1, -1],
                   'buttons': [['dock-app-button', 'Test Window', ['instance']],
                               ['dock-app-button', 'ghost-app', []]]},
 'right-bar-pills': {'anchor': ['0'],
                     'margin': [0, -8, 0, 0],
                     'exclusivity': 'WaylandWindowExclusivity.NONE',
                     'visible': True,
                     'wrapper': ['left', 'pills', 'vertical'],
                     'orientation': 'vertical',
                     'view_orientation': 'vertical',
                     'transition': 'slide-right',
                     'main': ['Revealer', 'EventBox'],
                     'main_orientation': 'horizontal',
                     'main_h_align': 'start',
                     'full': ['dock-corner-top',
                              'fabric+widgets+eventbox+EventBox',
                              'dock-corner-bottom'],
                     'full_classes': ['occluded', 'vertical'],
                     'corners': [True, True, True, True],
                     'activator': [1, -1],
                     'buttons': [['dock-app-button', 'Test Window', ['instance']],
                                 ['dock-app-button', 'ghost-app', []]]},
 'always-show': {'anchor': ['3'],
                 'margin': [-8, 0, 0, 0],
                 'exclusivity': 'WaylandWindowExclusivity.AUTO',
                 'visible': True,
                 'wrapper': ['horizontal', 'pills'],
                 'orientation': 'horizontal',
                 'view_orientation': 'horizontal',
                 'transition': 'slide-up',
                 'main': ['EventBox', 'Revealer'],
                 'main_orientation': 'vertical',
                 'main_h_align': 'center',
                 'full': ['dock-corner-left',
                          'fabric+widgets+eventbox+EventBox',
                          'dock-corner-right'],
                 'full_classes': ['horizontal'],
                 'corners': [True, True, True, True],
                 'activator': [-1, 1],
                 'buttons': [['dock-app-button', 'Test Window', ['instance']],
                             ['dock-app-button', 'ghost-app', []]]},
 'embedded-bottom': {'anchor': ['3'],
                     'margin': [0, 0, 0, 0],
                     'exclusivity': 'WaylandWindowExclusivity.NONE',
                     'visible': False,
                     'wrapper': ['horizontal', 'pills'],
                     'orientation': 'horizontal',
                     'view_orientation': 'horizontal',
                     'transition': 'slide-up',
                     'main': ['EventBox', 'Revealer'],
                     'main_orientation': 'vertical',
                     'main_h_align': 'center',
                     'full': ['dock-corner-left',
                              'fabric+widgets+eventbox+EventBox',
                              'dock-corner-right'],
                     'full_classes': ['horizontal', 'occluded'],
                     'corners': [True, True, True, True],
                     'activator': [-1, 1],
                     'buttons': [['dock-app-button', 'Test Window', ['instance']],
                                 ['dock-app-button', 'ghost-app', []]]},
 'disabled': {'anchor': ['3'],
              'margin': [-8, 0, 0, 0],
              'exclusivity': 'WaylandWindowExclusivity.NONE',
              'visible': False,
              'wrapper': ['horizontal', 'pills'],
              'orientation': 'horizontal',
              'view_orientation': 'horizontal',
              'transition': 'slide-up',
              'main': ['EventBox', 'Revealer'],
              'main_orientation': 'vertical',
              'main_h_align': 'center',
              'full': ['dock-corner-left', 'fabric+widgets+eventbox+EventBox', 'dock-corner-right'],
              'full_classes': ['horizontal', 'occluded'],
              'corners': [True, True, True, True],
              'activator': [-1, 1],
              'buttons': [['dock-app-button', 'Test Window', ['instance']],
                          ['dock-app-button', 'ghost-app', []]]}}


@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_layout(layout, monkeypatch, run_pending, dock_file):
    from modules.dock import Dock

    settings = DEFAULTS | LAYOUTS[layout]
    for name, value in settings.items():
        monkeypatch.setattr(shell_settings, name.lower(), value)
    dock = Dock(monitor_id=0)
    run_pending()
    try:
        shot = snapshot(dock)
    finally:
        Dock._instances.remove(dock)
        dock.destroy()
        run_pending()
    assert shot == EXPECTED[layout]


def test_hover_shows_the_dock_and_leaving_hides_it(monkeypatch, run_pending, dock_file):
    from modules.dock import Dock

    for name, value in (DEFAULTS | LAYOUTS["bottom-bar-pills"]).items():
        monkeypatch.setattr(shell_settings, name.lower(), value)
    dock = Dock(monitor_id=0)
    run_pending()
    try:
        assert not dock.dock_revealer.get_reveal_child()
        dock._on_hover_enter()
        assert dock.dock_revealer.get_reveal_child()
        assert not dock.dock_full.get_style_context().has_class("occluded")
        dock._on_hover_leave()
        time.sleep(0.1)
        run_pending()
        assert dock.dock_revealer.get_reveal_child()  # hides after 250 ms
        time.sleep(0.25)
        run_pending()
        assert not dock.dock_revealer.get_reveal_child()
        assert dock.hide_id is None
    finally:
        Dock._instances.remove(dock)
        dock.destroy()
        run_pending()


def test_forced_occlusion_survives_the_config_poll(monkeypatch, run_pending, dock_file):
    """Hiding the bar forces the always-shown dock into hover mode; the
    2-second dock.json poll used to put always_show back."""
    from modules.dock import Dock

    for name, value in (DEFAULTS | LAYOUTS["always-show"]).items():
        monkeypatch.setattr(shell_settings, name.lower(), value)
    dock = Dock(monitor_id=0)
    run_pending()
    try:
        assert dock.always_show
        dock.force_occlusion()
        dock.check_config_change()
        assert not dock.always_show
        dock.check_hide()
        assert not dock.dock_revealer.get_reveal_child()
        dock.restore_from_occlusion()
        assert dock.always_show
    finally:
        Dock._instances.remove(dock)
        dock.destroy()
        run_pending()
