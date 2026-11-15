"""utils/dock_model.py: which buttons the dock shows. The old Dock.update_dock
logic is copied below as the oracle (with one change: identifiers are tried
in a fixed order, where the old code's set() made it vary between runs)."""

from types import SimpleNamespace

import pytest

import utils.apps as apps
from utils.dock_model import app_entry, group_windows, plan_dock, window_id


def _app(name, display_name=None, window_class=None, executable=None, command_line=None):
    return SimpleNamespace(name=name, display_name=display_name, window_class=window_class,
                           executable=executable, command_line=command_line)


APPS = [
    _app("firefox", "Firefox", "firefox", "/usr/bin/firefox", "/usr/lib/firefox/firefox %u"),
    _app("org.gnome.Nautilus", "Files", "org.gnome.Nautilus", "nautilus", "nautilus --new-window"),
    _app("kitty", "kitty", "kitty", "kitty", "kitty"),
    _app("code", "Visual Studio Code", "code-oss", "/usr/bin/code", "code %F"),
    _app("steam", "Steam", "steam", "/usr/bin/steam", "steam %U"),
]
IDENTIFIERS = apps.build_identifier_map(APPS)


def find_app(item):
    return apps.find_app(item, IDENTIFIERS, APPS)


def find_app_by_key(key):
    return apps.find_app_by_key(key, IDENTIFIERS, APPS)


def _win(address, initial="", cls="", title=""):
    return {"address": address, "initialClass": initial, "class": cls, "title": title}


def _old(pinned, clients):
    """Dock.update_dock before the refactor, minus the widgets."""
    _normalize_window_class = apps.normalize_window_class
    running_windows = {}
    for c in clients:
        window_id = None
        if class_name := c.get("initialClass", "").lower(): window_id = class_name
        elif class_name := c.get("class", "").lower(): window_id = class_name
        elif title := c.get("title", "").lower():
            possible_name = title.split(" - ")[0].strip()
            if possible_name and len(possible_name) > 1: window_id = possible_name
            else: window_id = title
        if not window_id: window_id = "unknown-app"
        running_windows.setdefault(window_id, []).append(c)
        normalized_id = _normalize_window_class(window_id)
        if normalized_id != window_id:
            running_windows.setdefault(normalized_id, []).extend(running_windows[window_id])

    pinned_buttons = []
    used_window_classes = set()
    for app_data_item in pinned:
        app = find_app(app_data_item)
        instances = []
        matched_class = None
        possible_identifiers = []
        if isinstance(app_data_item, dict):
            for key in ["window_class", "executable", "command_line", "name", "display_name"]:
                if key in app_data_item and app_data_item[key]: possible_identifiers.append(app_data_item[key].lower())
        elif isinstance(app_data_item, str): possible_identifiers.append(app_data_item.lower())
        if app:
            if app.window_class: possible_identifiers.append(app.window_class.lower())
            if app.executable: possible_identifiers.append(app.executable.split('/')[-1].lower())
            if app.command_line:
                cmd_parts = app.command_line.split()
                if cmd_parts: possible_identifiers.append(cmd_parts[0].split('/')[-1].lower())
            if app.name: possible_identifiers.append(app.name.lower())
            if app.display_name: possible_identifiers.append(app.display_name.lower())
        possible_identifiers = list(dict.fromkeys(possible_identifiers))  # was list(set(...))
        for identifier in possible_identifiers:
            if identifier in running_windows:
                instances = running_windows[identifier]; matched_class = identifier; break
            normalized = _normalize_window_class(identifier)
            if normalized in running_windows:
                instances = running_windows[normalized]; matched_class = normalized; break
            for window_class_key in running_windows:
                if len(identifier) >= 3 and identifier in window_class_key:
                    instances = running_windows[window_class_key]; matched_class = window_class_key
                    break
            if matched_class: break
        if matched_class:
            used_window_classes.add(matched_class)
            used_window_classes.add(_normalize_window_class(matched_class))
        pinned_buttons.append((app_data_item, instances))

    open_buttons = []
    for class_name, instances in running_windows.items():
        if class_name not in used_window_classes:
            app = IDENTIFIERS.get(class_name)
            if not app:
                app = IDENTIFIERS.get(_normalize_window_class(class_name))
            if not app: app = find_app_by_key(class_name)
            if not app and instances and instances[0].get("title"):
                title = instances[0].get("title", "")
                potential_name = title.split(" - ")[0].strip()
                if len(potential_name) > 2: app = find_app_by_key(potential_name)
            if app:
                identifier = {"name": app.name, "display_name": app.display_name,
                              "window_class": app.window_class, "executable": app.executable,
                              "command_line": app.command_line}
            else: identifier = class_name
            open_buttons.append((identifier, instances))
    return pinned_buttons, open_buttons


FIREFOX = app_entry(APPS[0])
SCENARIOS = {
    "nothing": ([], []),
    "pinned, nothing running": ([FIREFOX, "kitty"], []),
    "pinned and running": ([FIREFOX], [_win("0x1", "firefox"), _win("0x2", "firefox")]),
    "running, not pinned": ([], [_win("0x1", "kitty"), _win("0x2", "steam")]),
    "pinned by old string id": (["org.gnome.Nautilus"], [_win("0x1", "org.gnome.Nautilus")]),
    "class differs from name": ([app_entry(APPS[3])], [_win("0x1", "code-oss")]),
    "suffix normalized": ([], [_win("0x1", "foo.bin"), _win("0x2", "foo")]),
    "pinned suffix match": (["foo"], [_win("0x1", "foo-gtk")]),
    "substring match": (["stea"], [_win("0x1", "steamwebhelper")]),
    "no class: title": ([], [_win("0x1", title="Firefox - Some Page"), _win("0x2", title="x")]),
    "unknown app": ([], [_win("0x1")]),
    "unknown pinned app": ([{"name": "ghost"}], [_win("0x1", "kitty")]),
    "mixed": ([FIREFOX, "kitty", {"name": "ghost"}],
              [_win("0x1", "kitty"), _win("0x2", "Steam"), _win("0x3", "firefox"),
               _win("0x4", cls="Code-oss")]),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_matches_the_old_logic(name):
    pinned, clients = SCENARIOS[name]
    assert plan_dock(pinned, clients, find_app, find_app_by_key, IDENTIFIERS) == \
        _old(pinned, clients)


def test_window_id_prefers_initial_class_then_class_then_title():
    assert window_id(_win("0x1", "Foo", "Bar", "t")) == "foo"
    assert window_id(_win("0x1", "", "Bar", "t")) == "bar"
    assert window_id(_win("0x1", title="Editor - file.txt")) == "editor"
    assert window_id(_win("0x1", title="x - y")) == "x - y"  # one-letter name: whole title
    assert window_id(_win("0x1")) == "unknown-app"


def test_group_windows_files_suffixed_classes_under_both_keys():
    a, b = _win("0x1", "foo.bin"), _win("0x2", "foo")
    assert group_windows([a, b]) == {"foo.bin": [a], "foo": [a, b]}
