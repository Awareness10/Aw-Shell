"""Notifications: the D-Bus server, the popup window and its container.
The card is in modules/notification_box.py, the history panel in
modules/notification_history_view.py."""


from fabric.notifications.service import Notifications
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from gi.repository import GLib, Gtk
from loguru import logger

import modules.icons as icons
from config.shell_settings import settings
from modules.notification_box import NotificationBox, get_limited_apps_history
from modules.notification_history_view import NotificationHistory
from widgets.wayland import WaylandWindow as Window

_notification_server = None


def get_notification_server() -> Notifications:
    """The process-wide org.freedesktop.Notifications server.

    fabric's service never releases its bus name or exported object, so a
    second instance in the same process fails to register.
    """
    global _notification_server
    if _notification_server is None:
        _notification_server = Notifications()
    return _notification_server


class NotificationContainer(Box):
    def __init__(
        self,
        notification_history_instance: NotificationHistory,
        revealer_transition_type: str = "slide-down",
        before_show=None,
    ):
        super().__init__(name="notification-container-main", orientation="v", spacing=4)
        self.notification_history = notification_history_instance
        # Called when a notification arrives while none are on screen
        self._before_show = before_show

        self._server = get_notification_server()
        handlers = [
            self._server.connect("notification-added", self.on_new_notification),
            self._server.connect("notification-removed", self.on_notification_removed),
        ]
        self.connect("destroy", lambda *_: [self._server.disconnect(h) for h in handlers])
        self._pending_removal = False
        self._is_destroying = False

        self.stack = Gtk.Stack(
            name="notification-stack",
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=200,
            visible=True,
        )
        self.navigation = Box(
            name="notification-navigation", spacing=4, h_align="center"
        )
        self.stack_box = Box(
            name="notification-stack-box",
            h_align="center",
            h_expand=False,
            children=[self.stack],
        )
        self.prev_button = Button(
            name="nav-button",
            child=Label(name="nav-button-label", markup=icons.chevron_left),
            on_clicked=self.show_previous,
        )
        self.close_all_button = Button(
            name="nav-button",
            child=Label(name="nav-button-label", markup=icons.cancel),
            on_clicked=self.close_all_notifications,
        )
        self.close_all_button_label = self.close_all_button.get_child()
        self.close_all_button_label.add_style_class("close")
        self.next_button = Button(
            name="nav-button",
            child=Label(name="nav-button-label", markup=icons.chevron_right),
            on_clicked=self.show_next,
        )
        for button in [self.prev_button, self.close_all_button, self.next_button]:
            button.connect(
                "enter-notify-event", lambda *_: self.pause_and_reset_all_timeouts()
            )
            button.connect("leave-notify-event", lambda *_: self.resume_all_timeouts())
        self.navigation.add(self.prev_button)
        self.navigation.add(self.close_all_button)
        self.navigation.add(self.next_button)

        self.navigation_revealer = Revealer(
            transition_type="slide-down",
            transition_duration=200,
            child=self.navigation,
            reveal_child=False,
        )

        self.notification_box_container = Box(
            name="notification-box-internal-container",
            orientation="v",
            children=[self.stack_box, self.navigation_revealer],
        )

        self.main_revealer = Revealer(
            name="notification-main-revealer",
            transition_type=revealer_transition_type,
            transition_duration=250,
            child_revealed=False,
            child=self.notification_box_container,
        )

        self.add(self.main_revealer)

        self.notifications = []
        self.current_index = 0
        self.update_navigation_buttons()
        self._destroyed_notifications = set()

    def on_new_notification(self, fabric_notif, id):
        notification_history_instance = self.notification_history
        if notification_history_instance.do_not_disturb_enabled:
            logger.info(
                "Do Not Disturb mode enabled: adding notification directly to history."
            )
            notification = fabric_notif.get_notification_from_id(id)
            new_box = NotificationBox(notification)  # caches its image itself
            notification_history_instance.add_notification(new_box)
            return

        if not self.notifications and self._before_show:
            self._before_show()

        notification = fabric_notif.get_notification_from_id(id)
        new_box = NotificationBox(notification)
        new_box.set_container(self)
        notification.connect("closed", self.on_notification_closed)

        app_name = notification.app_name
        if app_name in get_limited_apps_history():
            notification_history_instance.clear_history_for_app(app_name)

            existing_notification_index = -1
            for index, existing_box in enumerate(self.notifications):
                if existing_box.notification.app_name == app_name:
                    existing_notification_index = index
                    break

            if existing_notification_index != -1:
                old_notification_box = self.notifications.pop(
                    existing_notification_index
                )
                self.stack.remove(old_notification_box)
                old_notification_box.destroy()

                self.stack.add_named(new_box, str(id))
                self.notifications.append(new_box)
                self.current_index = len(self.notifications) - 1
                self.stack.set_visible_child(new_box)
            else:
                while len(self.notifications) >= 5:
                    oldest_notification = self.notifications[0]
                    notification_history_instance.add_notification(oldest_notification)
                    self.stack.remove(oldest_notification)
                    self.notifications.pop(0)
                    if self.current_index > 0:
                        self.current_index -= 1
                self.stack.add_named(new_box, str(id))
                self.notifications.append(new_box)
                self.current_index = len(self.notifications) - 1
                self.stack.set_visible_child(new_box)
        else:
            while len(self.notifications) >= 5:
                oldest_notification = self.notifications[0]
                notification_history_instance.add_notification(oldest_notification)
                self.stack.remove(oldest_notification)
                self.notifications.pop(0)
                if self.current_index > 0:
                    self.current_index -= 1
            self.stack.add_named(new_box, str(id))
            self.notifications.append(new_box)
            self.current_index = len(self.notifications) - 1
            self.stack.set_visible_child(new_box)

        for notification_box in self.notifications:
            notification_box.start_timeout()
        self.main_revealer.show_all()
        self.main_revealer.set_reveal_child(True)
        self.update_navigation_buttons()

    def show_previous(self, *args):
        if self.current_index > 0:
            self.current_index -= 1
            self.stack.set_visible_child(self.notifications[self.current_index])
            self.update_navigation_buttons()

    def show_next(self, *args):
        if self.current_index < len(self.notifications) - 1:
            self.current_index += 1
            self.stack.set_visible_child(self.notifications[self.current_index])
            self.update_navigation_buttons()

    def update_navigation_buttons(self):
        self.prev_button.set_sensitive(self.current_index > 0)
        self.next_button.set_sensitive(self.current_index < len(self.notifications) - 1)
        should_reveal = len(self.notifications) > 1
        self.navigation_revealer.set_reveal_child(should_reveal)

    def on_notification_removed(self, _server, notification_id):
        # fabric emits this for every close, before the notification's own
        # "closed" handlers run; only the app withdrawing it (CloseNotification)
        # leaves it unhandled, so check once those have had their turn
        GLib.idle_add(self._close_withdrawn, notification_id)

    def _close_withdrawn(self, notification_id):
        if notification_id not in self._destroyed_notifications:
            for notif_box in self.notifications:
                if notif_box.notification.id == notification_id:
                    notif_box.notification.close("closed-by-application")
                    break
        return False

    def on_notification_closed(self, notification, reason):
        if self._is_destroying:
            return
        if notification.id in self._destroyed_notifications:
            return
        self._destroyed_notifications.add(notification.id)
        try:
            logger.info(f"Notification {notification.id} closing with reason: {reason}")
            notif_to_remove = None
            for i, notif_box in enumerate(self.notifications):
                if notif_box.notification.id == notification.id:
                    notif_to_remove = (i, notif_box)
                    break
            if not notif_to_remove:
                return
            i, notif_box = notif_to_remove
            reason_str = str(reason)

            notification_history_instance = self.notification_history

            if reason_str == "NotificationCloseReason.DISMISSED_BY_USER":
                logger.info(
                    f"Cleaning up resources for dismissed notification {notification.id}"
                )
                notif_box.destroy()
            elif (
                reason_str == "NotificationCloseReason.EXPIRED"
                or reason_str == "NotificationCloseReason.CLOSED_BY_APPLICATION"
                or reason_str == "NotificationCloseReason.UNKNOWN"
            ):
                logger.info(
                    f"Adding notification {notification.id} to history (reason: {reason_str})"
                )
                notif_box.set_is_history(True)
                notification_history_instance.add_notification(notif_box)
                notif_box.stop_timeout()
            else:
                logger.warning(
                    f"Unknown close reason: {reason_str} for notification {notification.id}. Defaulting to destroy."
                )
                notif_box.destroy()

            new_index = i
            if i == self.current_index:
                new_index = max(0, i - 1)
            elif i < self.current_index:
                new_index = self.current_index - 1

            if notif_box.get_parent() == self.stack:
                self.stack.remove(notif_box)
            self.notifications.pop(i)

            if new_index >= len(self.notifications) and len(self.notifications) > 0:
                new_index = len(self.notifications) - 1

            self.current_index = new_index
            
            if not self.notifications:
                self._is_destroying = True
                self.main_revealer.set_reveal_child(False)
                self._destroy_container()
                return
            else:
                self.stack.set_visible_child(self.notifications[self.current_index])

            self.update_navigation_buttons()
        except Exception as e:
            logger.error(f"Error closing notification: {e}")

    def _destroy_container(self):
        try:
            self.notifications.clear()
            self._destroyed_notifications.clear()
            for child in self.stack.get_children():
                self.stack.remove(child)
                child.destroy()
            self.current_index = 0
        except Exception as e:
            logger.error(f"Error cleaning up the container: {e}")
        finally:
            self._is_destroying = False

    def pause_and_reset_all_timeouts(self):
        if self._is_destroying:
            return
        for notification in self.notifications[:]:
            try:
                if not notification._destroyed and notification.get_parent():
                    notification.stop_timeout()
            except Exception as e:
                logger.error(f"Error pausing timeout: {e}")

    def resume_all_timeouts(self):
        if self._is_destroying:
            return
        for notification in self.notifications[:]:
            try:
                if not notification._destroyed and notification.get_parent():
                    notification.start_timeout()
            except Exception as e:
                logger.error(f"Error resuming timeout: {e}")

    def close_all_notifications(self, *args):
        notifications_to_close = self.notifications.copy()
        for notification_box in notifications_to_close:
            notification_box.notification.close("dismissed-by-user")


