"""One notification: its card (icon, text, actions, timeout) and the
helpers for its image, shared by the popup and the history."""

import os
import uuid
from pathlib import Path

from fabric.notifications.service import Notification, NotificationAction
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from gi.repository import GdkPixbuf, GLib, Gtk
from loguru import logger

import modules.icons as icons
from config.paths import NOTIFICATION_HISTORY, NOTIFICATIONS_DIR, ensure_dir
from config.shell_settings import read_config_file
from utils.notification_history import (
    image_file_name,
)
from widgets.image import CustomImage

# Session-only, private to the user: $XDG_RUNTIME_DIR/aw-shell/notifications
PERSISTENT_DIR = str(NOTIFICATIONS_DIR)
PERSISTENT_HISTORY_FILE = str(NOTIFICATION_HISTORY)


# Get configurable app lists from settings
def get_limited_apps_history():
    config = read_config_file()
    return config.get("limited_apps_history", ["Spotify"])


def get_history_ignored_apps():
    config = read_config_file()
    return config.get("history_ignored_apps", ["Hyprshot"])


def notification_pixbuf(notification):
    """The notification's image, or None. fabric loads an image-path hint
    from disk on every access and raises when the file doesn't exist."""
    try:
        return notification.image_pixbuf
    except GLib.Error as e:
        logger.warning(f"Notification {notification.id}: can't load its image: {e.message}")
        return None


def cache_notification_pixbuf(notification_box):
    """
    Saves a scaled pixbuf (48x48) in the cache directory and returns the cache file path.
    """
    notification = notification_box.notification
    pixbuf = notification_pixbuf(notification)
    if pixbuf:
        ensure_dir(Path(PERSISTENT_DIR))
        cache_file = os.path.join(PERSISTENT_DIR, image_file_name(notification_box.uuid))
        logger.debug(
            f"Caching image for notification {notification.id} to: {cache_file}"
        )
        try:
            scaled = pixbuf.scale_simple(
                48, 48, GdkPixbuf.InterpType.BILINEAR
            )
            scaled.savev(cache_file, "png", [], [])
            logger.info(
                f"Successfully cached image for notification {notification.id} to: {cache_file}"
            )
            return cache_file
        except Exception as e:
            logger.error(f"Error caching image for notification {notification.id}: {e}")
            return None
    else:
        logger.debug(f"Notification {notification.id} has no image_pixbuf to cache.")
        return None


def load_scaled_pixbuf(notification_box, width, height):
    """
    Loads and scales a pixbuf for a notification_box, prioritizing cached images.
    """
    notification = notification_box.notification
    if not hasattr(notification_box, "notification") or notification is None:
        logger.error(
            "load_scaled_pixbuf: notification_box.notification is None or not set!"
        )
        return None

    pixbuf = None
    if (
        hasattr(notification_box, "cached_image_path")
        and notification_box.cached_image_path
        and os.path.exists(notification_box.cached_image_path)
    ):
        try:
            logger.debug(
                f"Attempting to load cached image from: {notification_box.cached_image_path} for notification {notification.id}"
            )
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(notification_box.cached_image_path)
            if pixbuf:
                pixbuf = pixbuf.scale_simple(
                    width, height, GdkPixbuf.InterpType.BILINEAR
                )
                logger.info(
                    f"Successfully loaded cached image from: {notification_box.cached_image_path} for notification {notification.id}"
                )
            return pixbuf
        except Exception as e:
            logger.error(
                f"Error loading cached image from {notification_box.cached_image_path} for notification {notification.id}: {e}"
            )
            logger.warning(
                f"Falling back to notification.image_pixbuf for notification {notification.id}"
            )

    pixbuf = notification_pixbuf(notification)
    if pixbuf:
        pixbuf = pixbuf.scale_simple(
            width, height, GdkPixbuf.InterpType.BILINEAR
        )
        return pixbuf

    logger.debug(
        f"No image_pixbuf or cached image found, trying app icon for notification {notification.id}"
    )
    return get_app_icon_pixbuf(notification.app_icon, width, height)


