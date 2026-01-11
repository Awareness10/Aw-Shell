import os
from typing import Dict, Any

import gi
gi.require_version("Gtk", "3.0")
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.image import Image as FabricImage
from fabric.widgets.label import Label
from fabric.widgets.scale import Scale
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import GdkPixbuf, Gtk

from config.settings_utils import get_bind_var


COMPONENT_DISPLAY_NAMES = {
    "button_apps": "App Launcher Button",
    "systray": "System Tray",
    "control": "Control Panel",
    "network": "Network Applet",
    "button_tools": "Toolbox Button",
    "sysprofiles": "Powerprofiles Switcher",
    "button_overview": "Overview Button",
    "ws_container": "Workspaces",
    "weather": "Weather Widget",
    "battery": "Battery Indicator",
    "metrics": "System Metrics",
    "language": "Language Indicator",
    "date_time": "Date & Time",
    "button_power": "Power Button",
}

POSITIONS = ["Top", "Bottom", "Left", "Right"]
THEMES = ["Pills", "Dense", "Edge"]
PANEL_THEMES = ["Notch", "Panel"]
PANEL_POSITIONS = ["Start", "Center", "End"]
NOTIFICATION_POSITIONS = ["Top", "Bottom"]


class AppearanceWidgets:
    __slots__ = (
        'wall_dir_chooser', 'face_image', 'face_status_label', 'selected_face_icon',
        'datetime_12h_switch', 'position_combo', 'centered_switch', 'dock_switch',
        'dock_hover_switch', 'dock_size_scale', 'ws_num_switch', 'ws_chinese_switch',
        'special_ws_switch', 'bar_theme_combo', 'dock_theme_combo', 'panel_theme_combo',
        'panel_position_combo', 'notification_pos_combo', 'component_switches', 'corners_switch',
    )

    def __init__(self):
        self.selected_face_icon = None
        self.component_switches: Dict[str, Gtk.Switch] = {}


def build_appearance_tab(widgets: AppearanceWidgets, on_select_face_icon_callback) -> ScrolledWindow:
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

    _build_wallpapers_section(vbox, widgets, on_select_face_icon_callback)
    _add_separator(vbox)
    _build_datetime_section(vbox, widgets)
    _build_layout_section(vbox, widgets)
    _add_separator(vbox)
    _build_components_section(vbox, widgets)

    return scrolled_window


def _add_separator(vbox: Box) -> None:
    separator = Box(
        style="min-height: 1px; background-color: alpha(@fg_color, 0.2); margin: 5px 0px;",
        h_expand=True,
    )
    vbox.add(separator)


def _build_wallpapers_section(vbox: Box, widgets: AppearanceWidgets, on_select_face_icon_callback) -> None:
    top_grid = Gtk.Grid()
    top_grid.set_column_spacing(20)
    top_grid.set_row_spacing(5)
    top_grid.set_margin_bottom(10)
    vbox.add(top_grid)

    wall_header = Label(markup="<b>Wallpapers</b>", h_align="start")
    top_grid.attach(wall_header, 0, 0, 1, 1)

    wall_label = Label(label="Directory:", h_align="start", v_align="center")
    top_grid.attach(wall_label, 0, 1, 1, 1)

    chooser_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    chooser_container.set_halign(Gtk.Align.START)
    chooser_container.set_valign(Gtk.Align.CENTER)

    widgets.wall_dir_chooser = Gtk.FileChooserButton(
        title="Select a folder", action=Gtk.FileChooserAction.SELECT_FOLDER
    )
    widgets.wall_dir_chooser.set_tooltip_text("Select the directory containing your wallpaper images")
    widgets.wall_dir_chooser.set_filename(get_bind_var("wallpapers_dir"))
    widgets.wall_dir_chooser.set_size_request(180, -1)
    chooser_container.add(widgets.wall_dir_chooser)
    top_grid.attach(chooser_container, 1, 1, 1, 1)

    face_header = Label(markup="<b>Profile Icon</b>", h_align="start")
    top_grid.attach(face_header, 2, 0, 2, 1)

    current_face = os.path.expanduser("~/.face.icon")
    face_image_container = Box(style_classes=["image-frame"], h_align="center", v_align="center")
    widgets.face_image = FabricImage(size=64)

    try:
        if os.path.exists(current_face):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(current_face, 64, 64)
            widgets.face_image.set_from_pixbuf(pixbuf)
        else:
            widgets.face_image.set_from_icon_name("user-info", Gtk.IconSize.DIALOG)
    except Exception as e:
        print(f"Error loading face icon: {e}")
        widgets.face_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

    face_image_container.add(widgets.face_image)
    top_grid.attach(face_image_container, 2, 1, 1, 1)

    browse_btn_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    browse_btn_container.set_halign(Gtk.Align.START)
    browse_btn_container.set_valign(Gtk.Align.CENTER)

    face_btn = Button(
        label="Browse...",
        tooltip_text="Select a square image for your profile icon",
        on_clicked=on_select_face_icon_callback,
    )
    browse_btn_container.add(face_btn)
    top_grid.attach(browse_btn_container, 3, 1, 1, 1)

    widgets.face_status_label = Label(label="", h_align="start")
    top_grid.attach(widgets.face_status_label, 2, 2, 2, 1)


