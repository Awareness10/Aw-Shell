import json

import cairo
import gi
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow

import config.data as data
import modules.icons as icons
from config.paths import KANBAN_FILE, ensure_dir

gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, GLib, GObject, Gtk


def createSurfaceFromWidget(widget: Gtk.Widget) -> cairo.ImageSurface:
    alloc = widget.get_allocation()
    surface = cairo.ImageSurface(cairo.Format.ARGB32, alloc.width, alloc.height)
    cr = cairo.Context(surface)

    cr.set_source_rgba(0, 0, 0, 0)
    cr.rectangle(0, 0, alloc.width, alloc.height)
    cr.fill()
    widget.draw(cr)
    return surface

class InlineEditor(Gtk.Box):
    __gsignals__ = {
        'confirmed': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'canceled': (GObject.SignalFlags.RUN_LAST, None, ())
    }

    def __init__(self, initial_text=""):
        super().__init__(name="inline-editor", spacing=4)

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        buffer = self.text_view.get_buffer()
        buffer.set_text(initial_text)

        self.text_view.connect("key-press-event", self.on_key_press)
        
        confirm_btn = Gtk.Button(name="kanban-btn", child=Label(name="kanban-btn-label", markup=icons.accept))
        confirm_btn.connect("clicked", self.on_confirm)
        confirm_btn.get_style_context().add_class("flat")
        
        cancel_btn = Gtk.Button(name="kanban-btn", child=Label(name="kanban-btn-neg", markup=icons.cancel))
        cancel_btn.connect("clicked", self.on_cancel)
        cancel_btn.get_style_context().add_class("flat")
        

        # EXTERNAL: the text's width doesn't size the board (the notch grew
        # with every word); NEVER: it grows taller instead, the column scrolls
        sw = ScrolledWindow(name="scrolled-window", propagate_height=False, propagate_width=False)
        sw.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self.text_view.set_size_request(-1, 50)
        sw.add(self.text_view)

        self.button_box = Box(children=[confirm_btn, cancel_btn], spacing=4)
        self.center_box = CenterBox(center_children=[self.button_box], orientation="v")

        self.pack_start(sw, True, True, 0)
        self.pack_start(self.center_box, False, False, 0)
        self.show_all()

    def on_confirm(self, widget):
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True).strip()
        if text:
            self.emit('confirmed', text)
        else:
            self.emit('canceled')

    def on_cancel(self, widget):
        self.emit('canceled')

    def on_key_press(self, widget, event):

        if event.keyval == Gdk.KEY_Escape:
            self.emit('canceled')
            return True


        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            state = event.get_state()
            if state & Gdk.ModifierType.SHIFT_MASK:

                buffer = self.text_view.get_buffer()
                cursor_iter = buffer.get_iter_at_mark(buffer.get_insert())
                buffer.insert(cursor_iter, "\n")
                return True
            else:

                self.on_confirm(widget)
                return True
        return False

COLUMNS = ("To Do", "In Progress", "Done")


