import gi

import config.data as data
from config.paths import PINS_FILE, ensure_dir

gi.require_version('Gtk', '3.0')
import json
import os
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request

import cairo
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import modules.icons as icons
from utils.portal import pick_file

SAVE_FILE = str(PINS_FILE)
SLOTS = 30  # 6 rows of 5, or 10 of 3 in a side panel

icon_size = 80
if data.PANEL_THEME == "Panel" and data.BAR_POSITION in ["Left", "Right"] or data.PANEL_POSITION in ["Start", "End"]:
    icon_size = 36

def createSurfaceFromWidget(widget: Gtk.Widget) -> cairo.ImageSurface:
    alloc = widget.get_allocation()
    surface = cairo.ImageSurface(cairo.Format.ARGB32, alloc.width, alloc.height)
    cr = cairo.Context(surface)
    cr.set_source_rgba(1, 1, 1, 0)
    cr.rectangle(0, 0, alloc.width, alloc.height)
    cr.fill()
    widget.draw(cr)
    return surface

def open_file(filepath):
    try:
        subprocess.Popen(["xdg-open", filepath])
    except Exception as e:
        print("Error opening file:", e)

def open_url(url):
    try:
        subprocess.Popen(["xdg-open", url])
    except Exception as e:
        print("Error opening URL:", e)

