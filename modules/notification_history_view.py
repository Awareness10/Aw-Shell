"""The dashboard's notification history: rows for past notifications,
grouped by day, kept in the history file."""

import os
from datetime import datetime, timedelta
from pathlib import Path

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import GLib, Gtk
from loguru import logger

import modules.icons as icons
from config.paths import ensure_dir
from modules.notification_box import (
    PERSISTENT_DIR,
    PERSISTENT_HISTORY_FILE,
    NotificationBox,
    get_history_ignored_apps,
    get_limited_apps_history,
    image_box,
    load_scaled_pixbuf,
)
from utils.notification_history import (
    HISTORY_LIMIT,
    HistoryStore,
    date_header,
    ordinal,
    orphan_images,
    parse_timestamp,
)


class HistoricalNotification(object):
    def __init__(
        self, id, app_icon, summary, body, app_name, timestamp, cached_image_path=None
    ):
        self.id = id
        self.app_icon = app_icon
        self.summary = summary
        self.body = body
        self.app_name = app_name
        self.timestamp = timestamp
        self.cached_image_path = cached_image_path
        self.image_pixbuf = None
        self.actions = []
        self.cached_scaled_pixbuf = None


class NotificationHistory(Box):
    def __init__(self, **kwargs):
        super().__init__(name="notification-history", orientation="v", **kwargs)

        self.containers = []
        self.header_label = Label(
            name="nhh",
            label="Notifications",
            h_align="start",
            h_expand=True,
        )
        self.header_switch = Gtk.Switch(name="dnd-switch")
        self.header_switch.set_vexpand(False)
        self.header_switch.set_valign(Gtk.Align.CENTER)
        self.header_switch.set_active(False)
        self.header_clean = Button(
            name="nhh-button",
            child=Label(name="nhh-button-label", markup=icons.trash),
            on_clicked=self.clear_history,
        )
        self.do_not_disturb_enabled = False
        self.header_switch.connect("notify::active", self.on_do_not_disturb_changed)
        self.dnd_label = Label(name="dnd-label", markup=icons.notifications_off)

        self.history_header = CenterBox(
            name="notification-history-header",
            spacing=8,
            start_children=[self.header_switch, self.dnd_label],
            center_children=[self.header_label],
            end_children=[self.header_clean],
        )
        self.notifications_list = Box(
            name="notifications-list",
            orientation="v",
            spacing=4,
            h_expand=True,
            v_expand=True,
            h_align="fill",
            v_align="fill",
        )
        self.no_notifications_label = Label(
            name="no-notif",
            markup=icons.notifications_clear,
            v_align="fill",
            h_align="fill",
            v_expand=True,
            h_expand=True,
            justification="center",
        )
        self.no_notifications_box = Box(
            name="no-notifications-box",
            v_align="fill",
            h_align="fill",
            v_expand=True,
            h_expand=True,
            children=[self.no_notifications_label],
        )
        self.scrolled_window = ScrolledWindow(
            name="notification-history-scrolled-window",
            orientation="v",
            h_expand=True,
            v_expand=True,
            h_align="fill",
            v_align="fill",
            propagate_width=False,
            propagate_height=False,
        )
        self.scrolled_window_viewport_box = Box(
            orientation="v",
            children=[self.notifications_list, self.no_notifications_box],
        )
        self.scrolled_window.add(self.scrolled_window_viewport_box)
        self._store = HistoryStore(PERSISTENT_HISTORY_FILE)
        self.add(self.history_header)
        self.add(self.scrolled_window)
        # One notification per idle call; False once the generator is done
        # (a bare __next__ would leak StopIteration into GLib)
        loader = self._load_persistent_history()
        GLib.idle_add(lambda: next(loader, False))

    def get_ordinal(self, n):
        return ordinal(n)

    def get_date_header(self, dt):
        return date_header(dt)

    @property
    def persistent_notifications(self):
        return self._store.notes

    @persistent_notifications.setter
    def persistent_notifications(self, notes):
        self._store.notes = notes

    def schedule_midnight_update(self):
        now = datetime.now()
        next_midnight = datetime.combine(
            now.date() + timedelta(days=1), datetime.min.time()
        )
        delta_seconds = (next_midnight - now).total_seconds()
        GLib.timeout_add_seconds(int(delta_seconds), self.on_midnight)

    def on_midnight(self):
        self.rebuild_with_separators()
        self.schedule_midnight_update()
        return GLib.SOURCE_REMOVE

    def create_date_separator(self, date_header):
        return Box(
            name="notif-date-sep",
            children=[
                Label(
                    name="notif-date-sep-label",
                    label=date_header,
                    h_align="center",
                    h_expand=True,
                )
            ],
        )

    def rebuild_with_separators(self):
        GLib.idle_add(self._do_rebuild_with_separators)

    def _do_rebuild_with_separators(self):
        for child in list(self.notifications_list.get_children()):
            self.notifications_list.remove(child)

        current_date_header = None
        for container in sorted(
            self.containers, key=lambda x: x.arrival_time, reverse=True
        ):
            header = self.get_date_header(container.arrival_time)
            if header != current_date_header:
                self.notifications_list.add(self.create_date_separator(header))
                current_date_header = header
            self.notifications_list.add(container)

        self.notifications_list.show_all()
        self.update_no_notifications_label_visibility()

    def on_do_not_disturb_changed(self, switch, pspec):
        self.do_not_disturb_enabled = switch.get_active()
        logger.info(
            f"Do Not Disturb mode {'enabled' if self.do_not_disturb_enabled else 'disabled'}"
        )

    def clear_history(self, *args):
        for child in self.notifications_list.get_children()[:]:
            notif_box = getattr(child, "notification_box", None)
            if notif_box:
                notif_box.destroy(from_history_delete=True)
            self.notifications_list.remove(child)
            child.destroy()
        self._store.clear()
        logger.info("Notification history cleared and persistent file deleted.")
        self.containers = []
        self.rebuild_with_separators()

    def _load_persistent_history(self):
        ensure_dir(Path(PERSISTENT_DIR))
        for note in reversed(list(self._store.load())):
            try:
                self._add_historical_notification(note)
            except Exception as e:
                logger.error(f"Error loading persistent history: {e}")
            yield True
        GLib.idle_add(self.update_no_notifications_label_visibility)
        self._cleanup_orphan_cached_images()
        self.schedule_midnight_update()

    def _save_persistent_history(self):
        self._store.save()

    def delete_historical_notification(self, note_id, container):
        """A row's close button: gone from the panel, the file and the image cache."""
        if hasattr(container, "notification_box"):
            container.notification_box.destroy(from_history_delete=True)
        if not self._store.remove([note_id]):
            logger.warning(f"Notification {note_id} was not in the history file.")
        container.destroy()
        self.containers = [c for c in self.containers if c != container]
        self.rebuild_with_separators()

    def _build_row(self, notification_box, arrival_time):
        """One history row, the same for a notification that moved here this
        session and one restored from the file."""
        notification = notification_box.notification
        container = Box(
            name="notification-container",
            orientation="v",
            h_align="fill",
            h_expand=True,
        )
        container.notification_box = notification_box
        container.arrival_time = arrival_time

        def separator():
            return Box(
                name="notif-sep",
                h_expand=False,
                v_expand=False,
                h_align="center",
                v_align="center",
            )

        body = (
            Label(
                name="notification-body",
                markup=notification.body,
                h_align="start",
                ellipsization="end",
                line_wrap="word-char",
            )
            if notification.body
            else Box()
        )
        if notification.body:
            body.set_single_line_mode(True)
        text = Box(
            name="notification-text",
            orientation="v",
            v_align="center",
            h_expand=True,
            children=[
                Box(
                    name="notification-summary-box",
                    orientation="h",
                    children=[
                        Label(
                            name="notification-summary",
                            markup=notification.summary,
                            h_align="start",
                            ellipsization="end",
                        ),
                        separator(),
                        Label(
                            name="notification-app-name",
                            markup=f"{notification.app_name}",
                            h_align="start",
                            ellipsization="end",
                        ),
                        separator(),
                        Label(
                            name="notification-timestamp",
                            markup=arrival_time.strftime("%H:%M"),
                            h_align="start",
                            ellipsization="end",
                        ),
                    ],
                ),
                body,
            ],
        )
        close_button = Button(
            name="notif-close-button",
            child=Label(name="notif-close-label", markup=icons.cancel),
            on_clicked=lambda *_: self.delete_historical_notification(
                notification_box.uuid, container
            ),
        )
        content = Box(
            name="notification-content",
            spacing=8,
            children=[
                box for box in (
                    image_box(load_scaled_pixbuf(notification_box, 48, 48)),
                    text,
                    Box(orientation="v", children=[close_button, Box(v_expand=True)]),
                ) if box
            ],
        )
        container.add(
            Box(
                name="notification-box-hist",
                orientation="v",
                h_align="fill",
                h_expand=True,
                children=[content],
            )
        )
        return container

    def _add_historical_notification(self, note):
        hist_notif = HistoricalNotification(
            id=note.get("id"),
            app_icon=note.get("app_icon"),
            summary=note.get("summary"),
            body=note.get("body"),
            app_name=note.get("app_name"),
            timestamp=note.get("timestamp"),
            cached_image_path=note.get("cached_image_path"),
        )
        hist_box = NotificationBox(hist_notif, timeout_ms=0)
        hist_box.uuid = hist_notif.id
        hist_box.cached_image_path = hist_notif.cached_image_path
        hist_box.set_is_history(True)
        container = self._build_row(hist_box, parse_timestamp(hist_notif.timestamp))
        self.containers.insert(0, container)
        self.rebuild_with_separators()
        self.update_no_notifications_label_visibility()

    def add_notification(self, notification_box):
        app_name = notification_box.notification.app_name
        if app_name in get_history_ignored_apps():
            logger.info(
                f"Ignoring notification from {app_name} as it is in the ignored list."
            )
            notification_box.destroy(from_history_delete=True)
            return

        if app_name in get_limited_apps_history():
            self.clear_history_for_app(app_name)

        if len(self.containers) >= HISTORY_LIMIT:
            oldest_container = self.containers.pop()
            _remove_cached_image(getattr(oldest_container, "notification_box", None))
            oldest_container.destroy()

        container = self._build_row(notification_box, datetime.now())
        self.containers.insert(0, container)
        self.rebuild_with_separators()
        self._append_persistent_notification(notification_box, container.arrival_time)
        self.update_no_notifications_label_visibility()

    def _append_persistent_notification(self, notification_box, arrival_time):
        notification = notification_box.notification
        self._store.add({
            "id": notification_box.uuid,
            "app_icon": notification.app_icon,
            "summary": notification.summary,
            "body": notification.body,
            "app_name": notification.app_name,
            "timestamp": arrival_time.isoformat(),
            "cached_image_path": notification_box.cached_image_path,
        })

    def _cleanup_orphan_cached_images(self):
        if not os.path.exists(PERSISTENT_DIR):
            return
        ids = [note.get("id") for note in self._store.notes]
        for name in orphan_images(os.listdir(PERSISTENT_DIR), ids):
            path = os.path.join(PERSISTENT_DIR, name)
            try:
                os.remove(path)
                logger.info(f"Deleted orphan cached image: {path}")
            except OSError as e:
                logger.error(f"Error deleting orphan cached image {path}: {e}")

    def update_no_notifications_label_visibility(self):
        has_notifications = bool(self.containers)
        self.no_notifications_box.set_visible(not has_notifications)
        self.notifications_list.set_visible(has_notifications)

    def clear_history_for_app(self, app_name):
        """Clears all notifications in history for a specific app."""
        to_remove = [
            c for c in self.containers
            if hasattr(c, "notification_box")
            and c.notification_box.notification.app_name == app_name
        ]
        for container in to_remove:
            _remove_cached_image(container.notification_box)
            self.containers.remove(container)
            self.notifications_list.remove(container)
            container.notification_box.destroy(from_history_delete=True)
            container.destroy()
        self._store.remove(c.notification_box.uuid for c in to_remove)
        self.rebuild_with_separators()
        self.update_no_notifications_label_visibility()


def _remove_cached_image(notification_box) -> None:
    path = getattr(notification_box, "cached_image_path", None)
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Deleted cached image: {path}")
        except OSError as e:
            logger.error(f"Error deleting cached image {path}: {e}")
