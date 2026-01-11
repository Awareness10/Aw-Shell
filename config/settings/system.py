from typing import Dict, List, Callable

import gi
gi.require_version("Gtk", "3.0")
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.entry import Entry
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gtk

from config.settings_utils import get_bind_var


METRIC_NAMES = {"cpu": "CPU", "ram": "RAM", "disk": "Disk", "gpu": "GPU"}


class SystemWidgets:
    __slots__ = (
        'auto_append_switch', 'monitor_checkboxes', 'terminal_entry',
        'lock_switch', 'idle_switch', 'limited_apps_entry', 'ignored_apps_entry',
        'metrics_switches', 'metrics_small_switches', 'disk_entries',
    )

    def __init__(self):
        self.monitor_checkboxes: Dict[str, Gtk.CheckButton] = {}
        self.metrics_switches: Dict[str, Gtk.Switch] = {}
        self.metrics_small_switches: Dict[str, Gtk.Switch] = {}
        self.lock_switch = None
        self.idle_switch = None


def build_system_tab(
    widgets: SystemWidgets,
    show_lock_checkbox: bool,
    show_idle_checkbox: bool,
    add_disk_entry_callback: Callable[[str], None],
) -> ScrolledWindow:
    scrolled_window = ScrolledWindow(
        h_scrollbar_policy="never",
        v_scrollbar_policy="automatic",
        h_expand=True,
        v_expand=True,
        propagate_width=False,
        propagate_height=False,
    )

    vbox = Box(orientation="v", spacing=15, style="margin: 15px;")
    scrolled_window.add(vbox)

    _build_general_section(vbox, widgets)
    _build_monitor_section(vbox, widgets)
    _build_terminal_section(vbox, widgets)
    _build_hypr_integration_section(vbox, widgets, show_lock_checkbox, show_idle_checkbox)
    _build_notification_apps_section(vbox, widgets)
    _build_metrics_section(vbox, widgets)
    _build_disk_section(vbox, widgets, add_disk_entry_callback)

    return scrolled_window


def _build_general_section(vbox: Box, widgets: SystemWidgets) -> None:
    system_grid = Gtk.Grid()
    system_grid.set_column_spacing(20)
    system_grid.set_row_spacing(10)
    system_grid.set_margin_bottom(15)
    vbox.add(system_grid)

    auto_append_label = Label(
        label="Auto-append to hyprland.conf", h_align="start", v_align="center"
    )
    system_grid.attach(auto_append_label, 0, 0, 1, 1)

    auto_append_switch_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.auto_append_switch = Gtk.Switch(
        active=get_bind_var("auto_append_hyprland"),
        tooltip_text="Automatically append Aw-Shell source string to hyprland.conf",
    )
    auto_append_switch_container.add(widgets.auto_append_switch)
    system_grid.attach(auto_append_switch_container, 1, 0, 1, 1)


def _build_monitor_section(vbox: Box, widgets: SystemWidgets) -> None:
    system_grid = Gtk.Grid()
    system_grid.set_column_spacing(20)
    system_grid.set_row_spacing(10)
    vbox.add(system_grid)

    monitor_header = Label(markup="<b>Monitor Selection</b>", h_align="start")
    system_grid.attach(monitor_header, 0, 0, 2, 1)

    monitor_label = Label(
        label="Show Aw-Shell on monitors:", h_align="start", v_align="center"
    )
    system_grid.attach(monitor_label, 0, 1, 1, 1)

    monitor_selection_container = Box(orientation="v", spacing=5, h_align="start")

    try:
        from utils.monitor_manager import get_monitor_manager
        monitor_manager = get_monitor_manager()
        available_monitors = monitor_manager.get_monitors()
    except (ImportError, Exception) as e:
        print(f"Could not get monitor info for settings: {e}")
        available_monitors = [{"id": 0, "name": "default"}]

    current_selection = get_bind_var("selected_monitors")

    for monitor in available_monitors:
        monitor_name = monitor.get("name", f'monitor-{monitor.get("id", 0)}')
        checkbox_container = Box(orientation="h", spacing=5, h_align="start")
        checkbox = Gtk.CheckButton(label=monitor_name)

        is_selected = len(current_selection) == 0 or monitor_name in current_selection
        checkbox.set_active(is_selected)

        checkbox_container.add(checkbox)
        monitor_selection_container.add(checkbox_container)
        widgets.monitor_checkboxes[monitor_name] = checkbox

    hint_label = Label(
        markup="<small>Leave all unchecked to show on all monitors</small>",
        h_align="start",
    )
    monitor_selection_container.add(hint_label)
    system_grid.attach(monitor_selection_container, 1, 1, 1, 1)