def is_url(text):

    url_pattern = re.compile(
        r'^(https?|ftp)://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(url_pattern.match(text))

def get_favicon_url(url):
    """Extract the base domain from a URL and construct a favicon URL."""
    parsed_url = urllib.parse.urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return f"{base_url}/favicon.ico"

def download_favicon(url, callback):
    """Download a favicon asynchronously and call the callback with the result."""
    favicon_url = get_favicon_url(url)

    def do_download():
        temp_file = None
        try:
            temp_fd, temp_path = tempfile.mkstemp(suffix='.ico')
            os.close(temp_fd)
            temp_file = temp_path

            urllib.request.urlretrieve(favicon_url, temp_path)

            GLib.idle_add(callback, temp_path)
        except Exception as e:
            print(f"Error downloading favicon: {e}")

            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            GLib.idle_add(callback, None)

    GLib.Thread.new("favicon-download", do_download, None)

class _FileEvents(FileSystemEventHandler):
    """Watchdog runs this on its own thread; the store handles it on GTK's."""

    def __init__(self, store):
        self.store = store

    def on_any_event(self, event):
        if not event.is_directory and event.event_type in ("deleted", "moved"):
            GLib.idle_add(self.store.on_file_event, event)


class PinStore(GObject.Object):
    """The pins, one set for the whole shell: every monitor's board shows and
    edits the same slots. Saved to SAVE_FILE; pinned files are followed when
    moved and unpinned when deleted. "changed" says which slot changed."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, (int,))}

    def __init__(self):
        super().__init__()
        self.slots = [(None, None)] * SLOTS  # (content, content_type)
        self._watched_dirs = set()
        self._observer = Observer()
        self._load()
        for content, content_type in self.slots:
            if content_type == 'file' and content:
                self._watch(content)
        self._observer.start()

    def get(self, index):
        return self.slots[index]

    def first_empty(self):
        return next((i for i, (content, _) in enumerate(self.slots) if content is None), None)

    def set(self, index, content, content_type):
        if self.slots[index] == (content, content_type):
            return
        self.slots[index] = (content, content_type)
        if content_type == 'file' and content:
            self._watch(content)
        self._save()
        self.emit("changed", index)

    def clear(self, index):
        self.set(index, None, None)

    def on_file_event(self, event):
        for index, (content, content_type) in enumerate(self.slots):
            if content_type != 'file' or not content:
                continue
            if os.path.realpath(content) != os.path.realpath(event.src_path):
                continue
            if event.event_type == 'deleted':
                self.clear(index)
            elif os.path.exists(event.dest_path):  # moved
                self.set(index, event.dest_path, 'file')

    def stop(self):
        self._observer.stop()
        self._observer.join()

    def _watch(self, filepath):
        folder = os.path.dirname(filepath)
        if folder not in self._watched_dirs and os.path.isdir(folder):
            self._observer.schedule(_FileEvents(self), folder, recursive=False)
            self._watched_dirs.add(folder)

    def _load(self):
        if not os.path.exists(SAVE_FILE):
            return
        try:
            with open(SAVE_FILE, 'r') as f:
                state = json.load(f)
            for index, cell_data in enumerate(state[:SLOTS]):
                self.slots[index] = (cell_data.get('content'), cell_data.get('content_type'))
        except Exception as e:
            print("Error loading pins:", e)

    def _save(self):
        state = [{'content_type': kind, 'content': content} for content, kind in self.slots]
        try:
            ensure_dir(PINS_FILE.parent)
            with open(SAVE_FILE, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print("Error saving pins:", e)


_store = None


def get_store():
    """The shell's one PinStore, created on first use."""
    global _store
    if _store is None:
        _store = PinStore()
    return _store


class Cell(Gtk.EventBox):
    """One slot of the store, shown on one board."""

    def __init__(self, store, index):
        super().__init__(name="pin-cell")
        self.store = store
        self.index = index
        self.box = Box(name="pin-cell-box", orientation="v", spacing=4)
        self.add(self.box)
        

        self.favicon_temp_path = None

        target_dest = Gtk.TargetEntry.new("text/uri-list", 0, 0)
        self.drag_dest_set(Gtk.DestDefaults.ALL, [target_dest], Gdk.DragAction.COPY)
        self.connect("drag-data-received", self.on_drag_data_received)

        targets = [
            Gtk.TargetEntry.new("text/uri-list", 0, 0),
            Gtk.TargetEntry.new("text/plain", 0, 1)
        ]
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, targets, Gdk.DragAction.COPY)
        self.connect("drag-data-get", self.on_drag_data_get)

        self.connect("button-press-event", self.on_button_press)

        self.connect("drag-begin", self.on_drag_begin)

        self.update_display()

    @property
    def content(self):
        return self.store.get(self.index)[0]

    @property
    def content_type(self):
        return self.store.get(self.index)[1]

    def update_display(self):

        if self.favicon_temp_path and os.path.exists(self.favicon_temp_path):
            try:
                os.remove(self.favicon_temp_path)
                self.favicon_temp_path = None
            except Exception as e:
                print(f"Error removing temp favicon: {e}")
        
        for child in self.box.get_children():
            self.box.remove(child)
        
        if self.content is None:
            label = Label(name="pin-add", markup=icons.paperclip)
            self.box.pack_start(label, True, True, 0)
        else:
            if self.content_type == 'file':
                widget = self.get_file_preview(self.content)
                self.box.pack_start(widget, True, True, 0)
                label = Label(name="pin-file", label=os.path.basename(self.content), justification="center", ellipsization="middle")
                self.box.pack_start(label, False, False, 0)
            elif self.content_type == 'text':
                if is_url(self.content):

                    icon_container = Box(name="pin-icon-container", orientation="v")
                    self.box.pack_start(icon_container, True, True, 0)
                    

                    url_icon = Label(name="pin-url-icon", markup=icons.world, style=f"font-size: {icon_size}px;")
                    icon_container.pack_start(url_icon, True, True, 0)
                    

                    domain = re.sub(r'^https?://', '', self.content)
                    domain = domain.split('/')[0]
                    label = Label(name="pin-url", label=domain, justification="center", ellipsization="end")
                    self.box.pack_start(label, False, False, 0)
                    

                    download_favicon(
                        self.content, 
                        lambda path: self.update_favicon(icon_container, url_icon, path)
                    )
                else:

                    label = Label(name="pin-text", label=self.content.split('\n')[0], justification="center", ellipsization="end", line_wrap="word-char")
                    self.box.pack_start(label, True, True, 0)
        self.box.show_all()
    
    def update_favicon(self, container, icon_widget, favicon_path):
        """Update the icon with the downloaded favicon or keep the default."""
        if not favicon_path or not os.path.exists(favicon_path):

            return
        
        try:

            self.favicon_temp_path = favicon_path
            

            if data.PANEL_THEME == "Panel" and data.BAR_POSITION in ["Left", "Right"]:

                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    favicon_path, width=36, height=36, preserve_aspect_ratio=True)
            else:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    favicon_path, width=48, height=48, preserve_aspect_ratio=True)
            

            container.remove(icon_widget)
            

            img = Gtk.Image.new_from_pixbuf(pixbuf)
            img.set_name("pin-favicon")
            container.pack_start(img, True, True, 0)
            

            container.show_all()
        except Exception as e:
            print(f"Error setting favicon: {e}")


    def get_file_preview(self, filepath):
        try:
            file = Gio.File.new_for_path(filepath)
            info = file.query_info("standard::content-type", Gio.FileQueryInfoFlags.NONE, None)
            content_type = info.get_content_type()
        except Exception:
            content_type = None

        icon_theme = Gtk.IconTheme.get_default()

        if content_type == "inode/directory":
            try:
                pixbuf = icon_theme.load_icon("default-folder", icon_size, 0)
                return Gtk.Image.new_from_pixbuf(pixbuf)
            except Exception:
                print("Error loading folder icon")
                return Gtk.Image.new_from_icon_name("default-folder", Gtk.IconSize.DIALOG)
        
        if content_type and content_type.startswith("image/"):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    filepath, width=icon_size, height=icon_size, preserve_aspect_ratio=True)
                return Gtk.Image.new_from_pixbuf(pixbuf)
            except Exception as e:
                print("Error loading image preview:", e)
        
        elif content_type and content_type.startswith("video/"):
            try:
                pixbuf = icon_theme.load_icon("video-x-generic", icon_size, 0)
                return Gtk.Image.new_from_pixbuf(pixbuf)
            except Exception:
                print("Error loading video icon")
                return Gtk.Image.new_from_icon_name("video-x-generic", Gtk.IconSize.DIALOG)
        else:
            icon_name = "text-x-generic"
            if content_type:
                themed_icon = Gio.content_type_get_icon(content_type)
                if hasattr(themed_icon, 'get_names'):
                    names = themed_icon.get_names()
                    if names:
                        icon_name = names[0]
            try:
                pixbuf = icon_theme.load_icon(icon_name, icon_size, 0)
                return Gtk.Image.new_from_pixbuf(pixbuf)
            except Exception:
                print("Error loading icon", icon_name)
                return Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)

    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        if self.content is None and data.get_length() >= 0:
            uris = data.get_uris()
            if uris:
                try:
                    filepath, _ = GLib.filename_from_uri(uris[0])
                    self.store.set(self.index, filepath, 'file')
                except Exception as e:
                    print("Error getting file from URI:", e)
        drag_context.finish(True, False, time)

    def on_drag_data_get(self, widget, drag_context, data, info, time):
        if self.content is None:
            return
        if info == 0 and self.content_type == 'file':
            uri = GLib.filename_to_uri(self.content)
            data.set_uris([uri])
        elif info == 1 and self.content_type == 'text':
            data.set_text(self.content, -1)

    def on_drag_begin(self, widget, context):

        if self.content_type == 'file':
            surface = createSurfaceFromWidget(self)
            Gtk.drag_set_icon_surface(context, surface)

    def on_button_press(self, widget, event):
        if self.content is None:
            if event.button == 1:
                self.select_file()
            elif event.button == 2:
                clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                text = clipboard.wait_for_text()
                if text:
                    self.store.set(self.index, text, 'text')
        else:
            if self.content_type == 'file':
                if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                    open_file(self.content)
                elif event.button == 3:
                    self.clear_cell()
            elif self.content_type == 'text':
                if event.button == 1:

                    if is_url(self.content):

                        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                        clipboard.set_text(self.content, -1)
                        

                        if not (event.state & Gdk.ModifierType.CONTROL_MASK):
                            open_url(self.content)
                    else:

                        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                        clipboard.set_text(self.content, -1)
                elif event.button == 3:
                    self.clear_cell()
        return True

    def select_file(self):
        # The picker is a normal window: it would open under the notch (an
        # overlay layer), and the open notch holds the keyboard. Close it
        # while picking, then come back to Pins
        notch = self.get_toplevel()
        if hasattr(notch, "close_notch"):
            notch.close_notch()

        def on_picked(filepath):
            if filepath and self.content is None:
                self.store.set(self.index, filepath, 'file')
            # open_notch toggles: skip it if the user reopened the notch meanwhile
            if hasattr(notch, "open_notch") and not getattr(notch, "_is_notch_open", False):
                notch.open_notch("pins")

        pick_file("Pin a File", on_picked)

    def clear_cell(self):
        # Every board's update_display removes its own favicon
        self.store.clear(self.index)