class KanbanStore(GObject.Object):
    """The notes, one set for the whole shell: every monitor's board shows
    and edits the same columns. Saved to KANBAN_FILE; "changed" names the
    column that changed."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self):
        super().__init__()
        self.columns = {title: [] for title in COLUMNS}
        self._load()

    def notes(self, title):
        return list(self.columns[title])

    def add(self, title, text):
        self.insert(title, len(self.columns[title]), text)

    def insert(self, title, index, text):
        self.columns[title].insert(index, text)
        self._changed(title)

    def edit(self, title, index, text):
        if self.columns[title][index] != text:
            self.columns[title][index] = text
            self._changed(title)

    def remove(self, title, index):
        del self.columns[title][index]
        self._changed(title)

    def move(self, source, source_index, target, target_index):
        """Move a note; target_index is where it's dropped, before the move."""
        if source == target and target_index in (source_index, source_index + 1):
            return  # dropped where it was
        text = self.columns[source].pop(source_index)
        if source == target and target_index > source_index:
            target_index -= 1
        self.columns[target].insert(target_index, text)
        self._save()
        self.emit("changed", source)
        if target != source:
            self.emit("changed", target)

    def _changed(self, title):
        self._save()
        self.emit("changed", title)

    def _load(self):
        try:
            with open(KANBAN_FILE, "r") as f:
                state = json.load(f)
            for col_data in state["columns"]:
                if col_data["title"] in self.columns:
                    self.columns[col_data["title"]] = list(col_data["notes"])
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error loading kanban: {e}")

    def _save(self):
        state = {"columns": [{"title": t, "notes": n} for t, n in self.columns.items()]}
        try:
            ensure_dir(KANBAN_FILE.parent)
            with open(KANBAN_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving kanban: {e}")


_store = None


def get_store():
    """The shell's one KanbanStore, created on first use."""
    global _store
    if _store is None:
        _store = KanbanStore()
    return _store


# The note being dragged, as (column title, index): drops move it in the store
_dragged = None


class KanbanNote(Gtk.EventBox):
    """One note of a column, shown on one board."""

    def __init__(self, column, index, text):
        super().__init__()
        self.column = column
        self.index = index
        self.text = text

        self.setup_ui()
        self.setup_dnd()
        self.connect("button-press-event", self.on_button_press)

    def setup_ui(self):
        self.box = Gtk.Box(name="kanban-note", spacing=4)
        self.label = Gtk.Label(label=self.text, xalign=0)
        self.label.set_line_wrap(True)

        self.label.set_line_wrap_mode(Gtk.WrapMode.WORD)
        
        self.delete_btn = Gtk.Button(name="kanban-btn", child=Label(name="kanban-btn-neg", markup=icons.trash))
        self.delete_btn.connect("clicked", self.on_delete_clicked)

        self.center_btn = CenterBox(orientation="v", start_children=[self.delete_btn])
        
        self.box.pack_start(self.label, True, True, 0)
        self.box.pack_start(self.center_btn, False, False, 0)
        self.add(self.box)
        self.show_all()

    def setup_dnd(self):
        self.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            [Gtk.TargetEntry.new('UTF8_STRING', Gtk.TargetFlags.SAME_APP, 0)],
            Gdk.DragAction.MOVE
        )
        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-begin", self.on_drag_begin)
        self.connect("drag-end", self.on_drag_end)

    def on_button_press(self, widget, event):
        if event.type != Gdk.EventType._2BUTTON_PRESS:
            return True
        self.start_edit()
        return False

    def on_drag_begin(self, widget, context):
        global _dragged
        _dragged = (self.column.title, self.index)
        surface = createSurfaceFromWidget(self)
        Gtk.drag_set_icon_surface(context, surface)

    def on_drag_end(self, widget, context):
        global _dragged
        _dragged = None

    def on_drag_data_get(self, widget, drag_context, data, info, time):
        data.set_text(self.label.get_text(), -1)

    def on_delete_clicked(self, button):
        self.column.store.remove(self.column.title, self.index)

    def start_edit(self):
        row = self.get_parent()
        editor = InlineEditor(self.label.get_text())

        def close_editor():
            row.remove(editor)
            row.add(self)
            row.show_all()

        def on_confirmed(editor, text):
            close_editor()
            self.column.store.edit(self.column.title, self.index, text)

        editor.connect('confirmed', on_confirmed)
        editor.connect('canceled', lambda editor: close_editor())
        
        row.remove(self)
        row.add(editor)
        row.show_all()

        GLib.timeout_add(50, lambda: (editor.text_view.grab_focus(), False))

def kanban_row(child):
    # A row that takes focus on click steals it from the editor's text
    # (GtkListBox focuses the row on release, even after a click in the text)
    row = Gtk.ListBoxRow(name="kanban-row", focus_on_click=False)
    row.add(child)
    return row