def _build_terminal_section(vbox: Box, widgets: SystemWidgets) -> None:
    terminal_grid = Gtk.Grid()
    terminal_grid.set_column_spacing(20)
    terminal_grid.set_row_spacing(10)
    vbox.add(terminal_grid)

    terminal_header = Label(markup="<b>Terminal Settings</b>", h_align="start")
    terminal_grid.attach(terminal_header, 0, 0, 2, 1)

    terminal_label = Label(label="Command:", h_align="start", v_align="center")
    terminal_grid.attach(terminal_label, 0, 1, 1, 1)

    widgets.terminal_entry = Entry(
        text=get_bind_var("terminal_command"),
        tooltip_text="Command used to launch terminal apps (e.g., 'kitty -e')",
        h_expand=True,
    )
    terminal_grid.attach(widgets.terminal_entry, 1, 1, 1, 1)

    hint_label = Label(
        markup="<small>Examples: 'kitty -e', 'alacritty -e', 'foot -e'</small>",
        h_align="start",
    )
    terminal_grid.attach(hint_label, 0, 2, 2, 1)


def _build_hypr_integration_section(
    vbox: Box,
    widgets: SystemWidgets,
    show_lock_checkbox: bool,
    show_idle_checkbox: bool,
) -> None:
    if not show_lock_checkbox and not show_idle_checkbox:
        return

    hypr_grid = Gtk.Grid()
    hypr_grid.set_column_spacing(20)
    hypr_grid.set_row_spacing(10)
    vbox.add(hypr_grid)

    hypr_header = Label(markup="<b>Hyprland Integration</b>", h_align="start")
    hypr_grid.attach(hypr_header, 0, 0, 2, 1)

    row = 1
    if show_lock_checkbox:
        lock_label = Label(
            label="Replace Hyprlock config", h_align="start", v_align="center"
        )
        hypr_grid.attach(lock_label, 0, row, 1, 1)

        lock_switch_container = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
        )
        widgets.lock_switch = Gtk.Switch(
            tooltip_text="Replace Hyprlock configuration with Aw-Shell's custom config"
        )
        lock_switch_container.add(widgets.lock_switch)
        hypr_grid.attach(lock_switch_container, 1, row, 1, 1)
        row += 1

    if show_idle_checkbox:
        idle_label = Label(
            label="Replace Hypridle config", h_align="start", v_align="center"
        )
        hypr_grid.attach(idle_label, 0, row, 1, 1)

        idle_switch_container = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
        )
        widgets.idle_switch = Gtk.Switch(
            tooltip_text="Replace Hypridle configuration with Aw-Shell's custom config"
        )
        idle_switch_container.add(widgets.idle_switch)
        hypr_grid.attach(idle_switch_container, 1, row, 1, 1)
        row += 1

    note_label = Label(
        markup="<small>Existing configs will be backed up</small>",
        h_align="start",
    )
    hypr_grid.attach(note_label, 0, row, 2, 1)