class Pins(Gtk.Box):
    """A board of the shared pins; each monitor's dashboard has one."""

    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.store = get_store()
        self.cells = []

        grid = Gtk.Grid(row_spacing=8, column_spacing=8, name="pin-grid")
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)

        scrolled_window = ScrolledWindow(child=grid, name="scrolled-window", style_classes="pins", propagate_width=False, propagate_height=False)
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        scrolled_window.set_halign(Gtk.Align.FILL)
        scrolled_window.set_valign(Gtk.Align.FILL)
        self.pack_start(scrolled_window, True, True, 0)

        side_panel = data.PANEL_THEME == "Panel" and (
            data.BAR_POSITION in ["Left", "Right"] or data.PANEL_POSITION in ["Start", "End"]
        )
        columns = 3 if side_panel else 5
        for index in range(SLOTS):
            cell = Cell(self.store, index)
            self.cells.append(cell)
            grid.attach(cell, index % columns, index // columns, 1, 1)

        handler = self.store.connect("changed", self.on_slot_changed)
        self.connect("destroy", lambda *_: self.store.disconnect(handler))

        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.connect("drag-data-received", self.on_drag_data_received)

    def on_slot_changed(self, _store, index):
        self.cells[index].update_display()

    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        if data.get_length() >= 0:
            for uri in data.get_uris():
                index = self.store.first_empty()
                if index is None:
                    break
                try:
                    filepath, _ = GLib.filename_from_uri(uri)
                    self.store.set(index, filepath, 'file')
                except Exception as e:
                    print("Error getting file from URI:", e)
        drag_context.finish(True, False, time)