def image_box(pixbuf):
    """The notification's image, or None without one (an empty box left a gap)."""
    if pixbuf is None:
        return None
    return Box(
        name="notification-image",
        orientation="v",
        children=[CustomImage(pixbuf=pixbuf), Box(v_expand=True)],
    )


def get_app_icon_pixbuf(icon_path, width, height):
    """
    Loads and scales a pixbuf from an app icon path.
    """
    if not icon_path:
        return None
    if icon_path.startswith("file://"):
        icon_path = icon_path[7:]
    if not os.path.exists(icon_path):
        logger.warning(f"Icon path does not exist: {icon_path}")
        return None
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_path)
        return pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    except Exception as e:
        logger.error(f"Failed to load or scale icon: {e}")
        return None


class ActionButton(Button):
    def __init__(
        self, action: NotificationAction, index: int, total: int, notification_box
    ):
        super().__init__(
            name="action-button",
            h_expand=True,
            on_clicked=self.on_clicked,
            child=Label(
                name="button-label",
                h_expand=True,
                h_align="fill",
                ellipsization="end",
                max_chars_width=1,
                label=action.label,
            ),
        )
        self.action = action
        self.notification_box = notification_box
        style_class = (
            "start-action"
            if index == 0
            else "end-action"
            if index == total - 1
            else "middle-action"
        )
        self.add_style_class(style_class)
        self.connect(
            "enter-notify-event", lambda *_: notification_box.hover_button(self)
        )
        self.connect(
            "leave-notify-event", lambda *_: notification_box.unhover_button(self)
        )

    def on_clicked(self, *_):
        self.action.invoke()
        self.action.parent.close("dismissed-by-user")


