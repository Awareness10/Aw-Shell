import json
from collections.abc import Callable
from dataclasses import dataclass

from fabric.hyprland.widgets import HyprlandActiveWindow as ActiveWindow
from fabric.utils.helpers import FormattedString
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from fabric.widgets.stack import Stack
from gi.repository import Gdk, GLib, Gtk, Pango

import config.data as data
import utils.apps as apps
from modules.cliphist import ClipHistory
from modules.corners import MyCorner
from modules.dashboard import Dashboard
from modules.emoji import EmojiPicker
from modules.launcher import AppLauncher
from modules.notch_osd import AudioDisplays
from modules.overview import Overview
from modules.player import PlayerSmall
from modules.power import PowerMenu
from modules.tmux import TmuxManager
from modules.tools import Toolbox
from utils.icon_resolver import IconResolver
from utils.monitor_manager import get_monitor_manager
from utils.notch_layout import notch_layout
from utils.occlusion import OcclusionWatcher
from widgets.wayland import WaylandWindow as Window


@dataclass(frozen=True)
class NotchView:
    """A view open_notch(name) shows on the notch stack."""

    name: str
    # Child of the notch stack
    widget: object
    on_open: Callable[[], object] | None = None
    # Runs after on_open
    focus: Callable[[], object] | None = None
    hide_bar_revealers: bool = False
    # Dashboard views: section to go to, and the applet stack child in the
    # widgets section. Applets switch in place while the dashboard shows.
    section: str | None = None
    applet: object | None = None


