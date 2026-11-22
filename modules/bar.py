import json
import os

from fabric.hyprland.service import HyprlandEvent
from fabric.hyprland.widgets import HyprlandLanguage as Language
from fabric.hyprland.widgets import WorkspaceButton, get_hyprland_connection
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.datetime import DateTime
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from gi.repository import Gdk, GLib, Gtk

import modules.icons as icons
from config.paths import CONFIG_FILE
from config.settings_constants import APP_NAME_CAP
from config.shell_settings import settings
from modules.controls import ControlSmall
from modules.dock import Dock
from modules.metrics import Battery, MetricsSmall, NetworkApplet
from modules.recording_indicator import RecordingIndicator
from modules.systemprofiles import Systemprofiles
from modules.systemtray import SystemTray
from modules.weather import Weather
from services import hyprland
from utils.bar_layout import bar_layout
from widgets.hyprland import HyprlandWorkspaces as Workspaces
from widgets.wayland import WaylandWindow as Window

RUNES = ["ᚠ", "ᚢ", "ᚦ", "ᚯ", "ᚱ", "ᚴ", "ᚼ", "ᚾ", "ᛁ", "ᛅ"]

# Tooltips
tooltip_apps = f"""<b><u>Launcher</u></b>
<b>• Apps:</b> Type to search.

<b>• Calculator [Prefix "="]:</b> Solve a math expression.
  e.g. "=2+2"

<b>• Converter [Prefix ";"]:</b> Convert between units.
  e.g. ";100 USD to EUR", ";10 km to miles"

<b>• Special Commands [Prefix ":"]:</b>
  :update - Open {APP_NAME_CAP}'s updater.
  :d - Open Dashboard.
  :w - Open Wallpapers."""

tooltip_power = """<b>Power Menu</b>"""
tooltip_tools = """<b>Toolbox</b>"""
tooltip_overview = """<b>Overview</b>"""