def _build_datetime_section(vbox: Box, widgets: AppearanceWidgets) -> None:
    datetime_format_header = Label(markup="<b>Date & Time Format</b>", h_align="start")
    vbox.add(datetime_format_header)

    datetime_grid = Gtk.Grid()
    datetime_grid.set_column_spacing(20)
    datetime_grid.set_row_spacing(10)
    datetime_grid.set_margin_start(10)
    datetime_grid.set_margin_top(5)
    datetime_grid.set_margin_bottom(10)
    vbox.add(datetime_grid)

    datetime_12h_label = Label(label="Use 12-Hour Clock", h_align="start", v_align="center")
    datetime_grid.attach(datetime_12h_label, 0, 0, 1, 1)

    datetime_12h_switch_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.datetime_12h_switch = Gtk.Switch(active=get_bind_var("datetime_12h_format"))
    datetime_12h_switch_container.add(widgets.datetime_12h_switch)
    datetime_grid.attach(datetime_12h_switch_container, 1, 0, 1, 1)


def _build_layout_section(vbox: Box, widgets: AppearanceWidgets) -> None:
    layout_header = Label(markup="<b>Layout Options</b>", h_align="start")
    vbox.add(layout_header)

    layout_grid = Gtk.Grid()
    layout_grid.set_column_spacing(20)
    layout_grid.set_row_spacing(10)
    layout_grid.set_margin_start(10)
    layout_grid.set_margin_top(5)
    vbox.add(layout_grid)

    _add_position_row(layout_grid, widgets, 0)
    _add_dock_rows(layout_grid, widgets, 1, 2)
    _add_workspace_rows(layout_grid, widgets, 3, 4)
    _add_theme_rows(layout_grid, widgets, 5, 6, 7)
    _add_notification_row(layout_grid, widgets, 8)


def _add_position_row(grid: Gtk.Grid, widgets: AppearanceWidgets, row: int) -> None:
    position_label = Label(label="Bar Position", h_align="start", v_align="center")
    grid.attach(position_label, 0, row, 1, 1)

    position_combo_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.position_combo = Gtk.ComboBoxText()
    widgets.position_combo.set_tooltip_text("Select the position of the bar")

    for pos in POSITIONS:
        widgets.position_combo.append_text(pos)

    current_position = get_bind_var("bar_position")
    try:
        widgets.position_combo.set_active(POSITIONS.index(current_position))
    except ValueError:
        widgets.position_combo.set_active(0)

    position_combo_container.add(widgets.position_combo)
    grid.attach(position_combo_container, 1, row, 1, 1)

    centered_label = Label(label="Centered Bar (Left/Right Only)", h_align="start", v_align="center")
    grid.attach(centered_label, 2, row, 1, 1)

    centered_switch_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.centered_switch = Gtk.Switch(
        active=get_bind_var("centered_bar"),
        sensitive=get_bind_var("bar_position") in ["Left", "Right"],
    )
    centered_switch_container.add(widgets.centered_switch)
    grid.attach(centered_switch_container, 3, row, 1, 1)