class KanbanColumn(Gtk.Frame):
    """One column of the store, shown on one board."""

    def __init__(self, store, title):
        super().__init__(name="kanban-column")
        self.store = store
        self.title = title
        self.setup_ui()
        self.setup_dnd()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.show_notes()

    def setup_ui(self):
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        
        self.add_btn = Gtk.Button(name="kanban-btn-add", child=Label(name="kanban-btn-label", markup=icons.add))
        header = CenterBox(name="kanban-header", center_children=[Label(name="column-header", label=self.title)], end_children=[self.add_btn])
        self.box.pack_start(header, False, False, 0)
        
        self.add_btn.connect("clicked", self.on_add_clicked)
        
        self.scroller = ScrolledWindow(name="scrolled-window", propagate_height=False, propagate_width=False)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.add(self.listbox)
        self.scroller.set_vexpand(True)
        
        self.box.pack_start(self.scroller, True, True, 0)
        self.add(self.box)
        self.show_all()

    def setup_dnd(self):
        self.listbox.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new('UTF8_STRING', Gtk.TargetFlags.SAME_APP, 0)],
            Gdk.DragAction.MOVE
        )
        
        self.listbox.connect("drag-data-received", self.on_drag_data_received)
        self.listbox.connect("drag-motion", self.on_drag_motion)
        self.listbox.connect("drag-leave", self.on_drag_leave)

    def show_notes(self):
        """Rebuild the rows from the store, keeping the scroll position."""
        adjustment = self.scroller.get_vadjustment()
        scrolled = adjustment.get_value()
        for row in self.listbox.get_children():
            row.destroy()
        for index, text in enumerate(self.store.notes(self.title)):
            self.listbox.add(kanban_row(KanbanNote(self, index, text)))
        self.listbox.show_all()
        GLib.idle_add(lambda: adjustment.set_value(scrolled) and False)

    def on_add_clicked(self, button):
        editor = InlineEditor()
        row = kanban_row(editor)
        self.listbox.add(row)
        self.listbox.show_all()
        editor.text_view.grab_focus()

        def scroll_to_bottom():
            adj = self.scroller.get_vadjustment()
            adj.set_value(adj.get_upper())

        # The store's change rebuilds the column, editor row included
        editor.connect('confirmed', lambda editor, text: self.store.add(self.title, text))
        editor.connect('canceled', lambda editor: row.destroy())

        GLib.idle_add(scroll_to_bottom) # ensure this is called after row is loaded

    def add_note(self, text):
        self.store.add(self.title, text)

    def get_notes(self):
        return self.store.notes(self.title)

    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        text = data.get_text()
        if not text:
            return
        row = self.listbox.get_row_at_y(y)
        index = row.get_index() if row else len(self.store.notes(self.title))
        source = _dragged

        # After the drop finishes: the move rebuilds the dragged note's column
        def drop():
            if source:
                self.store.move(*source, self.title, index)
            else:
                self.store.insert(self.title, index, text)
            return False

        GLib.idle_add(drop)

    def on_drag_motion(self, widget, drag_context, x, y, time):
        Gdk.drag_status(drag_context, Gdk.DragAction.MOVE, time)
        return True

    def on_drag_leave(self, widget, drag_context, time):
        widget.get_parent().get_parent().drag_unhighlight()

class Kanban(Gtk.Box):
    """A board of the shared notes; each monitor's dashboard has one."""

    STATE_FILE = KANBAN_FILE

    def __init__(self):
        super().__init__(name="kanban")
        self.store = get_store()
        
        self.grid = Gtk.Grid(column_spacing=4, column_homogeneous=True, row_spacing=4, row_homogeneous=True)
        self.grid.set_vexpand(True)
        self.add(self.grid)
        
        self.columns = [KanbanColumn(self.store, title) for title in COLUMNS]

        vertical_mode = True if data.PANEL_THEME == "Panel" and (data.BAR_POSITION in ["Left", "Right"] or data.PANEL_POSITION in ["Start", "End"]) else False
        
        for i, column in enumerate(self.columns):
            if vertical_mode == False:
                self.grid.attach(column, i, 0, 1, 1)
            else:
                self.grid.attach(column, 0, i, 1, 1)

        handler = self.store.connect("changed", self.on_column_changed)
        self.connect("destroy", lambda *_: self.store.disconnect(handler))
        self.show_all()

    def on_column_changed(self, _store, title):
        for column in self.columns:
            if column.title == title:
                column.show_notes()