def _build_notification_apps_section(vbox: Box, widgets: SystemWidgets) -> None:
    notifications_header = Label(markup="<b>Notification Settings</b>", h_align="start")
    vbox.add(notifications_header)

    notif_grid = Gtk.Grid()
    notif_grid.set_column_spacing(20)
    notif_grid.set_row_spacing(10)
    notif_grid.set_margin_start(10)
    notif_grid.set_margin_top(5)
    notif_grid.set_margin_bottom(15)
    vbox.add(notif_grid)

    limited_apps_label = Label(
        label="Limited Apps History:", h_align="start", v_align="center"
    )
    notif_grid.attach(limited_apps_label, 0, 0, 1, 1)

    limited_apps_list = get_bind_var("limited_apps_history")
    limited_apps_text = ", ".join(f'"{app}"' for app in limited_apps_list)
    widgets.limited_apps_entry = Entry(
        text=limited_apps_text,
        tooltip_text='Enter app names separated by commas, e.g: "Spotify", "Discord"',
        h_expand=True,
    )
    notif_grid.attach(widgets.limited_apps_entry, 1, 0, 1, 1)

    limited_apps_hint = Label(
        markup='<small>Apps with limited notification history (format: "App1", "App2")</small>',
        h_align="start",
    )
    notif_grid.attach(limited_apps_hint, 0, 1, 2, 1)

    ignored_apps_label = Label(
        label="History Ignored Apps:", h_align="start", v_align="center"
    )
    notif_grid.attach(ignored_apps_label, 0, 2, 1, 1)

    ignored_apps_list = get_bind_var("history_ignored_apps")
    ignored_apps_text = ", ".join(f'"{app}"' for app in ignored_apps_list)
    widgets.ignored_apps_entry = Entry(
        text=ignored_apps_text,
        tooltip_text='Enter app names separated by commas, e.g: "Hyprshot", "Screenshot"',
        h_expand=True,
    )
    notif_grid.attach(widgets.ignored_apps_entry, 1, 2, 1, 1)

    ignored_apps_hint = Label(
        markup='<small>Apps whose notifications are ignored in history (format: "App1", "App2")</small>',
        h_align="start",
    )
    notif_grid.attach(ignored_apps_hint, 0, 3, 2, 1)


def _build_metrics_section(vbox: Box, widgets: SystemWidgets) -> None:
    metrics_header = Label(markup="<b>System Metrics Options</b>", h_align="start")
    vbox.add(metrics_header)

    metrics_grid = Gtk.Grid(
        column_spacing=15, row_spacing=8, margin_start=10, margin_top=5
    )
    vbox.add(metrics_grid)

    metrics_grid.attach(Label(label="Show in Metrics", h_align="start"), 0, 0, 1, 1)

    for i, (key, label_text) in enumerate(METRIC_NAMES.items()):
        switch = Gtk.Switch(active=get_bind_var("metrics_visible").get(key, True))
        widgets.metrics_switches[key] = switch
        metrics_grid.attach(Label(label=label_text, h_align="start"), 0, i + 1, 1, 1)
        metrics_grid.attach(switch, 1, i + 1, 1, 1)

    metrics_grid.attach(Label(label="Show in Small Metrics", h_align="start"), 2, 0, 1, 1)

    for i, (key, label_text) in enumerate(METRIC_NAMES.items()):
        switch = Gtk.Switch(active=get_bind_var("metrics_small_visible").get(key, True))
        widgets.metrics_small_switches[key] = switch
        metrics_grid.attach(Label(label=label_text, h_align="start"), 2, i + 1, 1, 1)
        metrics_grid.attach(switch, 3, i + 1, 1, 1)

    def enforce_minimum_metrics(switch_dict: Dict[str, Gtk.Switch]) -> None:
        enabled_switches = [s for s in switch_dict.values() if s.get_active()]
        can_disable = len(enabled_switches) > 3
        for s in switch_dict.values():
            s.set_sensitive(True if can_disable or not s.get_active() else False)

    def on_metric_toggle(switch, gparam, switch_dict):
        enforce_minimum_metrics(switch_dict)

    for s in widgets.metrics_switches.values():
        s.connect("notify::active", on_metric_toggle, widgets.metrics_switches)
    for s in widgets.metrics_small_switches.values():
        s.connect("notify::active", on_metric_toggle, widgets.metrics_small_switches)

    enforce_minimum_metrics(widgets.metrics_switches)
    enforce_minimum_metrics(widgets.metrics_small_switches)


def _build_disk_section(
    vbox: Box,
    widgets: SystemWidgets,
    add_disk_entry_callback: Callable[[str], None],
) -> None:
    disks_label = Label(
        label="Disk directories for Metrics", h_align="start", v_align="center"
    )
    vbox.add(disks_label)

    widgets.disk_entries = Box(orientation="v", spacing=8, h_align="start")

    for p in get_bind_var("bar_metrics_disks"):
        add_disk_entry_callback(p)

    vbox.add(widgets.disk_entries)

    add_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    add_btn = Button(
        label="Add new disk",
        on_clicked=lambda _: add_disk_entry_callback("/"),
    )
    add_container.add(add_btn)
    vbox.add(add_container)