def _add_dock_rows(grid: Gtk.Grid, widgets: AppearanceWidgets, row1: int, row2: int) -> None:
    dock_label = Label(label="Show Dock", h_align="start", v_align="center")
    grid.attach(dock_label, 0, row1, 1, 1)

    dock_switch_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.dock_switch = Gtk.Switch(active=get_bind_var("dock_enabled"))
    dock_switch_container.add(widgets.dock_switch)
    grid.attach(dock_switch_container, 1, row1, 1, 1)

    dock_hover_label = Label(label="Always Show Dock", h_align="start", v_align="center")
    grid.attach(dock_hover_label, 2, row1, 1, 1)

    dock_hover_switch_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.dock_hover_switch = Gtk.Switch(
        active=get_bind_var("dock_always_show"),
        sensitive=widgets.dock_switch.get_active(),
    )
    dock_hover_switch_container.add(widgets.dock_hover_switch)
    grid.attach(dock_hover_switch_container, 3, row1, 1, 1)

    dock_size_label = Label(label="Dock Icon Size", h_align="start", v_align="center")
    grid.attach(dock_size_label, 0, row2, 1, 1)

    widgets.dock_size_scale = Scale(
        min_value=16,
        max_value=48,
        value=get_bind_var("dock_icon_size"),
        increments=(2, 4),
        draw_value=True,
        value_position="right",
        digits=0,
        h_expand=True,
    )
    grid.attach(widgets.dock_size_scale, 1, row2, 3, 1)


def _add_workspace_rows(grid: Gtk.Grid, widgets: AppearanceWidgets, row1: int, row2: int) -> None:
    ws_num_label = Label(label="Show Workspace Numbers", h_align="start", v_align="center")
    grid.attach(ws_num_label, 0, row1, 1, 1)

    ws_num_switch_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.ws_num_switch = Gtk.Switch(active=get_bind_var("bar_workspace_show_number"))
    ws_num_switch_container.add(widgets.ws_num_switch)
    grid.attach(ws_num_switch_container, 1, row1, 1, 1)

    ws_chinese_label = Label(label="Use Chinese Numerals", h_align="start", v_align="center")
    grid.attach(ws_chinese_label, 2, row1, 1, 1)

    ws_chinese_switch_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.ws_chinese_switch = Gtk.Switch(
        active=get_bind_var("bar_workspace_use_chinese_numerals"),
        sensitive=widgets.ws_num_switch.get_active(),
    )
    ws_chinese_switch_container.add(widgets.ws_chinese_switch)
    grid.attach(ws_chinese_switch_container, 3, row1, 1, 1)

    special_ws_label = Label(label="Hide Special Workspace", h_align="start", v_align="center")
    grid.attach(special_ws_label, 0, row2, 1, 1)

    special_ws_switch_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.special_ws_switch = Gtk.Switch(active=get_bind_var("bar_hide_special_workspace"))
    special_ws_switch_container.add(widgets.special_ws_switch)
    grid.attach(special_ws_switch_container, 1, row2, 1, 1)


def _add_theme_rows(grid: Gtk.Grid, widgets: AppearanceWidgets, row1: int, row2: int, row3: int) -> None:
    bar_theme_label = Label(label="Bar Theme", h_align="start", v_align="center")
    grid.attach(bar_theme_label, 0, row1, 1, 1)

    bar_theme_combo_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.bar_theme_combo = Gtk.ComboBoxText()
    widgets.bar_theme_combo.set_tooltip_text("Select the visual theme for the bar")

    for theme in THEMES:
        widgets.bar_theme_combo.append_text(theme)

    current_theme = get_bind_var("bar_theme")
    try:
        widgets.bar_theme_combo.set_active(THEMES.index(current_theme))
    except ValueError:
        widgets.bar_theme_combo.set_active(0)

    bar_theme_combo_container.add(widgets.bar_theme_combo)
    grid.attach(bar_theme_combo_container, 1, row1, 3, 1)

    dock_theme_label = Label(label="Dock Theme", h_align="start", v_align="center")
    grid.attach(dock_theme_label, 0, row2, 1, 1)

    dock_theme_combo_container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.dock_theme_combo = Gtk.ComboBoxText()
    widgets.dock_theme_combo.set_tooltip_text("Select the visual theme for the dock")

    for theme in THEMES:
        widgets.dock_theme_combo.append_text(theme)

    current_dock_theme = get_bind_var("dock_theme")
    try:
        widgets.dock_theme_combo.set_active(THEMES.index(current_dock_theme))
    except ValueError:
        widgets.dock_theme_combo.set_active(0)

    dock_theme_combo_container.add(widgets.dock_theme_combo)
    grid.attach(dock_theme_combo_container, 1, row2, 3, 1)

    panel_theme_label = Label(label="Panel Theme", h_align="start", v_align="center")
    grid.attach(panel_theme_label, 0, row3, 1, 1)

    panel_theme_combo_container = Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.panel_theme_combo = Gtk.ComboBoxText()
    widgets.panel_theme_combo.set_tooltip_text("Select the theme/mode for panels like toolbox, clipboard, etc.")

    for theme in PANEL_THEMES:
        widgets.panel_theme_combo.append_text(theme)

    current_panel_theme = get_bind_var("panel_theme")
    try:
        widgets.panel_theme_combo.set_active(PANEL_THEMES.index(current_panel_theme))
    except ValueError:
        widgets.panel_theme_combo.set_active(0)

    panel_theme_combo_container.add(widgets.panel_theme_combo)
    grid.attach(panel_theme_combo_container, 1, row3, 1, 1)

    panel_position_label = Label(label="Panel Position", h_align="start", v_align="center")
    grid.attach(panel_position_label, 2, row3, 1, 1)

    panel_position_combo_container = Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    widgets.panel_position_combo = Gtk.ComboBoxText()
    widgets.panel_position_combo.set_tooltip_text("Select the position for the 'Panel' theme panels")

    for option in PANEL_POSITIONS:
        widgets.panel_position_combo.append_text(option)

    current_panel_position = get_bind_var("panel_position")
    try:
        widgets.panel_position_combo.set_active(PANEL_POSITIONS.index(current_panel_position))
    except ValueError:
        try:
            widgets.panel_position_combo.set_active(PANEL_POSITIONS.index("Center"))
        except ValueError:
            widgets.panel_position_combo.set_active(0)

    is_panel_theme = widgets.panel_theme_combo.get_active_text() == "Panel"
    widgets.panel_position_combo.set_sensitive(is_panel_theme)

    panel_position_combo_container.add(widgets.panel_position_combo)
    grid.attach(panel_position_combo_container, 3, row3, 1, 1)