class Bar(Window):
    # Components the settings can hide (config key: bar_<name>_visible)
    COMPONENTS = (
        "button_apps", "systray", "control", "network", "button_tools",
        "button_overview", "ws_container", "weather", "battery", "metrics",
        "language", "date_time", "button_power", "sysprofiles",
    )

    def __init__(self, monitor_id: int = 0, **kwargs):
        self.monitor_id = monitor_id

        super().__init__(
            name="bar",
            layer="top",
            exclusivity="auto",
            visible=True,
            all_visible=True,
            monitor=monitor_id,
        )

        self.layout = bar_layout(
            settings.bar_position, settings.centered_bar, settings.bar_theme, settings.panel_theme
        )
        self.anchor_var = self.layout.anchor
        self.margin_var = self.layout.margin
        self.set_anchor(self.anchor_var)
        self.set_margin(self.margin_var)

        self.notch = kwargs.get("notch", None)
        self.component_visibility = settings.bar_components_visibility

        self.dock_instance = None
        self.integrated_dock_widget = None

        self._build_widgets()
        self.apply_component_props()
        self._build_revealers()
        self._build_layout()
        self._apply_theme()

        self.systray._update_visibility()
        self.runic_numbers()

    def _workspaces(self, name, spacing, label_for, style_classes=None):
        # Workspaces 1-10 on every monitor (shared workspace model); Hyprland
        # decides which is active where
        return Workspaces(
            name=name,
            invert_scroll=True,
            empty_scroll=True,
            v_align="fill",
            orientation="v" if self.layout.vertical else "h",
            spacing=spacing,
            buttons=[
                WorkspaceButton(
                    h_expand=False,
                    v_expand=False,
                    h_align="center",
                    v_align="center",
                    id=i,
                    label=label_for(i),
                    style_classes=style_classes,
                )
                for i in range(1, 11)
            ],
            buttons_factory=(
                None
                if settings.bar_hide_special_workspace
                else Workspaces.default_buttons_factory
            ),
        )

    def _bar_button(self, tooltip, icon, action):
        button = Button(
            name="button-bar",
            tooltip_markup=tooltip,
            on_clicked=lambda *_: action(),
            child=Label(name="button-bar-label", markup=icon),
        )
        button.connect("enter_notify_event", self.on_button_enter)
        button.connect("leave_notify_event", self.on_button_leave)
        return button

    def _build_widgets(self):
        vertical = self.layout.vertical
        runes = settings.bar_workspace_use_runes
        self.workspaces = self._workspaces(
            "workspaces", 8, lambda i: None, ["vertical"] if vertical else None
        )
        self.workspaces_num = self._workspaces(
            "workspaces-num",
            4 if runes else 0,
            lambda i: RUNES[i - 1] if runes and 0 <= (i - 1) < len(RUNES) else str(i),
        )
        self.ws_container = Box(
            name="workspaces-container",
            children=(
                self.workspaces_num if settings.bar_workspace_show_number else self.workspaces
            ),
        )

        self.button_tools = self._bar_button(tooltip_tools, icons.toolbox, self.tools_menu)
        self.connection = get_hyprland_connection()

        self.systray = SystemTray()
        self.recording = RecordingIndicator()
        self.weather = Weather()
        self.sysprofiles = Systemprofiles()
        self.network = NetworkApplet()

        self.lang_label = Label(name="lang-label")
        self.language = Button(
            name="language", h_align="center", v_align="center", child=self.lang_label
        )
        self.on_language_switch()
        self.connection.connect("event::activelayout", self.on_language_switch)

        if settings.datetime_12h_format:
            time_format = "%I\n%M\n%p" if vertical else "%I:%M %p"
        else:
            time_format = "%H\n%M" if vertical else "%H:%M"
        self.date_time = DateTime(
            name="date-time",
            formatters=[time_format],
            h_align="fill" if vertical else "center",
            v_align="center",
            h_expand=True,
            v_expand=True,
            style_classes=["vertical"] if vertical else [],
        )

        self.button_apps = self._bar_button(tooltip_apps, icons.apps, self.search_apps)
        self.button_power = self._bar_button(tooltip_power, icons.shutdown, self.power_menu)
        self.button_overview = self._bar_button(
            tooltip_overview, icons.windows, self.overview
        )

        self.control = ControlSmall()
        self.metrics = MetricsSmall()
        self.battery = Battery()

    def _side_revealer(self, children, transition):
        revealer = Revealer(
            name="bar-revealer",
            transition_type=transition,
            child_revealed=True,
            child=Box(
                name="bar-revealer-box",
                orientation="h",
                spacing=4,
                children=None if self.layout.vertical else children,
            ),
        )
        return revealer, Box(name="boxed-revealer", children=[revealer])

    def _build_revealers(self):
        """Widgets beside the notch, hidden while it's open (horizontal bars)."""
        self.rev_right = [self.metrics, self.control]
        self.revealer_right, self.boxed_revealer_right = self._side_revealer(
            self.rev_right, "slide-left"
        )
        self.rev_left = [self.weather, self.sysprofiles, self.network]
        self.revealer_left, self.boxed_revealer_left = self._side_revealer(
            self.rev_left, "slide-right"
        )

    def _build_layout(self):
        vertical, centered = self.layout.vertical, self.layout.centered
        self.h_start_children = [
            self.button_apps, self.ws_container, self.button_overview,
            self.boxed_revealer_left,
        ]
        self.h_end_children = [
            self.boxed_revealer_right, self.battery, self.systray, self.recording,
            self.button_tools, self.language, self.date_time, self.button_power,
        ]
        self.v_start_children = [
            self.button_apps, self.systray, self.control, self.sysprofiles,
            self.network, self.recording, self.button_tools,
        ]
        self.v_center_children = [self.button_overview, self.ws_container, self.weather]
        self.v_end_children = [
            self.battery, self.metrics, self.language, self.date_time, self.button_power,
        ]
        self.v_all_children = [
            *self.v_start_children, *self.v_center_children, *self.v_end_children
        ]

        # A bottom bar (or a top/bottom panel layout) carries the dock
        if self.layout.embed_dock:
            self.dock_instance = Dock(integrated_mode=True)
            self.integrated_dock_widget = self.dock_instance.wrapper

        center = None
        if self.integrated_dock_widget is not None:
            center = self.integrated_dock_widget
        elif vertical:
            center = Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=4,
                children=self.v_all_children if centered else self.v_center_children,
            )

        orientation = Gtk.Orientation.VERTICAL if vertical else Gtk.Orientation.HORIZONTAL

        def side(name, children):
            if centered:
                return None
            return Box(name=name, spacing=4, orientation=orientation, children=children)

        self.bar_inner = CenterBox(
            name="bar-inner",
            orientation=orientation,
            h_align="fill",
            v_align="fill",
            start_children=side(
                "start-container",
                self.v_start_children if vertical else self.h_start_children,
            ),
            center_children=center,
            end_children=side(
                "end-container", self.v_end_children if vertical else self.h_end_children
            ),
        )
        self.children = self.bar_inner
        self.hidden = False

    def _apply_theme(self):
        self.themed_children = [
            self.button_apps, self.button_overview, self.button_power,
            self.button_tools, self.language, self.date_time, self.ws_container,
            self.weather, self.network, self.battery, self.metrics, self.systray,
            self.control, self.recording,
        ]
        if self.integrated_dock_widget:
            self.themed_children.append(self.integrated_dock_widget)

        self.style = self.layout.style
        self.bar_inner.add_style_class(self.style)
        if self.integrated_dock_widget:
            for theme_class in ("pills", "dense", "edge"):
                self.integrated_dock_widget.remove_style_class(theme_class)
            self.integrated_dock_widget.add_style_class(self.style)

        if self.layout.invert:
            for child in self.themed_children:
                if hasattr(child, "add_style_class"):
                    child.add_style_class("invert")

        self.bar_inner.add_style_class(self.layout.position_class)
        if self.layout.vertical:
            self.bar_inner.add_style_class("vertical")

    def _components(self) -> dict:
        return {name: getattr(self, name) for name in self.COMPONENTS}

    def apply_component_props(self):
        for name, widget in self._components().items():
            if name in self.component_visibility:
                widget.set_visible(self.component_visibility[name])

    def toggle_component_visibility(self, component_name):
        if component_name not in self.COMPONENTS or \
                component_name not in self.component_visibility:
            return None
        visible = not self.component_visibility[component_name]
        self.component_visibility[component_name] = visible
        getattr(self, component_name).set_visible(visible)

        config_file = CONFIG_FILE
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                config[f"bar_{component_name}_visible"] = visible
                with open(config_file, "w") as f:
                    json.dump(config, f, indent=4)
            except Exception as e:
                print(f"Error updating config file: {e}")
        return visible

    def on_button_enter(self, widget, event):
        window = widget.get_window()
        if window:
            window.set_cursor(Gdk.Cursor.new_from_name(widget.get_display(), "hand2"))

    def on_button_leave(self, widget, event):
        window = widget.get_window()
        if window:
            window.set_cursor(None)

    def search_apps(self):
        if self.notch:
            self.notch.open_notch("launcher")

    def overview(self):
        if self.notch:
            self.notch.open_notch("overview")

    def power_menu(self):
        if self.notch:
            self.notch.open_notch("power")

    def tools_menu(self):
        if self.notch:
            self.notch.open_notch("tools")

    def on_language_switch(self, _=None, event: HyprlandEvent = None):
        try:
            lang_data = (
                event.data[1]
                if event and event.data and len(event.data) > 1
                else Language().get_label()
            )
        except json.JSONDecodeError:
            lang_data = "UNK"  # Fallback to default language label
        self.language.set_tooltip_text(lang_data)
        if not settings.vertical:
            self.lang_label.set_label(lang_data[:3].upper())
        else:
            self.lang_label.add_style_class("icon")
            self.lang_label.set_markup(icons.keyboard)

    def toggle_hidden(self):
        self.hidden = not self.hidden
        if self.hidden:
            self.bar_inner.add_style_class("hidden")
        else:
            self.bar_inner.remove_style_class("hidden")
            # Ensure notch is above bar when bar is shown
            if self.notch:
                # Focus the notch window to bring it to front
                GLib.idle_add(lambda: hyprland.dispatch('hl.dsp.focus({ window = "class:notch" })') if self.notch else None)

    def runic_numbers(self):
        if settings.bar_workspace_use_runes:
            self.workspaces_num.add_style_class("runic")
        else:
            self.workspaces_num.remove_style_class("runic")
