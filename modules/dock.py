import json

import cairo
from fabric.utils import (
    exec_shell_command_async,
    idle_add,
    remove_handler,
)
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.eventbox import EventBox
from fabric.widgets.image import Image
from fabric.widgets.revealer import Revealer
from gi.repository import Gdk, GLib, Gtk
from loguru import logger

import utils.apps as apps
from config.paths import DOCK_FILE
from config.shell_settings import settings
from modules.corners import MyCorner
from services import hyprland
from utils.dock_layout import dock_hidden, dock_layout
from utils.dock_model import app_entry, plan_dock
from utils.icon_resolver import IconResolver
from widgets.wayland import WaylandWindow as Window


def read_config():
    """Read and return the full configuration from the JSON file, handling missing file."""
    try:
        with open(DOCK_FILE, "r") as file:
            config_data = json.load(file)
            
        if "pinned_apps" in config_data and config_data["pinned_apps"] and isinstance(config_data["pinned_apps"][0], str):
            all_apps = apps.desktop_apps()
            app_map = {app.name: app for app in all_apps if app.name}
            
            old_pinned = config_data["pinned_apps"]
            config_data["pinned_apps"] = []
            
            for app_id in old_pinned:
                app = app_map.get(app_id)
                if app:
                    config_data["pinned_apps"].append(app_entry(app))
                else:
                    config_data["pinned_apps"].append({"name": app_id})
                
    except (FileNotFoundError, json.JSONDecodeError):
        config_data = {"pinned_apps": []}
    return config_data

def createSurfaceFromWidget(widget: Gtk.Widget) -> cairo.ImageSurface:
    alloc = widget.get_allocation()
    surface = cairo.ImageSurface(
        cairo.Format.ARGB32,
        alloc.width,
        alloc.height,
    )
    cr = cairo.Context(surface)
    cr.set_source_rgba(255, 255, 255, 0)
    cr.rectangle(0, 0, alloc.width, alloc.height)
    cr.fill()
    widget.draw(cr)
    return surface