def _add_notification_row(grid: Gtk.Grid, widgets: AppearanceWidgets, row: int) -> None:
    notification_pos_label = Label(label="Notification Position", h_align="start", v_align="center")
    grid.attach(notification_pos_label, 0, row, 1, 1)

    notification_pos_combo_container = Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )

    widgets.notification_pos_combo = Gtk.ComboBoxText()
    widgets.notification_pos_combo.set_tooltip_text("Select where notifications appear on the screen.")

    for pos in NOTIFICATION_POSITIONS:
        widgets.notification_pos_combo.append_text(pos)

    current_notif_pos = get_bind_var("notif_pos")
    try:
        widgets.notification_pos_combo.set_active(NOTIFICATION_POSITIONS.index(current_notif_pos))
    except ValueError:
        widgets.notification_pos_combo.set_active(0)

    notification_pos_combo_container.add(widgets.notification_pos_combo)
    grid.attach(notification_pos_combo_container, 1, row, 3, 1)


def _build_components_section(vbox: Box, widgets: AppearanceWidgets) -> None:
    components_header = Label(markup="<b>Modules</b>", h_align="start")
    vbox.add(components_header)

    components_grid = Gtk.Grid()
    components_grid.set_column_spacing(15)
    components_grid.set_row_spacing(8)
    components_grid.set_margin_start(10)
    components_grid.set_margin_top(5)
    vbox.add(components_grid)

    widgets.corners_switch = Gtk.Switch(active=get_bind_var("corners_visible"))
    num_components = len(COMPONENT_DISPLAY_NAMES) + 1
    rows_per_column = (num_components + 1) // 2

    corners_label = Label(label="Rounded Corners", h_align="start", v_align="center")
    components_grid.attach(corners_label, 0, 0, 1, 1)

    switch_container_corners = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        halign=Gtk.Align.START,
        valign=Gtk.Align.CENTER,
    )
    switch_container_corners.add(widgets.corners_switch)
    components_grid.attach(switch_container_corners, 1, 0, 1, 1)

    item_idx = 0
    for name, display in COMPONENT_DISPLAY_NAMES.items():
        if item_idx < (rows_per_column - 1):
            row = item_idx + 1
            col = 0
        else:
            row = item_idx - (rows_per_column - 1)
            col = 2

        component_label = Label(label=display, h_align="start", v_align="center")
        components_grid.attach(component_label, col, row, 1, 1)

        switch_container = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.START,
            valign=Gtk.Align.CENTER,
        )
        component_switch = Gtk.Switch(active=get_bind_var(f"bar_{name}_visible"))
        switch_container.add(component_switch)
        components_grid.attach(switch_container, col + 1, row, 1, 1)

        widgets.component_switches[name] = component_switch
        item_idx += 1
