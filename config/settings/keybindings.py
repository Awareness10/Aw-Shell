from typing import List, Tuple

import gi
gi.require_version("Gtk", "3.0")
from fabric.widgets.box import Box
from fabric.widgets.entry import Entry
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gtk

from config.data import APP_NAME_CAP
from config.settings_utils import get_bind_var


KEYBIND_DEFINITIONS: List[Tuple[str, str, str]] = [
    (f"Reload {APP_NAME_CAP}", "prefix_restart", "suffix_restart"),
    ("Message", "prefix_axmsg", "suffix_axmsg"),
    ("Dashboard", "prefix_dash", "suffix_dash"),
    ("Bluetooth", "prefix_bluetooth", "suffix_bluetooth"),
    ("Pins", "prefix_pins", "suffix_pins"),
    ("Kanban", "prefix_kanban", "suffix_kanban"),
    ("App Launcher", "prefix_launcher", "suffix_launcher"),
    ("Tmux", "prefix_tmux", "suffix_tmux"),
    ("Clipboard History", "prefix_cliphist", "suffix_cliphist"),
    ("Toolbox", "prefix_toolbox", "suffix_toolbox"),
    ("Overview", "prefix_overview", "suffix_overview"),
    ("Wallpapers", "prefix_wallpapers", "suffix_wallpapers"),
    ("Random Wallpaper", "prefix_randwall", "suffix_randwall"),
    ("Audio Mixer", "prefix_mixer", "suffix_mixer"),
    ("Emoji Picker", "prefix_emoji", "suffix_emoji"),
    ("Power Menu", "prefix_power", "suffix_power"),
    ("Toggle Caffeine", "prefix_caffeine", "suffix_caffeine"),
    ("Toggle Bar", "prefix_toggle", "suffix_toggle"),
    ("Reload CSS", "prefix_css", "suffix_css"),
    ("Restart with inspector", "prefix_restart_inspector", "suffix_restart_inspector"),
]


def build_keybindings_tab() -> Tuple[ScrolledWindow, List[Tuple[str, str, Entry, Entry]]]:
    scrolled_window = ScrolledWindow(
        h_scrollbar_policy="never",
        v_scrollbar_policy="automatic",
        h_expand=True,
        v_expand=True,
        propagate_width=False,
        propagate_height=False,
    )

    main_vbox = Box(orientation="v", spacing=10, style="margin: 15px;")
    scrolled_window.add(main_vbox)

    keybind_grid = Gtk.Grid()
    keybind_grid.set_column_spacing(10)
    keybind_grid.set_row_spacing(8)
    keybind_grid.set_margin_start(5)
    keybind_grid.set_margin_end(5)
    keybind_grid.set_margin_top(5)
    keybind_grid.set_margin_bottom(5)

    headers = [
        (Label(markup="<b>Action</b>", h_align="start", style="margin-bottom: 5px;"), 0),
        (Label(markup="<b>Modifier</b>", h_align="start", style="margin-bottom: 5px;"), 1),
        (Label(label="+", h_align="center", style="margin-bottom: 5px;"), 2),
        (Label(markup="<b>Key</b>", h_align="start", style="margin-bottom: 5px;"), 3),
    ]
    for header, col in headers:
        keybind_grid.attach(header, col, 0, 1, 1)

    entries: List[Tuple[str, str, Entry, Entry]] = []

    for i, (label_text, prefix_key, suffix_key) in enumerate(KEYBIND_DEFINITIONS):
        row = i + 1
        binding_label = Label(label=label_text, h_align="start")
        keybind_grid.attach(binding_label, 0, row, 1, 1)

        prefix_entry = Entry(text=get_bind_var(prefix_key))
        keybind_grid.attach(prefix_entry, 1, row, 1, 1)

        plus_label = Label(label="+", h_align="center")
        keybind_grid.attach(plus_label, 2, row, 1, 1)

        suffix_entry = Entry(text=get_bind_var(suffix_key))
        keybind_grid.attach(suffix_entry, 3, row, 1, 1)

        entries.append((prefix_key, suffix_key, prefix_entry, suffix_entry))

    main_vbox.add(keybind_grid)
    return scrolled_window, entries