class NotificationBox(Box):
    def __init__(self, notification: Notification, timeout_ms=5000, **kwargs):
        super().__init__(
            name="notification-box",
            orientation="v",
            h_align="fill",
            h_expand=True,
            children=[],
        )
        self.notification = notification
        self.uuid = str(uuid.uuid4())

        if timeout_ms == 0:
            self.timeout_ms = 0
        else:
            live_timeout = getattr(self.notification, "timeout", -1)
            self.timeout_ms = live_timeout if live_timeout != -1 else timeout_ms
        self._timeout_id = None
        self._container = None
        self.cached_image_path = None
        # Before the timeout starts: its callback reads them
        self._destroyed = False
        self._is_history = False

        if self.timeout_ms > 0:
            self.start_timeout()

        if notification_pixbuf(self.notification):
            cache_path = cache_notification_pixbuf(self)
            if cache_path:
                self.cached_image_path = cache_path
                logger.debug(
                    f"NotificationBox {self.uuid}: Cached image path set to: {self.cached_image_path}"
                )
            else:
                logger.warning(
                    f"NotificationBox {self.uuid}: Caching failed, cached_image_path not set."
                )
        else:
            logger.debug(f"NotificationBox {self.uuid}: No image to cache.")

        content = self.create_content()
        action_buttons = self.create_action_buttons()
        self.add(content)
        if action_buttons:
            self.add(action_buttons)

        self.connect("enter-notify-event", self.on_hover_enter)
        self.connect("leave-notify-event", self.on_hover_leave)
        logger.debug(
            f"NotificationBox {self.uuid} created for notification {notification.id}"
        )

    def set_is_history(self, is_history):
        self._is_history = is_history

    def set_container(self, container):
        self._container = container

    def get_container(self):
        return self._container

    def create_header(self):
        notification = self.notification
        self.app_icon_image = (
            Image(
                name="notification-icon",
                image_file=notification.app_icon[7:],
                size=24,
            )
            if "file://" in notification.app_icon
            else Image(
                name="notification-icon",
                icon_name="dialog-information-symbolic" or notification.app_icon,
                icon_size=24,
            )
        )
        self.app_name_label_header = Label(
            notification.app_name, name="notification-app-name", h_align="start"
        )
        self.header_close_button = self.create_close_button()

        return CenterBox(
            name="notification-title",
            start_children=[
                Box(
                    spacing=4,
                    children=[
                        self.app_icon_image,
                        self.app_name_label_header,
                    ],
                )
            ],
            end_children=[self.header_close_button],
        )

    def create_content(self):
        notification = self.notification
        self.notification_image_box = image_box(load_scaled_pixbuf(self, 48, 48))
        self.notification_summary_label = Label(
            name="notification-summary",
            markup=notification.summary,
            h_align="start",
            max_chars_width=16,
            ellipsization="end",
        )
        self.notification_app_name_label_content = Label(
            name="notification-app-name",
            markup=notification.app_name,
            h_align="start",
            max_chars_width=16,
            ellipsization="end",
        )
        self.notification_body_label = (
            Label(
                markup=notification.body,
                h_align="start",
                max_chars_width=34,
                ellipsization="end",
            )
            if notification.body
            else Box()
        )
        self.notification_body_label.set_single_line_mode(
            True
        ) if notification.body else None
        self.notification_text_box = Box(
            name="notification-text",
            orientation="v",
            v_align="center",
            h_expand=True,
            h_align="start",
            children=[
                Box(
                    name="notification-summary-box",
                    orientation="h",
                    children=[
                        self.notification_summary_label,
                        Box(
                            name="notif-sep",
                            h_expand=False,
                            v_expand=False,
                            h_align="center",
                            v_align="center",
                        ),
                        self.notification_app_name_label_content,
                    ],
                ),
                self.notification_body_label,
            ],
        )
        self.content_close_button = self.create_close_button()
        self.content_close_button_box = Box(
            orientation="v",
            children=[
                self.content_close_button,
            ],
        )

        return Box(
            name="notification-content",
            spacing=8,
            children=[
                box for box in (
                    self.notification_image_box,
                    self.notification_text_box,
                    self.content_close_button_box,
                ) if box
            ],
        )

    def create_action_buttons(self):
        notification = self.notification
        if not notification.actions:
            return None

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        grid.set_column_spacing(4)
        for i, action in enumerate(notification.actions):
            action_button = ActionButton(action, i, len(notification.actions), self)
            grid.attach(action_button, i, 0, 1, 1)
        return grid

    def create_close_button(self):
        self.close_button = Button(
            name="notif-close-button",
            child=Label(name="notif-close-label", markup=icons.cancel),
            on_clicked=lambda *_: self.notification.close("dismissed-by-user"),
        )
        self.close_button.connect(
            "enter-notify-event", lambda *_: self.hover_button(self.close_button)
        )
        self.close_button.connect(
            "leave-notify-event", lambda *_: self.unhover_button(self.close_button)
        )
        return self.close_button

    def on_hover_enter(self, *args):
        if self._container:
            self._container.pause_and_reset_all_timeouts()

    def on_hover_leave(self, *args):
        if self._container:
            self._container.resume_all_timeouts()

    def start_timeout(self):
        self.stop_timeout()
        self._timeout_id = GLib.timeout_add(self.timeout_ms, self.close_notification)

    def stop_timeout(self):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def close_notification(self):
        if not self._destroyed:
            try:
                logger.debug(
                    f"Notification {self.notification.id} timeout expired, closing notification."
                )
                self.notification.close("expired")
                self.stop_timeout()
            except Exception as e:
                logger.error(
                    f"Error in close_notification for notification {self.notification.id}: {e}"
                )
        return False

    def destroy(self, from_history_delete=False):
        logger.debug(
            f"NotificationBox destroy called for notification: {self.notification.id}, from_history_delete: {from_history_delete}, is_history: {self._is_history}"
        )
        if (
            hasattr(self, "cached_image_path")
            and self.cached_image_path
            and os.path.exists(self.cached_image_path)
            and (not self._is_history or from_history_delete)
        ):
            try:
                os.remove(self.cached_image_path)
                logger.info(f"Deleted cached image: {self.cached_image_path}")
            except Exception as e:
                logger.error(
                    f"Error deleting cached image {self.cached_image_path}: {e}"
                )
        self._destroyed = True
        self.stop_timeout()
        super().destroy()

    def hover_button(self, button):
        if self._container:
            self._container.pause_and_reset_all_timeouts()

    def unhover_button(self, button):
        if self._container:
            self._container.resume_all_timeouts()
