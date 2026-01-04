import json
import os
import subprocess
import time
from typing import List, Tuple

import gi
gi.require_version("Gtk", "3.0")
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.entry import Entry
from fabric.widgets.label import Label
from fabric.widgets.stack import Stack
from fabric.widgets.window import Window
from gi.repository import GdkPixbuf, GLib, Gtk
from PIL import Image

from config.data import APP_NAME, APP_NAME_CAP
from config.settings_utils import backup_and_replace, bind_vars, get_bind_var, get_default, start_config

from .about import build_about_tab
from .appearance import AppearanceWidgets, build_appearance_tab, POSITIONS, THEMES, PANEL_THEMES, PANEL_POSITIONS, NOTIFICATION_POSITIONS, COMPONENT_DISPLAY_NAMES
from .keybindings import build_keybindings_tab
from .system import SystemWidgets, build_system_tab, METRIC_NAMES


class HyprConfGUI(Window):
    def __init__(self, show_lock_checkbox: bool, show_idle_checkbox: bool, **kwargs):
        super().__init__(
            title="Aw-Shell Settings",
            name="awshell-settings-window",
            size=(640, 640),
            **kwargs,
        )

        self.set_resizable(False)
        self.show_lock_checkbox = show_lock_checkbox
        self.show_idle_checkbox = show_idle_checkbox

        self.appearance = AppearanceWidgets()
        self.system = SystemWidgets()
        self.entries: List[Tuple[str, str, Entry, Entry]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        root_box = Box(orientation="v", spacing=10, style="margin: 10px;")
        self.add(root_box)

        main_content_box = Box(orientation="h", spacing=6, v_expand=True, h_expand=True)
        root_box.add(main_content_box)

        self.tab_stack = Stack(
            transition_type="slide-up-down",
            transition_duration=250,
            v_expand=True,
            h_expand=True,
        )

        keybindings_tab, self.entries = build_keybindings_tab()
        appearance_tab = build_appearance_tab(self.appearance, self._on_select_face_icon)
        system_tab = build_system_tab(
            self.system,
            self.show_lock_checkbox,
            self.show_idle_checkbox,
            self._add_disk_entry_widget,
        )
        about_tab = build_about_tab()

        self.tab_stack.add_titled(keybindings_tab, "key_bindings", "Key Bindings")
        self.tab_stack.add_titled(appearance_tab, "appearance", "Appearance")
        self.tab_stack.add_titled(system_tab, "system", "System")
        self.tab_stack.add_titled(about_tab, "about", "About")

        tab_switcher = Gtk.StackSwitcher()
        tab_switcher.set_stack(self.tab_stack)
        tab_switcher.set_orientation(Gtk.Orientation.VERTICAL)
        main_content_box.add(tab_switcher)
        main_content_box.add(self.tab_stack)

        button_box = Box(orientation="h", spacing=10, h_align="end")
        reset_btn = Button(label="Reset to Defaults", on_clicked=self._on_reset)
        button_box.add(reset_btn)
        close_btn = Button(label="Close", on_clicked=self._on_close)
        button_box.add(close_btn)
        accept_btn = Button(label="Apply & Reload", on_clicked=self._on_accept)
        button_box.add(accept_btn)
        root_box.add(button_box)

        self._connect_signals()

    def _connect_signals(self) -> None:
        self.appearance.position_combo.connect("changed", self._on_position_changed)
        self.appearance.dock_switch.connect("notify::active", self._on_dock_enabled_changed)
        self.appearance.ws_num_switch.connect("notify::active", self._on_ws_num_changed)
        self.appearance.panel_theme_combo.connect("changed", self._on_panel_theme_changed)
        self.appearance.notification_pos_combo.connect("changed", self._on_notification_position_changed)

    def _on_position_changed(self, combo) -> None:
        position = combo.get_active_text()
        is_vertical = position in ["Left", "Right"]
        self.appearance.centered_switch.set_sensitive(is_vertical)
        if not is_vertical:
            self.appearance.centered_switch.set_active(False)

    def _on_dock_enabled_changed(self, switch, gparam) -> None:
        is_active = switch.get_active()
        self.appearance.dock_hover_switch.set_sensitive(is_active)
        if not is_active:
            self.appearance.dock_hover_switch.set_active(False)

    def _on_ws_num_changed(self, switch, gparam) -> None:
        is_active = switch.get_active()
        self.appearance.ws_chinese_switch.set_sensitive(is_active)
        if not is_active:
            self.appearance.ws_chinese_switch.set_active(False)

    def _on_panel_theme_changed(self, combo) -> None:
        selected_theme = combo.get_active_text()
        self.appearance.panel_position_combo.set_sensitive(selected_theme == "Panel")

    def _on_notification_position_changed(self, combo) -> None:
        selected_text = combo.get_active_text()
        if selected_text:
            bind_vars["notif_pos"] = selected_text

    def _on_select_face_icon(self, widget) -> None:
        dialog = Gtk.FileChooserDialog(
            title="Select Face Icon",
            transient_for=self.get_toplevel(),
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        image_filter = Gtk.FileFilter()
        image_filter.set_name("Image files")
        for mime in ["image/png", "image/jpeg"]:
            image_filter.add_mime_type(mime)
        for pattern in ["*.png", "*.jpg", "*.jpeg"]:
            image_filter.add_pattern(pattern)
        dialog.add_filter(image_filter)

        if dialog.run() == Gtk.ResponseType.OK:
            self.appearance.selected_face_icon = dialog.get_filename()
            self.appearance.face_status_label.label = f"Selected: {os.path.basename(self.appearance.selected_face_icon)}"
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    self.appearance.selected_face_icon, 64, 64
                )
                self.appearance.face_image.set_from_pixbuf(pixbuf)
            except Exception as e:
                print(f"Error loading selected face icon preview: {e}")
                self.appearance.face_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

        dialog.destroy()

    def _add_disk_entry_widget(self, path: str) -> None:
        bar = Box(orientation="h", spacing=10, h_align="start")
        entry = Entry(text=path, h_expand=True)
        bar.add(entry)

        x_btn = Button(label="X")
        x_btn.connect(
            "clicked",
            lambda _, b=bar: self.system.disk_entries.remove(b),
        )
        bar.add(x_btn)

        self.system.disk_entries.add(bar)
        self.system.disk_entries.show_all()

    def _collect_settings(self) -> dict:
        settings = {}

        for prefix_key, suffix_key, prefix_entry, suffix_entry in self.entries:
            settings[prefix_key] = prefix_entry.get_text()
            settings[suffix_key] = suffix_entry.get_text()

        settings["wallpapers_dir"] = self.appearance.wall_dir_chooser.get_filename()
        settings["bar_position"] = self.appearance.position_combo.get_active_text()
        settings["vertical"] = settings["bar_position"] in ["Left", "Right"]
        settings["centered_bar"] = self.appearance.centered_switch.get_active()
        settings["datetime_12h_format"] = self.appearance.datetime_12h_switch.get_active()
        settings["dock_enabled"] = self.appearance.dock_switch.get_active()
        settings["dock_always_show"] = self.appearance.dock_hover_switch.get_active()
        settings["dock_icon_size"] = int(self.appearance.dock_size_scale.value)
        settings["terminal_command"] = self.system.terminal_entry.get_text()
        settings["auto_append_hyprland"] = self.system.auto_append_switch.get_active()
        settings["corners_visible"] = self.appearance.corners_switch.get_active()
        settings["bar_workspace_show_number"] = self.appearance.ws_num_switch.get_active()
        settings["bar_workspace_use_chinese_numerals"] = self.appearance.ws_chinese_switch.get_active()
        settings["bar_hide_special_workspace"] = self.appearance.special_ws_switch.get_active()
        settings["bar_theme"] = self.appearance.bar_theme_combo.get_active_text()
        settings["dock_theme"] = self.appearance.dock_theme_combo.get_active_text()
        settings["panel_theme"] = self.appearance.panel_theme_combo.get_active_text()
        settings["panel_position"] = self.appearance.panel_position_combo.get_active_text()

        selected_notif_pos = self.appearance.notification_pos_combo.get_active_text()
        settings["notif_pos"] = selected_notif_pos if selected_notif_pos else "Top"

        for component_name, switch in self.appearance.component_switches.items():
            settings[f"bar_{component_name}_visible"] = switch.get_active()

        settings["metrics_visible"] = {k: s.get_active() for k, s in self.system.metrics_switches.items()}
        settings["metrics_small_visible"] = {k: s.get_active() for k, s in self.system.metrics_small_switches.items()}

        settings["bar_metrics_disks"] = [
            child.get_children()[0].get_text()
            for child in self.system.disk_entries.get_children()
            if isinstance(child, Gtk.Box) and child.get_children() and isinstance(child.get_children()[0], Entry)
        ]

        settings["limited_apps_history"] = self._parse_app_list(self.system.limited_apps_entry.get_text())
        settings["history_ignored_apps"] = self._parse_app_list(self.system.ignored_apps_entry.get_text())

        selected_monitors = []
        any_checked = False
        for monitor_name, checkbox in self.system.monitor_checkboxes.items():
            if checkbox.get_active():
                selected_monitors.append(monitor_name)
                any_checked = True
        settings["selected_monitors"] = selected_monitors if any_checked else []

        return settings

    def _parse_app_list(self, text: str) -> list:
        if not text.strip():
            return []
        apps = []
        for app in text.split(","):
            app = app.strip()
            if app.startswith('"') and app.endswith('"'):
                app = app[1:-1]
            elif app.startswith("'") and app.endswith("'"):
                app = app[1:-1]
            if app:
                apps.append(app)
        return apps

    def _on_accept(self, widget) -> None:
        current_settings = self._collect_settings()
        selected_icon_path = self.appearance.selected_face_icon
        replace_lock = self.system.lock_switch and self.system.lock_switch.get_active()
        replace_idle = self.system.idle_switch and self.system.idle_switch.get_active()

        if self.appearance.selected_face_icon:
            self.appearance.selected_face_icon = None
            self.appearance.face_status_label.label = ""

        def apply_and_reload_thread(user_data):
            from config import settings_utils
            settings_utils.bind_vars.clear()
            settings_utils.bind_vars.update(current_settings)

            config_json = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/config/config.json")
            os.makedirs(os.path.dirname(config_json), exist_ok=True)
            try:
                with open(config_json, "w") as f:
                    json.dump(settings_utils.bind_vars, f, indent=4)
            except Exception as e:
                print(f"Error saving config.json: {e}")

            if selected_icon_path:
                try:
                    img = Image.open(selected_icon_path)
                    side = min(img.size)
                    left = (img.width - side) // 2
                    top = (img.height - side) // 2
                    cropped_img = img.crop((left, top, left + side, top + side))
                    face_icon_dest = os.path.expanduser("~/.face.icon")
                    cropped_img.save(face_icon_dest, format="PNG")
                    GLib.idle_add(self._update_face_image_widget, face_icon_dest)
                except Exception as e:
                    print(f"Error processing face icon: {e}")

            if replace_lock:
                src = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/config/hypr/hyprlock.conf")
                dest = os.path.expanduser("~/.config/hypr/hyprlock.conf")
                if os.path.exists(src):
                    backup_and_replace(src, dest, "Hyprlock")

            if replace_idle:
                src = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/config/hypr/hypridle.conf")
                dest = os.path.expanduser("~/.config/hypr/hypridle.conf")
                if os.path.exists(src):
                    backup_and_replace(src, dest, "Hypridle")

            hypr_path = os.path.expanduser("~/.config/hypr/hyprland.conf")
            try:
                from config.settings_constants import SOURCE_STRING
                auto_append_enabled = current_settings.get("auto_append_hyprland", True)
                if auto_append_enabled:
                    needs_append = True
                    if os.path.exists(hypr_path):
                        with open(hypr_path, "r") as f:
                            if SOURCE_STRING.strip() in f.read():
                                needs_append = False
                    else:
                        os.makedirs(os.path.dirname(hypr_path), exist_ok=True)

                    if needs_append:
                        with open(hypr_path, "a") as f:
                            f.write("\n" + SOURCE_STRING)
            except Exception as e:
                print(f"Error updating {hypr_path}: {e}")

            start_config()

            main_py = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/main.py")
            try:
                kill_proc = subprocess.Popen(
                    f"killall {APP_NAME}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                kill_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                print(f"Error running killall: {e}")

            try:
                subprocess.Popen(
                    ["uwsm", "app", "--", "python", main_py],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except Exception as e:
                print(f"Error restarting {APP_NAME_CAP}: {e}")

        GLib.Thread.new("apply-reload-task", apply_and_reload_thread, None)

    def _update_face_image_widget(self, icon_path: str) -> bool:
        try:
            if self.appearance.face_image and self.appearance.face_image.get_window():
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 64, 64)
                self.appearance.face_image.set_from_pixbuf(pixbuf)
        except Exception as e:
            print(f"Error reloading face icon preview: {e}")
            if self.appearance.face_image and self.appearance.face_image.get_window():
                self.appearance.face_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
        return GLib.SOURCE_REMOVE

    def _on_reset(self, widget) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Reset all settings to defaults?",
        )
        dialog.format_secondary_text(
            "This will reset all keybindings and appearance settings to their default values."
        )

        if dialog.run() == Gtk.ResponseType.YES:
            self._apply_defaults()

        dialog.destroy()

    def _apply_defaults(self) -> None:
        from config import settings_utils
        from config.settings_constants import DEFAULTS

        settings_utils.bind_vars.clear()
        settings_utils.bind_vars.update(DEFAULTS.copy())

        for prefix_key, suffix_key, prefix_entry, suffix_entry in self.entries:
            prefix_entry.set_text(settings_utils.bind_vars[prefix_key])
            suffix_entry.set_text(settings_utils.bind_vars[suffix_key])

        self.appearance.wall_dir_chooser.set_filename(settings_utils.bind_vars["wallpapers_dir"])

        default_position = get_default("bar_position")
        try:
            self.appearance.position_combo.set_active(POSITIONS.index(default_position))
        except ValueError:
            self.appearance.position_combo.set_active(0)

        self.appearance.centered_switch.set_active(get_bind_var("centered_bar"))
        self.appearance.centered_switch.set_sensitive(default_position in ["Left", "Right"])
        self.appearance.datetime_12h_switch.set_active(get_bind_var("datetime_12h_format"))
        self.appearance.dock_switch.set_active(get_bind_var("dock_enabled"))
        self.appearance.dock_hover_switch.set_active(get_bind_var("dock_always_show"))
        self.appearance.dock_hover_switch.set_sensitive(self.appearance.dock_switch.get_active())
        self.appearance.dock_size_scale.set_value(get_bind_var("dock_icon_size"))

        self.system.terminal_entry.set_text(settings_utils.bind_vars["terminal_command"])
        self.system.auto_append_switch.set_active(get_bind_var("auto_append_hyprland"))

        self.appearance.ws_num_switch.set_active(get_bind_var("bar_workspace_show_number"))
        self.appearance.ws_chinese_switch.set_active(get_bind_var("bar_workspace_use_chinese_numerals"))
        self.appearance.ws_chinese_switch.set_sensitive(self.appearance.ws_num_switch.get_active())
        self.appearance.special_ws_switch.set_active(get_bind_var("bar_hide_special_workspace"))

        default_theme = get_default("bar_theme")
        try:
            self.appearance.bar_theme_combo.set_active(THEMES.index(default_theme))
        except ValueError:
            self.appearance.bar_theme_combo.set_active(0)

        default_dock_theme = get_default("dock_theme")
        try:
            self.appearance.dock_theme_combo.set_active(THEMES.index(default_dock_theme))
        except ValueError:
            self.appearance.dock_theme_combo.set_active(0)

        default_panel_theme = get_default("panel_theme")
        try:
            self.appearance.panel_theme_combo.set_active(PANEL_THEMES.index(default_panel_theme))
        except ValueError:
            self.appearance.panel_theme_combo.set_active(0)

        default_panel_position = get_default("panel_position")
        try:
            self.appearance.panel_position_combo.set_active(PANEL_POSITIONS.index(default_panel_position))
        except ValueError:
            self.appearance.panel_position_combo.set_active(0)

        default_notif_pos = get_default("notif_pos")
        try:
            self.appearance.notification_pos_combo.set_active(NOTIFICATION_POSITIONS.index(default_notif_pos))
        except ValueError:
            self.appearance.notification_pos_combo.set_active(0)

        for name, switch in self.appearance.component_switches.items():
            switch.set_active(get_bind_var(f"bar_{name}_visible"))
        self.appearance.corners_switch.set_active(get_bind_var("corners_visible"))

        metrics_vis_defaults = get_default("metrics_visible")
        for k, s in self.system.metrics_switches.items():
            s.set_active(metrics_vis_defaults.get(k, True))

        metrics_small_vis_defaults = get_default("metrics_small_visible")
        for k, s in self.system.metrics_small_switches.items():
            s.set_active(metrics_small_vis_defaults.get(k, True))

        for child in list(self.system.disk_entries.get_children()):
            self.system.disk_entries.remove(child)
        for p in get_default("bar_metrics_disks"):
            self._add_disk_entry_widget(p)

        limited_apps_list = get_default("limited_apps_history")
        self.system.limited_apps_entry.set_text(", ".join(f'"{app}"' for app in limited_apps_list))

        ignored_apps_list = get_default("history_ignored_apps")
        self.system.ignored_apps_entry.set_text(", ".join(f'"{app}"' for app in ignored_apps_list))

        default_monitors = get_default("selected_monitors")
        for monitor_name, checkbox in self.system.monitor_checkboxes.items():
            is_selected = len(default_monitors) == 0 or monitor_name in default_monitors
            checkbox.set_active(is_selected)

        self._on_panel_theme_changed(self.appearance.panel_theme_combo)

        self.appearance.selected_face_icon = None
        self.appearance.face_status_label.label = ""

        current_face = os.path.expanduser("~/.face.icon")
        try:
            if os.path.exists(current_face):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(current_face, 64, 64)
                self.appearance.face_image.set_from_pixbuf(pixbuf)
            else:
                self.appearance.face_image.set_from_icon_name("user-info", Gtk.IconSize.DIALOG)
        except Exception:
            self.appearance.face_image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

        if self.system.lock_switch:
            self.system.lock_switch.set_active(False)
        if self.system.idle_switch:
            self.system.idle_switch.set_active(False)

    def _on_close(self, widget) -> None:
        if self.application:
            self.application.quit()
        else:
            self.destroy()