class Notch(Window):
    def __init__(self, monitor_id: int = 0, **kwargs):
        self.monitor_id = monitor_id
        self.monitor_manager = get_monitor_manager()
        self._layout = layout = notch_layout(
            panel_theme=data.PANEL_THEME,
            bar_position=data.BAR_POSITION,
            panel_position=data.PANEL_POSITION,
            vertical=data.VERTICAL,
            bar_theme=data.BAR_THEME,
        )

        super().__init__(
            name="notch",
            layer="overlay",
            anchor=layout.anchor,
            margin=layout.margin,
            keyboard_mode="none",
            exclusivity=layout.exclusivity,
            visible=True,
            all_visible=True,
            monitor=monitor_id,
        )

        self._init_state(kwargs.get("bar", None))
        self._build_views()
        self._build_osd()
        self._build_compact()
        self._build_stack()
        self._build_frame()
        self._finish_init()

    def _init_state(self, bar):
        """State the handlers rely on: timers, flags, the bar link, app lookups."""
        # Audio display variables
        self.VOLUME_DISPLAY_DURATION = 2000
        self._current_display_timeout_id = None
        self._suppress_first_audio_display = True

        self._typed_chars_buffer = ""
        self._launcher_transitioning = False
        self._launcher_transition_timeout = None

        self.bar = bar
        self.is_hovered = False
        self.connect("realize", self._on_realize)
        self._prevent_occlusion = False
        self._occlusion_timer_id = None
        self._forced_occlusion = False

        self.icon_resolver = IconResolver()
        self.app_identifiers = apps.app_identifiers()

    def _build_views(self):
        """The dashboard and the other views the notch opens."""
        self.dashboard = Dashboard(notch=self)
        self.nhistory = self.dashboard.widgets.notification_history

        self.applet_stack = self.dashboard.widgets.applet_stack
        self.btdevices = self.dashboard.widgets.bluetooth
        self.nwconnections = self.dashboard.widgets.network_connections

        self.btdevices.set_visible(False)
        self.nwconnections.set_visible(False)

        self.launcher = AppLauncher(notch=self)
        self.overview = Overview(monitor_id=self.monitor_id)
        self.emoji = EmojiPicker(notch=self)
        self.power = PowerMenu(notch=self)
        self.tmux = TmuxManager(notch=self)
        self.cliphist = ClipHistory(notch=self)

    def _build_osd(self):
        """Volume and microphone displays shown in the compact notch."""
        self.audio_displays = AudioDisplays(show=self._show_audio_display)
        self.audio = self.audio_displays.volume.source.audio
        volume, mic = self.audio_displays.volume, self.audio_displays.mic
        self.volume_icon, self.volume_bar = volume.icon, volume.bar
        self.volume_label, self.volume_box = volume.label, volume.box
        self.mic_icon, self.mic_bar = mic.icon, mic.bar
        self.mic_label, self.mic_box = mic.label, mic.box

    def _build_compact(self):
        """The closed notch: active window, player, user and OSD."""
        self.window_icon = Image(
            name="notch-window-icon", icon_name="application-x-executable", icon_size=20
        )

        self.active_window = ActiveWindow(
            name="hyprland-window",
            h_expand=True,
            h_align="fill",
            formatter=FormattedString(
                "{'Desktop' if not win_title or win_title == 'unknown' else win_title}",
            ),
        )

        self.active_window_box = CenterBox(
            name="active-window-box",
            h_expand=True,
            h_align="fill",
            start_children=self.window_icon,
            center_children=self.active_window,
            end_children=None,
        )

        self.active_window_box.connect(
            "button-press-event",
            lambda widget, event: (self.open_notch("dashboard"), False)[1],
        )

        self.active_window.connect("notify::label", self.update_window_icon)

        if data.PANEL_THEME == "Notch":
            self.active_window.connect("notify::label", self.on_active_window_changed)

        self.active_window.get_children()[0].set_hexpand(True)
        self.active_window.get_children()[0].set_halign(Gtk.Align.FILL)
        self.active_window.get_children()[0].set_ellipsize(Pango.EllipsizeMode.END)

        self.active_window.connect(
            "notify::label", lambda *_: self.restore_label_properties()
        )

        self.player_small = PlayerSmall()
        self.user_label = Label(
            name="compact-user", label=f"{data.USERNAME}@{data.HOSTNAME}"
        )

        self.player_small.mpris_manager.connect(
            "player-appeared",
            lambda *_: self.compact_stack.set_visible_child(self.player_small),
        )
        self.player_small.mpris_manager.connect(
            "player-vanished", self.on_player_vanished
        )

        self.compact_stack = Stack(
            name="notch-compact-stack",
            v_expand=True,
            h_expand=True,
            transition_type="slide-up-down",
            transition_duration=100,
            children=[
                self.user_label,
                self.active_window_box,
                self.player_small,
                # Add audio display widgets to compact stack
                self.volume_box,
                self.mic_box,
            ],
        )
        self.compact_stack.set_visible_child(self.active_window_box)

        self.compact = Gtk.EventBox(name="notch-compact")
        self.compact.set_visible(True)
        self.compact.add(self.compact_stack)
        self.compact.add_events(
            Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.SMOOTH_SCROLL_MASK
        )
        self.compact.connect("scroll-event", self._on_compact_scroll)
        self.compact.connect(
            "button-press-event",
            lambda widget, event: (self.open_notch("dashboard"), False)[1],
        )
        self.compact.connect("enter-notify-event", self.on_button_enter)
        self.compact.connect("leave-notify-event", self.on_button_leave)

    def _build_stack(self):
        """The notch content stack holding every view, and the view registry."""
        self.tools = Toolbox(notch=self)
        self.stack = Stack(
            name="notch-content",
            v_expand=True,
            h_expand=True,
            style_classes=["invert"] if self._layout.invert else [],
            transition_type="crossfade",
            transition_duration=250,
            children=[
                self.compact,
                self.launcher,
                self.dashboard,
                self.overview,
                self.emoji,
                self.power,
                self.tools,
                self.tmux,
                self.cliphist,
            ],
        )

        if data.PANEL_THEME == "Panel":
            self.stack.add_style_class("panel")

            self.stack.add_style_class(data.BAR_POSITION.lower())
            self.stack.add_style_class(data.PANEL_POSITION.lower())

        if self._layout.narrow_views:
            self.compact.set_size_request(260, 40)
            self.launcher.set_size_request(320, 635)
            self.tmux.set_size_request(320, 635)
            self.cliphist.set_size_request(320, 635)
            self.dashboard.set_size_request(410, 900)

        else:
            self.compact.set_size_request(260, 40)
            self.launcher.set_size_request(480, 244)
            self.tmux.set_size_request(480, 244)
            self.cliphist.set_size_request(480, 244)
            self.dashboard.set_size_request(1093, 472)

        self.stack.set_interpolate_size(True)
        self.stack.set_homogeneous(False)
        self._views = self._build_view_registry()

    def _build_frame(self):
        """Corners, revealer and wrappers around the stack; adds it to the window."""
        self.corner_left = Box(
            name="notch-corner-left",
            orientation="v",
            h_align="start",
            children=[MyCorner("top-right")],
        )

        self.corner_right = Box(
            name="notch-corner-right",
            orientation="v",
            h_align="end",
            children=[MyCorner("top-left")],
        )

        self.notch_box = CenterBox(
            name="notch-box",
            orientation="h",
            h_align="center",
            v_align="center",
            start_children=self.corner_left,
            center_children=self.stack,
            end_children=self.corner_right,
        )

        self.notch_box.add_style_class(data.PANEL_THEME.lower())

        self.notch_revealer = Revealer(
            name="notch-revealer",
            transition_type=self._layout.revealer_transition,
            transition_duration=250,
            child_revealed=True,
            child=self.notch_box,
        )
        
        self.notch_revealer.set_size_request(-1, 1)

        self.notch_complete = Box(
            name="notch-complete",
            orientation="v" if self._layout.is_panel_vertical else "h",
            children=[self.notch_revealer],
        )

        self._is_notch_open = False
        self._scrolling = False

        if self._layout.vert_comp_size is not None:
            vert_comp_size = self._layout.vert_comp_size

            self.vert_comp_left = Box(name="vert-comp")
            self.vert_comp_left.set_size_request(vert_comp_size, 0)
            self.vert_comp_left.set_sensitive(False)
            
            self.vert_comp_right = Box(name="vert-comp") 
            self.vert_comp_right.set_size_request(vert_comp_size, 0)
            self.vert_comp_right.set_sensitive(False)
            
            self.notch_children = [
                self.vert_comp_left,
                self.notch_complete,
                self.vert_comp_right,
            ]
        else:
            self.notch_children = [self.notch_complete]

        self.notch_wrap = Box(
            name="notch-wrap",
            children=self.notch_children,
        )

        # Create top-level EventBox that wraps the entire notch for hover detection
        if data.PANEL_THEME == "Notch":
            self.hover_eventbox = Gtk.EventBox(name="notch-hover-eventbox")
            self.hover_eventbox.add(self.notch_wrap)
            self.hover_eventbox.set_visible(True)
            # Set minimum size to ensure hover detection area is always available
            self.hover_eventbox.set_size_request(260, 4)  # Width matches compact size, min height for hover
            self.hover_eventbox.add_events(
                Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
            )
            self.hover_eventbox.connect(
                "enter-notify-event", self.on_notch_hover_area_enter
            )
            self.hover_eventbox.connect(
                "leave-notify-event", self.on_notch_hover_area_leave
            )
            self.add(self.hover_eventbox)
        else:
            self.add(self.notch_wrap)
        self.show_all()

    def _finish_init(self):
        """Keybindings, signals, initial reveal state and occlusion watching."""
        # Connect audio signals after a short delay
        GLib.timeout_add(100, self._connect_audio_signals)

        self.add_keybinding("Escape", lambda *_: self.close_notch())
        self.add_keybinding("Ctrl Tab", lambda *_: self.dashboard.go_to_next_child())
        self.add_keybinding(
            "Ctrl Shift ISO_Left_Tab", lambda *_: self.dashboard.go_to_previous_child()
        )

        self.update_window_icon()

        self.active_window.connect(
            "button-press-event",
            lambda widget, event: (self.open_notch("dashboard"), False)[1],
        )

        if data.PANEL_THEME != "Notch":
            for corner in [self.corner_left, self.corner_right]:
                corner.set_visible(False)

        self._current_window_class = self._get_current_window_class()

        # Always enable occlusion detection for fullscreen windows. The watcher
        # reacts to Hyprland events; the timer only re-applies its cached state
        # after hover/open state changes
        self._monitor_name = self._get_monitor_name()
        self._occlusion_watcher = OcclusionWatcher.get()
        self._occlusion_watcher.connect(self._check_occlusion)
        GLib.timeout_add(500, self._check_occlusion)

        if data.PANEL_THEME == "Notch":
            self.notch_revealer.set_reveal_child(True)
        else:
            self.notch_revealer.set_reveal_child(False)

        self.connect("key-press-event", self.on_key_press)

    def _connect_audio_signals(self):
        self.audio_displays.connect()
        self.connect("destroy", lambda *_: self.audio_displays.disconnect())
        GLib.timeout_add(500, self._enable_audio_display)
        return False

    def _enable_audio_display(self):
        """Startup values (and the first changes) only update the displays."""
        self._suppress_first_audio_display = False
        self.audio_displays.arm()
        return False

    def _show_audio_display(self, display):
        if self._is_notch_open:
            return
        if self._current_display_timeout_id:
            GLib.source_remove(self._current_display_timeout_id)
        self.compact_stack.set_visible_child(display.box)
        self._current_display_timeout_id = GLib.timeout_add(
            self.VOLUME_DISPLAY_DURATION, self.return_to_normal_view
        )

    def show_volume_display(self):
        self._show_audio_display(self.audio_displays.volume)

    def show_mic_display(self):
        self._show_audio_display(self.audio_displays.mic)

    def return_to_normal_view(self):
        self._current_display_timeout_id = None

        if not self._is_notch_open:
            current_child = self.compact_stack.get_visible_child()
            if current_child in [self.volume_box, self.mic_box]:
                self.compact_stack.set_visible_child(self.active_window_box)

        return False

    def on_button_enter(self, widget, event):
        self.is_hovered = True
        window = widget.get_window()
        if window:
            window.set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2))
        return True

    def on_button_leave(self, widget, event):
        if event.detail == Gdk.NotifyType.INFERIOR:
            return False

        self.is_hovered = False
        window = widget.get_window()
        if window:
            window.set_cursor(None)
        return True

    def _on_realize(self, widget):
        """Ensure the notch window is raised above the bar."""
        self.get_window().raise_()

    def on_notch_hover_area_enter(self, widget, event):
        """Handle hover enter for the entire notch area"""
        self.is_hovered = True
        if data.PANEL_THEME == "Notch" and data.BAR_POSITION != "Top":
            self.notch_revealer.set_reveal_child(True)
        return False

    def on_notch_hover_area_leave(self, widget, event):
        """Handle hover leave for the entire notch area"""

        if event.detail == Gdk.NotifyType.INFERIOR:
            return False

        self.is_hovered = False

        return False

    def close_notch(self):
        if self.monitor_manager:
            self.monitor_manager.set_notch_state(self.monitor_id, False)
            
        self.set_keyboard_mode("none")
        self.notch_box.remove_style_class("open")
        self.stack.remove_style_class("open")

        self.bar.revealer_right.set_reveal_child(True)
        self.bar.revealer_left.set_reveal_child(True)
        self.applet_stack.set_visible_child(self.nhistory)
        self._is_notch_open = False
        self.stack.set_visible_child(self.compact)
        if data.PANEL_THEME != "Notch":
            self.notch_revealer.set_reveal_child(False)

        if self.bar and not self.bar.get_visible() and data.BAR_POSITION == "Top":
            self.set_margin(self._layout.hidden_bar_margin)

    def open_notch(self, widget_name: str):
        # Debug info for troubleshooting
        if hasattr(self, '_debug_monitor_focus') and self._debug_monitor_focus:
            print(f"DEBUG: open_notch called on monitor {self.monitor_id} for widget '{widget_name}'")
        
        # Handle monitor focus switching - always check real focused monitor from Hyprland
        if self.monitor_manager:
            # Get real focused monitor directly from Hyprland to ensure accuracy
            real_focused_monitor_id = self._get_real_focused_monitor_id()
            
            # Update monitor manager if we got a valid result
            if real_focused_monitor_id is not None:
                # Update the monitor manager's focused monitor
                self.monitor_manager._focused_monitor_id = real_focused_monitor_id
                if hasattr(self, '_debug_monitor_focus') and self._debug_monitor_focus:
                    print(f"DEBUG: Real focused monitor from Hyprland: {real_focused_monitor_id}")
            
            focused_monitor_id = self.monitor_manager.get_focused_monitor_id()
            focused_notch = self.monitor_manager.get_instance(focused_monitor_id, 'notch')

            # Close notches on other monitors
            self.monitor_manager.close_all_notches_except(focused_monitor_id)

            if focused_notch and hasattr(focused_notch, 'open_notch'):
                # Open notch on focused monitor
                focused_notch._open_notch_internal(widget_name)
                self.monitor_manager.set_notch_state(focused_monitor_id, True, widget_name)

    def _get_real_focused_monitor_id(self):
        """Get the real focused monitor ID directly from Hyprland."""
        # Use thread to avoid blocking UI
        self._focused_monitor_result = None
        self._focused_monitor_done = False
        GLib.Thread.new("get-focused-monitor", self._get_focused_monitor_thread, None)
        # Wait for result (not ideal, but for compatibility)
        import time
        start = time.time()
        while not self._focused_monitor_done and time.time() - start < 2.0:
            time.sleep(0.01)
        return self._focused_monitor_result

    def _get_focused_monitor_thread(self, user_data):
        try:
            self._focused_monitor_result = self.monitor_manager.query_focused_monitor_id()
        finally:
            self._focused_monitor_done = True

    def _build_view_registry(self):
        """The views open_notch() can show, by name (see NotchView)."""
        widgets_section = {"section": "widgets", "hide_bar_revealers": True}

        def focus_search(view):
            return lambda: (view.search_entry.set_text(""), view.search_entry.grab_focus())

        views = [
            # Dashboard applets, in the widgets section's applet stack
            NotchView("dashboard", self.dashboard, applet=self.nhistory, **widgets_section),
            NotchView("bluetooth", self.dashboard, applet=self.btdevices, **widgets_section),
            NotchView(
                "network_applet", self.dashboard, applet=self.nwconnections, **widgets_section
            ),
            # Other dashboard sections
            *(
                NotchView(name, self.dashboard, section=name, hide_bar_revealers=True)
                for name in ("pins", "kanban", "wallpapers", "mixer")
            ),
            NotchView("tmux", self.tmux, on_open=lambda: self.tmux.open_manager()),
            NotchView(
                "cliphist", self.cliphist, on_open=lambda: GLib.idle_add(self.cliphist.open)
            ),
            NotchView(
                "launcher",
                self.launcher,
                on_open=lambda: self.launcher.open_launcher(),
                focus=focus_search(self.launcher),
            ),
            NotchView(
                "emoji",
                self.emoji,
                on_open=lambda: self.emoji.open_picker(),
                focus=focus_search(self.emoji),
            ),
            NotchView("overview", self.overview, hide_bar_revealers=True),
            NotchView("power", self.power),
            NotchView("tools", self.tools),
        ]
        return {view.name: view for view in views}

    def _view(self, widget_name: str) -> "NotchView":
        """The registered view; an unknown name shows the dashboard as it is."""
        view = self._views.get(widget_name)
        if view is None:
            view = NotchView(widget_name, self.dashboard, hide_bar_revealers=True)
        return view

    def _is_view_showing(self, view: "NotchView") -> bool:
        if self.stack.get_visible_child() != view.widget:
            return False
        if view.widget != self.dashboard:
            return True
        if view.section is None:
            return False
        return self.dashboard.stack.get_visible_child() == getattr(
            self.dashboard, view.section
        ) and (view.applet is None or self.applet_stack.get_visible_child() == view.applet)

    def _show_dashboard_section(self, view: "NotchView"):
        if view.section is None:
            return
        self.dashboard.go_to_section(view.section)
        if view.applet is not None:
            self.applet_stack.set_visible_child(view.applet)

    def _open_notch_internal(self, widget_name: str):
        self.notch_revealer.set_reveal_child(True)
        self.notch_box.add_style_class("open")
        self.stack.add_style_class("open")
        view = self._view(widget_name)

        # Opening the view that is showing closes the notch
        if self._is_view_showing(view):
            self.close_notch()
            return

        # Applets switch in place while the dashboard is showing
        if view.applet is not None and self.stack.get_visible_child() == self.dashboard:
            self.set_keyboard_mode("exclusive")
            self._show_dashboard_section(view)
            return

        self.set_keyboard_mode("exclusive")
        self.stack.set_visible_child(view.widget)

        if view.on_open:
            view.on_open()
        if view.focus:
            view.focus()

        self._show_dashboard_section(view)

        if self._layout.keep_bar_revealers:
            self.bar.revealer_right.set_reveal_child(True)
            self.bar.revealer_left.set_reveal_child(True)
        else:
            self.bar.revealer_right.set_reveal_child(not view.hide_bar_revealers)
            self.bar.revealer_left.set_reveal_child(not view.hide_bar_revealers)

        if self.bar and not self.bar.get_visible() and data.BAR_POSITION == "Top":
            self.set_margin("0px 8px 8px 8px")

        self._is_notch_open = True

    def _on_compact_scroll(self, widget, event):
        if self._scrolling:
            return True

        children = self.compact_stack.get_children()
        current = children.index(self.compact_stack.get_visible_child())
        new_index = current

        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < -0.1:
                new_index = (current - 1) % len(children)
            elif event.delta_y > 0.1:
                new_index = (current + 1) % len(children)
            else:
                return False
        elif event.direction == Gdk.ScrollDirection.UP:
            new_index = (current - 1) % len(children)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            new_index = (current + 1) % len(children)
        else:
            return False

        self.compact_stack.set_visible_child(children[new_index])
        self._scrolling = True
        GLib.timeout_add(500, self._reset_scrolling)
        return True

    def _reset_scrolling(self):
        self._scrolling = False
        return False

    def on_player_vanished(self, *args):
        if self.player_small.mpris_label.get_label() == "Nothing Playing":
            self.compact_stack.set_visible_child(self.active_window_box)

    def restore_label_properties(self):
        label = self.active_window.get_children()[0]
        if isinstance(label, Gtk.Label):
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_hexpand(True)
            label.set_halign(Gtk.Align.FILL)
            label.queue_resize()

            self.update_window_icon()

    def find_app(self, app_id: str):
        """Exact match on the identifier map (no substring fallback, unlike the dock)."""
        return self.app_identifiers.get(app_id.lower())

    def update_window_icon(self, *args):
        """Update the window icon based on the current active window title"""

        label_widget = self.active_window.get_children()[0]
        if not isinstance(label_widget, Gtk.Label):
            return

        title = label_widget.get_text()
        if title == "Desktop" or not title:
            self.window_icon.set_visible(False)
            return

        self.window_icon.set_visible(True)
        app_id = self._get_current_window_class()
        icon_pixbuf = self._app_icon_pixbuf(app_id, 20) if app_id else None
        if icon_pixbuf:
            self.window_icon.set_from_pixbuf(icon_pixbuf)
        else:
            self.window_icon.set_from_icon_name("application-x-executable", 20)

    def _app_icon_pixbuf(self, app_id: str, size: int):
        """The app's icon: its desktop entry, else the icon theme by class
        (and by the part before a "-", for classes like "app-beta")."""
        try:
            desktop_app = self.find_app(app_id)
            pixbuf = apps.icon_pixbuf(desktop_app, size) if desktop_app else None
            if not pixbuf:
                pixbuf = self.icon_resolver.get_icon_pixbuf(app_id, size)
            if not pixbuf and "-" in app_id:
                pixbuf = self.icon_resolver.get_icon_pixbuf(app_id.split("-")[0], size)
            return pixbuf
        except Exception as e:
            print(f"Error updating window icon: {e}")
            return None

    def _check_occlusion(self):
        """
        Check if top 40px of the screen is occluded by any window
        and update the notch_revealer accordingly.
        """

        if self._forced_occlusion:
            # When forced occlusion is active, show only on hover
            self.notch_revealer.set_reveal_child(self.is_hovered)
        elif not (self.is_hovered or self._is_notch_open or self._prevent_occlusion):
            is_occluded = self._occlusion_watcher.is_occluded(self._monitor_name)
            self.notch_revealer.set_reveal_child(not is_occluded)

        return True

    def _get_monitor_name(self):
        """Connector name of this notch's monitor, or None if unknown.

        monitor_id is the GDK monitor index the window is placed by.
        """
        screen = Gdk.Screen.get_default()
        if screen is None or not 0 <= self.monitor_id < screen.get_display().get_n_monitors():
            return None
        return screen.get_monitor_plug_name(self.monitor_id)
    
    def force_occlusion(self):
        """Force notch to occlusion mode (hidden)."""
        self._forced_occlusion = True
        self._prevent_occlusion = False
        self.notch_revealer.set_reveal_child(False)
        # Start occlusion check timer if in vertical mode (left/right)
        if data.BAR_POSITION in ["Left", "Right"]:
            GLib.timeout_add(100, self._check_occlusion)
    
    def restore_from_occlusion(self):
        """Restore notch from occlusion mode."""
        self._forced_occlusion = False
        if data.PANEL_THEME == "Notch":
            if data.BAR_POSITION == "Top":
                self.notch_revealer.set_reveal_child(True)
            else:
                self._prevent_occlusion = False

    def _get_current_window_class(self):
        """The active window's initial class (else its class); "" without one."""
        try:
            from fabric.hyprland.widgets import get_hyprland_connection

            conn = get_hyprland_connection()
            if conn:
                window = json.loads(conn.send_command("j/activewindow").reply.decode())
                return window.get("initialClass", "") or window.get("class", "")
        except Exception as e:
            print(f"Error getting window class: {e}")
        return ""

    def on_active_window_changed(self, *args):
        """
        Temporarily remove the 'occluded' class when active window class changes
        to make the notch visible momentarily.
        """

        if data.PANEL_THEME != "Notch":
            return

        new_window_class = self._get_current_window_class()

        if new_window_class != self._current_window_class:
            self._current_window_class = new_window_class

            if self._occlusion_timer_id is not None:
                GLib.source_remove(self._occlusion_timer_id)
                self._occlusion_timer_id = None

            self._prevent_occlusion = True
            self.notch_revealer.set_reveal_child(True)

            self._occlusion_timer_id = GLib.timeout_add(
                500, self._restore_occlusion_check
            )

    def _restore_occlusion_check(self):
        """Re-enable occlusion checking after temporary visibility"""

        self._prevent_occlusion = False
        self._occlusion_timer_id = None

        return False

    def open_launcher_with_text(self, initial_text):
        """Open the launcher with initial text in the search field."""

        self._launcher_transitioning = True

        if initial_text:
            self._typed_chars_buffer = initial_text

        if self.stack.get_visible_child() == self.launcher:
            current_text = self.launcher.search_entry.get_text()
            self.launcher.search_entry.set_text(current_text + initial_text)

            self.launcher.search_entry.set_position(-1)
            self.launcher.search_entry.select_region(-1, -1)
            self.launcher.search_entry.grab_focus()
            return

        self.set_keyboard_mode("exclusive")

        for style in [
            "launcher",
            "dashboard",
            "notification",
            "overview",
            "emoji",
            "power",
            "tools",
            "tmux",
        ]:
            self.stack.remove_style_class(style)
        for w in dict.fromkeys(view.widget for view in self._views.values()):
            w.remove_style_class("open")

        self.stack.add_style_class("launcher")
        self.stack.set_visible_child(self.launcher)
        self.launcher.add_style_class("open")

        self.launcher.ensure_initialized()

        self.launcher.open_launcher()

        if self._launcher_transition_timeout:
            GLib.source_remove(self._launcher_transition_timeout)

        self._launcher_transition_timeout = GLib.timeout_add(
            150, self._finalize_launcher_transition
        )

        self.bar.revealer_right.set_reveal_child(True)
        self.bar.revealer_left.set_reveal_child(True)

        self._is_notch_open = True

    def _finalize_launcher_transition(self):
        """Apply buffered text and finalize launcher transition"""

        if self._typed_chars_buffer:
            entry = self.launcher.search_entry
            entry.set_text(self._typed_chars_buffer)

            entry.grab_focus()

            GLib.timeout_add(10, self._ensure_no_text_selection)
            GLib.timeout_add(50, self._ensure_no_text_selection)
            GLib.timeout_add(100, self._ensure_no_text_selection)

            print(f"Applied buffered text: '{self._typed_chars_buffer}'")

            self._typed_chars_buffer = ""

        self._launcher_transitioning = False
        self._launcher_transition_timeout = None

        return False

    def _ensure_no_text_selection(self):
        """Make absolutely sure no text is selected in the search entry"""
        entry = self.launcher.search_entry

        text_len = len(entry.get_text())

        entry.set_position(text_len)

        entry.select_region(text_len, text_len)

        if not entry.has_focus():
            entry.grab_focus()

            GLib.idle_add(lambda: entry.select_region(text_len, text_len))

        return False

    @staticmethod
    def _typed_char(keyval):
        """The character a key types into the launcher search, or None."""
        keychar = chr(keyval) if 32 <= keyval <= 126 else None

        is_valid_char = (
            (keyval >= Gdk.KEY_a and keyval <= Gdk.KEY_z)
            or (keyval >= Gdk.KEY_A and keyval <= Gdk.KEY_Z)
            or (keyval >= Gdk.KEY_0 and keyval <= Gdk.KEY_9)
            or keyval
            in (Gdk.KEY_space, Gdk.KEY_underscore, Gdk.KEY_minus, Gdk.KEY_period)
        )
        return keychar if is_valid_char else None

    def on_key_press(self, widget, event):
        """Handle key presses at the notch level"""

        if self._launcher_transitioning:
            keychar = self._typed_char(event.keyval)
            if keychar:
                self._typed_chars_buffer += keychar
                print(
                    f"Buffered character: {keychar}, buffer now: '{self._typed_chars_buffer}'"
                )
                return True

        # Typing on the dashboard's widgets section opens the launcher
        if (
            self.stack.get_visible_child() == self.dashboard
            and self.dashboard.stack.get_visible_child() == self.dashboard.widgets
        ):
            keychar = self._typed_char(event.keyval)
            if keychar:
                print(f"Notch received keypress: {keychar}")

                self.open_launcher_with_text(keychar)
                return True

        return False
