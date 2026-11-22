import gi

gi.require_version("DbusmenuGtk3", "0.4")
import os

from fabric.widgets.box import Box
from gi.repository import DbusmenuGtk3, Gdk, GdkPixbuf, GLib, Gtk
from loguru import logger

from config.shell_settings import settings
from services.status_notifier import Item, Watcher, pick_pixmap, pixmap_to_pixbuf

_watcher = None
_menus: dict[Item, tuple[str, DbusmenuGtk3.Menu | None]] = {}


def _get_watcher() -> Watcher:
    """Process-wide watcher shared by every bar's tray.

    Only one watcher per process can serve org.kde.StatusNotifierWatcher;
    a second one never receives items, so its tray would stay empty.
    """
    global _watcher
    if _watcher is None:
        _watcher = Watcher()
    return _watcher


def _drop_menu(item: Item):
    entry = _menus.pop(item, None)
    if entry is not None and entry[1] is not None:
        entry[1].destroy()


def _get_menu(item: Item) -> DbusmenuGtk3.Menu | None:
    """The item's dbusmenu as a Gtk.Menu, shared by every tray; built when the
    item is added, so it has loaded by the time it pops up."""
    path = item.get_menu_path()
    entry = _menus.get(item)
    if entry is not None and entry[0] == path:
        return entry[1]
    if entry is None:
        item.connect("removed", _drop_menu)
    else:
        _drop_menu(item)
    if not path:
        _menus[item] = (path, None)
        return None
    menu = DbusmenuGtk3.Menu.new(item.owner or item.get_bus_name(), path)
    _menus[item] = (path, menu)
    return menu


class SystemTray(Box):
    def __init__(self, pixel_size: int = 20, **kwargs) -> None:
        orientation = Gtk.Orientation.HORIZONTAL if not settings.vertical else Gtk.Orientation.VERTICAL
        super().__init__(
            name="systray",
            orientation=orientation,
            spacing=8,
            **kwargs
        )
        self.enabled = True
        super().set_visible(False)
        self.pixel_size = pixel_size
        self.buttons_by_id = {}
        self.items_by_id = {}
        self.item_handlers_by_id = {}

        self.watcher = _get_watcher()
        self._watcher_handler = self.watcher.connect("item-added", self.on_watcher_item_added)
        self.connect("destroy", self._on_destroy)

        # Items registered before this tray was built (e.g. by another bar)
        for identifier in list(self.watcher.get_items()):
            self.on_watcher_item_added(self.watcher, identifier)

    def _disconnect_item(self, identifier: str):
        item = self.items_by_id.get(identifier)
        for handler in self.item_handlers_by_id.pop(identifier, []):
            if item is not None and item.handler_is_connected(handler):
                item.disconnect(handler)

    def _on_destroy(self, *_):
        if self.watcher.handler_is_connected(self._watcher_handler):
            self.watcher.disconnect(self._watcher_handler)
        for identifier in list(self.items_by_id):
            self._disconnect_item(identifier)

    def set_visible(self, visible: bool):
        self.enabled = visible
        self._update_visibility()

    def _update_visibility(self):
        has = len(self.get_children()) > 0
        super().set_visible(self.enabled and has)

    def _get_item_pixbuf(self, item: Item) -> GdkPixbuf.Pixbuf:
        try:
            name = item.get_icon_name()
            pm = pick_pixmap(item.get_icon_pixmaps(), self.pixel_size)
            # A pixmap smaller than the icon only wins when there's no icon name
            if pm and (pm.width >= self.pixel_size or not name):
                pixbuf = pixmap_to_pixbuf(pm, self.pixel_size, GdkPixbuf.InterpType.HYPER)
                if pixbuf:
                    return pixbuf

            # If IconName is a file path, prioritize loading directly from the file
            if name and os.path.exists(name):
                try:
                    return GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        name, self.pixel_size, self.pixel_size, True
                    )
                except Exception as e:
                    # The file path exists but loading fails, falling back to theme search
                    logger.debug(
                        f"Load icon from file failed: {e}; fallback to theme for '{name}'"
                    )

            theme = Gtk.IconTheme.new()
            path = item.get_icon_theme_path()
            if path:
                theme.prepend_search_path(path)
            return theme.load_icon(name, self.pixel_size, Gtk.IconLookupFlags.FORCE_SIZE)
        except GLib.Error as e:
            logger.debug(f"Icon load error {e}")
            return Gtk.IconTheme.get_default().load_icon(
                "image-missing", self.pixel_size, Gtk.IconLookupFlags.FORCE_SIZE
            )

    def _refresh_item_ui(self, item: Item, button: Gtk.Button):
        pixbuf = self._get_item_pixbuf(item)
        img = button.get_image()
        if isinstance(img, Gtk.Image):
            img.set_from_pixbuf(pixbuf)
        else:
            new = Gtk.Image.new_from_pixbuf(pixbuf)
            button.set_image(new)
            new.show()
        tip = item.get_title()
        if tip:
            button.set_tooltip_text(tip)
        else:
            button.set_has_tooltip(False)

    def on_watcher_item_added(self, _, identifier: str):
        item = self.watcher.get_item_for_identifier(identifier)
        if not item:
            return

        if identifier in self.buttons_by_id:
            self._disconnect_item(identifier)
            self.buttons_by_id[identifier].destroy()
            del self.buttons_by_id[identifier]
            del self.items_by_id[identifier]

        btn = self.do_bake_item_button(item)
        self.buttons_by_id[identifier] = btn
        self.items_by_id[identifier] = item

        _get_menu(item)
        handlers = [
            # Fires for icon, title, tooltip, status and menu changes
            item.connect("changed", lambda itm: self._refresh_item_ui(itm, btn)),
            item.connect("removed", lambda itm: self.on_item_instance_removed(identifier, itm)),
        ]
        self.item_handlers_by_id[identifier] = handlers

        self.add(btn)
        btn.show_all()
        self._update_visibility()

    def do_bake_item_button(self, item: Item) -> Gtk.Button:
        btn = Gtk.Button()
        btn.connect("button-press-event", lambda b, e: self.on_button_click(b, item, e))
        img = Gtk.Image.new_from_pixbuf(self._get_item_pixbuf(item))
        btn.set_image(img)
        tip = item.get_title()
        if tip:
            btn.set_tooltip_text(tip)
        return btn

    def on_item_instance_removed(self, identifier: str, removed_item: Item):
        if self.items_by_id.get(identifier) is removed_item:
            self._disconnect_item(identifier)
            btn = self.buttons_by_id.pop(identifier, None)
            self.items_by_id.pop(identifier, None)
            if btn:
                btn.destroy()
            self._update_visibility()

    def on_button_click(self, button: Gtk.Button, item: Item, event: Gdk.EventButton):
        if event.button == Gdk.BUTTON_PRIMARY:
            try:
                item.activate(int(event.x_root), int(event.y_root))
            except Exception as e:
                logger.error(f"Activate error: {e}")
        elif event.button == Gdk.BUTTON_SECONDARY:
            menu = _get_menu(item)
            if isinstance(menu, Gtk.Menu):
                menu.popup_at_widget(button, Gdk.Gravity.SOUTH_WEST,
                                     Gdk.Gravity.NORTH_WEST, event)
            else:
                try:
                    item.context_menu(int(event.x_root), int(event.y_root))
                except Exception as e:
                    logger.error(f"ContextMenu error: {e}")