class NotificationPopup(Window):
    def __init__(self, **kwargs):
        y_pos = settings.notif_pos.lower()
        x_pos = "right"

        if (
            settings.bar_position in ["Top", "Bottom"]
            and settings.panel_position == "End"
            or x_pos == settings.bar_position.lower()
        ):
            x_pos = "left"

        super().__init__(
            name="notification-popup",
            anchor=f"{x_pos} {y_pos}",
            layer="top",
            keyboard_mode="none",
            exclusivity="none",
            monitor=kwargs.get("monitor"),
            visible=True,
            all_visible=True,
        )

        self.widgets = kwargs.get("widgets", None)

        self.notification_history = (
            self.widgets.notification_history if self.widgets else NotificationHistory()
        )
        # Monitors the popup may follow focus to; None keeps it where it is
        self._follow_focus_monitors = kwargs.get("follow_focus_monitors")
        self.notification_container = NotificationContainer(
            notification_history_instance=self.notification_history,
            revealer_transition_type="slide-down" if y_pos == "top" else "slide-up",
            before_show=self._move_to_focused_monitor,
        )

        self.show_box = Box()
        self.show_box.set_size_request(1, 1)

        self.add(
            Box(
                name="notification-popup-box",
                orientation="v",
                children=[self.notification_container, self.show_box],
            )
        )

    def _move_to_focused_monitor(self):
        """Show new notifications on the monitor in use.

        Only runs while none are on screen, so a visible stack never jumps
        between monitors.
        """
        if not self._follow_focus_monitors:
            return
        from utils.monitor_manager import get_monitor_manager

        monitor_id = get_monitor_manager().query_focused_monitor_id()
        if monitor_id in self._follow_focus_monitors and monitor_id != self.monitor:
            self.monitor = monitor_id