class Dock(Window):
    _instances = []
    
    def __init__(self, monitor_id: int = 0, integrated_mode: bool = False, **kwargs):
        self.monitor_id = monitor_id

        self.integrated_mode = integrated_mode
        self.icon_size = 20 if self.integrated_mode else settings.dock_icon_size
        self.effective_occlusion_size = 36 + self.icon_size
        self.always_show = settings.dock_always_show if not self.integrated_mode else False

        self.layout = dock_layout(integrated_mode, settings.bar_position, settings.dock_theme)
        self.actual_dock_is_horizontal = self.layout.horizontal
        if not self.integrated_mode:
            super().__init__(
                name="dock-window",
                layer="top",
                anchor=self.layout.anchor,
                margin="0px 0px 0px 0px",
                exclusivity="auto" if self.always_show else "none",
                monitor=monitor_id,
                **kwargs,
            )
            Dock._instances.append(self)
            self.set_margin(self.layout.margin)

        self.config = read_config()
        self.conn = hyprland.connection()
        self.icon_resolver = IconResolver()
        self.pinned = self.config.get("pinned_apps", [])
        self.app_map = {}
        self._all_apps = apps.desktop_apps()
        self.app_identifiers = apps.app_identifiers()

        self.hide_id = None
        self._arranger_handler = None
        self._drag_in_progress = False
        self.is_mouse_over_dock_area = False
        self._prevent_occlusion = False
        self._forced_occlusion = False

        orientation = (
            Gtk.Orientation.VERTICAL if self.layout.orientation == "v"
            else Gtk.Orientation.HORIZONTAL
        )
        self.view = Box(name="viewport", spacing=4, orientation=orientation)
        self.wrapper = Box(
            name="dock", children=[self.view], orientation=orientation,
            style_classes=list(self.layout.classes),
        )
        if not self.integrated_mode:
            self._build_window()

        self._set_up_drag(self.view)
        self._connect_hyprland()
        GLib.timeout_add_seconds(2, self.check_config_change)

    def _corner_box(self, name, corner, filler_first, vertical_strip):
        """A dock corner: the rounded piece pushed to one end of a strip."""
        if vertical_strip:
            filler = Box(v_expand=True, v_align="fill")
            align = {"h_align": "start" if name.endswith("left") else "end"}
            orientation = Gtk.Orientation.VERTICAL
        else:
            filler = Box(h_expand=True, h_align="fill")
            align = {"v_align": "start" if name.endswith("top") else "end"}
            orientation = Gtk.Orientation.HORIZONTAL
        children = [filler, MyCorner(corner)] if filler_first else [MyCorner(corner), filler]
        return Box(name=name, orientation=orientation, children=children, **align)

    def _build_window(self):
        """The standalone dock: corners, hover strip and auto-hide revealer."""
        self.dock_eventbox = EventBox()
        self.dock_eventbox.add(self.wrapper)
        self.dock_eventbox.connect("enter-notify-event", self._on_dock_enter)
        self.dock_eventbox.connect("leave-notify-event", self._on_dock_leave)

        self.corner_left = Box()
        self.corner_right = Box()
        self.corner_top = Box()
        self.corner_bottom = Box()
        if self.actual_dock_is_horizontal:
            self.corner_left = self._corner_box("dock-corner-left", "bottom-right", True, True)
            self.corner_right = self._corner_box("dock-corner-right", "bottom-left", True, True)
            self.dock_full = Box(
                name="dock-full", orientation=Gtk.Orientation.HORIZONTAL, h_expand=True,
                h_align="fill", children=[self.corner_left, self.dock_eventbox, self.corner_right]
            )
        else:
            on_right = self.layout.anchor == "right"
            self.corner_top = self._corner_box(
                "dock-corner-top", "bottom-right" if on_right else "bottom-left", on_right, False
            )
            self.corner_bottom = self._corner_box(
                "dock-corner-bottom", "top-right" if on_right else "top-left", on_right, False
            )
            self.dock_full = Box(
                name="dock-full", orientation=Gtk.Orientation.VERTICAL, v_expand=True,
                v_align="fill", children=[self.corner_top, self.dock_eventbox, self.corner_bottom]
            )

        self.dock_revealer = Revealer(
            name="dock-revealer",
            transition_type=self.layout.transition,
            transition_duration=250,
            child_revealed=False,
            child=self.dock_full
        )

        self.hover_activator = EventBox()
        horizontal = self.actual_dock_is_horizontal
        self.hover_activator.set_size_request(-1 if horizontal else 1, 1 if horizontal else -1)
        self.hover_activator.connect("enter-notify-event", self._on_hover_enter)
        self.hover_activator.connect("leave-notify-event", self._on_hover_leave)

        self.main_box = Box(
            orientation=(
                Gtk.Orientation.VERTICAL if self.layout.main_orientation == "v"
                else Gtk.Orientation.HORIZONTAL
            ),
            children=(
                [self.hover_activator, self.dock_revealer] if self.layout.activator_first
                else [self.dock_revealer, self.hover_activator]
            ),
            h_align=self.layout.main_h_align,
        )
        self.add(self.main_box)

        if self.layout.hide_corners:
            for corner in [self.corner_left, self.corner_right, self.corner_top,
                           self.corner_bottom]:
                corner.set_visible(False)

        if dock_hidden(settings.bar_position, settings.panel_theme, settings.dock_enabled):
            self.set_visible(False)

        if self.always_show:
            self.dock_full.add_style_class("occluded")

    def _set_up_drag(self, widget):
        """Buttons (and the view) can be dragged and dropped to reorder."""
        target = [Gtk.TargetEntry.new("text/plain", Gtk.TargetFlags.SAME_APP, 0)]
        widget.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, target, Gdk.DragAction.MOVE)
        widget.drag_dest_set(Gtk.DestDefaults.ALL, target, Gdk.DragAction.MOVE)
        widget.connect("drag-data-get", self.on_drag_data_get)
        widget.connect("drag-data-received", self.on_drag_data_received)
        widget.connect("drag-begin", self.on_drag_begin)
        widget.connect("drag-end", self.on_drag_end)

    def _connect_hyprland(self):
        if self.conn.ready:
            self.update_dock()
            if not self.integrated_mode:
                GLib.timeout_add(500, self.check_occlusion_state)
        else:
            self.conn.connect("event::ready", self.update_dock)
            if not self.integrated_mode:
                self.conn.connect(
                    "event::ready", lambda *args: GLib.timeout_add(250, self.check_occlusion_state)
                )

        # Apps opening and closing change the buttons
        self.conn.connect("event::openwindow", self.update_dock)
        self.conn.connect("event::closewindow", self.update_dock)

        if not self.integrated_mode:
            self.conn.connect("event::workspace", self.check_hide)

    def _normalize_window_class(self, class_name):
        return apps.normalize_window_class(class_name)

    def on_drag_begin(self, widget, drag_context):
        self._drag_in_progress = True
        Gtk.drag_set_icon_surface(drag_context, createSurfaceFromWidget(widget))

    def _pointer_entered(self):
        self.is_mouse_over_dock_area = True
        self._cancel_hide()
        self.dock_revealer.set_reveal_child(True)
        if not self.always_show:
            self.dock_full.remove_style_class("occluded")

    def _pointer_left(self):
        self.is_mouse_over_dock_area = False
        if self._forced_occlusion:
            self.dock_revealer.set_reveal_child(False)
        else:
            self.delay_hide()

    def _cancel_hide(self):
        if self.hide_id:
            GLib.source_remove(self.hide_id)
            self.hide_id = None

    def _on_hover_enter(self, *args):
        if not self.integrated_mode:
            self._pointer_entered()

    def _on_hover_leave(self, *args):
        if not self.integrated_mode:
            self._pointer_left()

    def _on_dock_enter(self, widget, event):
        if not self.integrated_mode:
            self._pointer_entered()
        return True

    def _on_dock_leave(self, widget, event):
        if self.integrated_mode:
            return True
        if event.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._pointer_left()
        if not self.always_show:
            self.dock_full.add_style_class("occluded")
        return True

    def find_app(self, app_identifier):
        return apps.find_app(app_identifier, self.app_identifiers, self._all_apps)

    def find_app_by_key(self, key_value):
        return apps.find_app_by_key(key_value, self.app_identifiers, self._all_apps)

    def update_app_map(self):
        self._all_apps = apps.desktop_apps()
        self.app_map = {app.name: app for app in self._all_apps if app.name}
        self.app_identifiers = apps.app_identifiers()

    def create_button(self, app_identifier, instances):
        desktop_app = self.find_app(app_identifier)
        icon_img = None
        display_name = None
        
        if desktop_app:
            icon_img = apps.icon_pixbuf(desktop_app, self.icon_size) 
            display_name = desktop_app.display_name or desktop_app.name
        
        id_value = app_identifier["name"] if isinstance(app_identifier, dict) else app_identifier
        
        if not icon_img:
            icon_img = self.icon_resolver.get_icon_pixbuf(id_value, self.icon_size) 
        
        if not icon_img:
            icon_img = self.icon_resolver.get_icon_pixbuf("application-x-executable-symbolic", self.icon_size) 
            if not icon_img:
                icon_img = self.icon_resolver.get_icon_pixbuf("image-missing", self.icon_size) 
                
        items = [Image(pixbuf=icon_img)]
        tooltip = display_name or (id_value if isinstance(id_value, str) else "Unknown")
        if not display_name and instances and instances[0].get("title"):
            tooltip = instances[0]["title"]

        button = Button(
            child= Box(name="dock-icon", orientation="v", h_align="center", children=items), 
            on_clicked=lambda *a: self.handle_app(app_identifier, instances, desktop_app),
            tooltip_text=tooltip, name="dock-app-button",
        )
        button.app_identifier = app_identifier
        button.desktop_app = desktop_app
        button.instances = instances
        if instances:
            button.add_style_class("instance")

        self._set_up_drag(button)
        button.connect("enter-notify-event", self._on_child_enter)
        return button

    def handle_app(self, app_identifier, instances, desktop_app=None):
        if not instances:
            if not desktop_app:
                desktop_app = self.find_app(app_identifier)
            if desktop_app:
                launch_success = desktop_app.launch()
                if not launch_success:
                    if desktop_app.command_line:
                        exec_shell_command_async(f"nohup {desktop_app.command_line} &")
                    elif desktop_app.executable:
                        exec_shell_command_async(f"nohup {desktop_app.executable} &")
            else:
                cmd_to_run = None
                if isinstance(app_identifier, dict):
                    if "command_line" in app_identifier and app_identifier["command_line"]:
                        cmd_to_run = app_identifier['command_line']
                    elif "executable" in app_identifier and app_identifier["executable"]:
                        cmd_to_run = app_identifier['executable']
                    elif "name" in app_identifier and app_identifier["name"]:
                        cmd_to_run = app_identifier['name']
                elif isinstance(app_identifier, str):
                    cmd_to_run = app_identifier
                if cmd_to_run:
                    exec_shell_command_async(f"nohup {cmd_to_run} &")
        else:
            focused = self.get_focused()
            idx = next((i for i, inst in enumerate(instances) if inst["address"] == focused), -1)
            next_inst = instances[(idx + 1) % len(instances)]
            self._focus_window(next_inst["address"])

    @staticmethod
    def _focus_window(address):
        hyprland.focus_window(address)

    def _on_child_enter(self, widget, event):
        if self.integrated_mode:
            return False
        self.is_mouse_over_dock_area = True
        self._cancel_hide()
        return False

    def delay_hide(self):
        if self.integrated_mode:
            return
        self._cancel_hide()
        self.hide_id = GLib.timeout_add(250, self.hide_dock_if_not_hovered)

    def _held_open(self) -> bool:
        """The pointer, a drag or a notch request keeps the dock out."""
        return self.is_mouse_over_dock_area or self._drag_in_progress or self._prevent_occlusion

    def hide_dock_if_not_hovered(self):
        if self.integrated_mode:
            return False 
        self.hide_id = None 
        if not self._held_open():
            if not self.always_show:
                self.dock_revealer.set_reveal_child(False)
        return False

    def check_hide(self, *args):
        if self.integrated_mode:
            return 
        if self._held_open():
            return
        self._apply_resting_state()

    def _apply_resting_state(self):
        """Shown (always_show) or tucked away, when nothing holds it open."""
        self._set_shown(self.always_show)

    def _set_shown(self, shown: bool):
        if self.dock_revealer.get_reveal_child() != shown:
            self.dock_revealer.set_reveal_child(shown)
        if shown:
            self.dock_full.remove_style_class("occluded")
        else:
            self.dock_full.add_style_class("occluded")

    def update_dock(self, *args):
        self.update_app_map()
        arranger_handler = getattr(self, "_arranger_handler", None)
        if arranger_handler:
            remove_handler(arranger_handler)

        pinned, running = plan_dock(
            self.pinned, self.get_clients(), self.find_app, self.find_app_by_key,
            self.app_identifiers,
        )
        pinned_buttons = [self.create_button(item, windows) for item, windows in pinned]
        open_buttons = [self.create_button(item, windows) for item, windows in running]

        children = pinned_buttons
        separator_orientation = Gtk.Orientation.VERTICAL if self.view.get_orientation() == Gtk.Orientation.HORIZONTAL else Gtk.Orientation.HORIZONTAL
        if pinned_buttons and open_buttons:
            children += [Box(orientation=separator_orientation, v_expand=False, h_expand=False, h_align="center", v_align="center", name="dock-separator")]
        children += open_buttons

        self.view.children = children
        if not self.integrated_mode:
            idle_add(self._update_size)
        self._drag_in_progress = False
        if not self.integrated_mode:
            self.check_occlusion_state()

    def _update_size(self):
        if self.integrated_mode:
            return False
        width, _ = self.view.get_preferred_width()
        self.set_size_request(width, -1) 
        return False

    def get_clients(self):
        try:
            return hyprland.query("clients")
        except ValueError:
            return []

    def get_focused(self):
        try:
            return hyprland.query("activewindow").get("address", "")
        except ValueError:
            return ""

    def get_workspace(self):
        try:
            return hyprland.query("activeworkspace").get("id", 0)
        except ValueError:
            return 0

    def check_occlusion_state(self):
        if self.integrated_mode:
            return False

        # When forced occlusion is active, only show on hover
        if self._forced_occlusion:
            self._set_shown(self.is_mouse_over_dock_area)
            return True

        if self._held_open():
            if not self.dock_revealer.get_reveal_child():
                self.dock_revealer.set_reveal_child(True)
            if not self.always_show:
                 self.dock_full.remove_style_class("occluded")
            return True

        self._apply_resting_state()
        return True

    def _find_drag_target(self, widget):
        children = self.view.get_children()
        while widget is not None and widget not in children:
            widget = widget.get_parent() if hasattr(widget, "get_parent") else None
        return widget

    def on_drag_data_get(self, widget, drag_context, data_obj, info, time):
        target = self._find_drag_target(widget.get_parent() if isinstance(widget, Box) else widget)
        if target is not None:
            index = self.view.get_children().index(target)
            data_obj.set_text(str(index), -1)

    def on_drag_data_received(self, widget, drag_context, x, y, data_obj, info, time):
        target = self._find_drag_target(widget.get_parent() if isinstance(widget, Box) else widget)
        if target is None:
            return
        try:
            source_index = int(data_obj.get_text())
        except (TypeError, ValueError):
            return

        children = self.view.get_children()
        try:
            target_index = children.index(target)
        except ValueError:
            return

        if source_index != target_index:
            separator_index = -1
            for i, child_item_loop in enumerate(children): 
                if child_item_loop.get_name() == "dock-separator":
                    separator_index = i
                    break
            cross_section_drag = (separator_index != -1 and
                                 ((source_index < separator_index and target_index > separator_index) or
                                  (source_index > separator_index and target_index < separator_index)))
            
            child_item_to_move = children.pop(source_index) 
            children.insert(target_index, child_item_to_move)
            self.view.children = children
            self.update_pinned_apps(skip_update=not cross_section_drag)
            if cross_section_drag:
                GLib.idle_add(self.update_dock)

    def on_drag_end(self, widget, drag_context):
        if not self._drag_in_progress:
            return

        def process_drag_end():
            display = Gdk.Display.get_default()
            _, x, y, _ = display.get_pointer()
            
            # Get the widget's allocation to check if drag ended outside
            alloc = self.view.get_allocation()
            widget_x = alloc.x
            widget_y = alloc.y
            widget_width = alloc.width
            widget_height = alloc.height
            
            # Check if pointer is outside the dock area
            if not (widget_x <= x <= widget_x + widget_width and widget_y <= y <= widget_y + widget_height):
                app_id_dragged = widget.app_identifier
                instances_dragged = widget.instances

                # Remove pinned app
                app_index_dragged = -1
                for i, pinned_app_item in enumerate(self.pinned):
                    if isinstance(app_id_dragged, dict) and isinstance(pinned_app_item, dict):
                        if app_id_dragged.get("name") == pinned_app_item.get("name"):
                            app_index_dragged = i
                            break
                    elif app_id_dragged == pinned_app_item:
                        app_index_dragged = i
                        break
                
                if app_index_dragged >= 0:
                    self.pinned.pop(app_index_dragged)
                    self.config["pinned_apps"] = self.pinned
                    self.update_pinned_apps_file()
                    self.update_dock()
                elif instances_dragged:
                    address = instances_dragged[0].get("address")
                    if address:
                        self._focus_window(address)

            self._drag_in_progress = False
            if not self.integrated_mode:
                self.check_occlusion_state()

        GLib.idle_add(process_drag_end)
    def _reload_config(self):
        """Pick up dock.json if it changed. (Settings only change with a
        restart; re-reading always_show here undid force_occlusion.)"""
        new_config = read_config()
        if new_config.get("pinned_apps", []) != self.config.get("pinned_apps", []):
            self.config = new_config
            self.pinned = self.config.get("pinned_apps", [])
            self.update_app_map()
            self.update_dock()

    def check_config_change(self):
        self._reload_config()
        return True  # keep polling

    def update_pinned_apps_file(self):
        try:
            DOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(DOCK_FILE, "w") as file:
                json.dump(self.config, file, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to write dock config: {e}")
            return False

    def update_pinned_apps(self, skip_update=False):
        pinned_children_data = [] 
        for child_widget in self.view.get_children(): 
            if child_widget.get_name() == "dock-separator":
                break
            if hasattr(child_widget, "app_identifier"):
                if getattr(child_widget, "desktop_app", None):
                    pinned_children_data.append(app_entry(child_widget.desktop_app))
                else:
                    pinned_children_data.append(child_widget.app_identifier)

        self.config["pinned_apps"] = pinned_children_data
        self.pinned = pinned_children_data
        file_updated = self.update_pinned_apps_file()
        if file_updated and not skip_update:
            self.update_dock()

    @staticmethod
    def notify_config_change():
        for dock_instance in Dock._instances: 
             GLib.idle_add(dock_instance.check_config_change_immediate)

    def check_config_change_immediate(self):
        self._reload_config()
        return False  # once

    @staticmethod
    def update_visibility(visible):
        for dock in Dock._instances: 
            dock.set_visible(visible)
            if visible:
                GLib.idle_add(dock.check_occlusion_state)
            else:
                if hasattr(dock, 'dock_revealer') and dock.dock_revealer.get_reveal_child():
                    dock.dock_revealer.set_reveal_child(False)
    
    def force_occlusion(self):
        """Force dock to hide and act as if always_show is False."""
        if self.integrated_mode:
            return
        # Save current always_show state
        self._saved_always_show = self.always_show
        # Set to False to enable hover behavior
        self.always_show = False
        self._forced_occlusion = True
        if not self.is_mouse_over_dock_area:
            self.dock_revealer.set_reveal_child(False)
    
    def restore_from_occlusion(self):
        """Restore dock to its previous always_show state."""
        if self.integrated_mode:
            return
        self._forced_occlusion = False
        # Restore saved always_show state
        if hasattr(self, '_saved_always_show'):
            self.always_show = self._saved_always_show
            delattr(self, '_saved_always_show')
        self.check_occlusion_state()
