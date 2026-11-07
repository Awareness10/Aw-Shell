"""Kanban notes are saved to ~/.local/share/aw-shell/kanban.json and survive a rebuild."""

import json

import pytest


@pytest.fixture
def state_file(sandbox):
    from modules.kanban import Kanban

    path = Kanban.STATE_FILE
    assert path.parent == sandbox.home / ".local" / "share" / "aw-shell"  # not the real board
    path.unlink(missing_ok=True)
    yield path
    path.unlink(missing_ok=True)


def _restart_store():
    """Drop the shell's KanbanStore, as a restart would; the next board loads
    a new one from the state file."""
    import modules.kanban as kanban

    kanban._store = None


@pytest.fixture
def board(state_file, run_pending):
    from modules.kanban import Kanban

    _restart_store()
    boards = []

    def make():
        kanban = Kanban()
        boards.append(kanban)
        run_pending()
        return kanban

    yield make
    for kanban in boards:
        kanban.destroy()
    run_pending()
    _restart_store()


def _notes(kanban):
    return {column.title: column.get_notes() for column in kanban.columns}


def test_notes_saved_and_reloaded(board, state_file):
    first = board()
    todo, doing, done = first.columns
    todo.add_note("write tests")
    todo.add_note("fix bugs")
    done.add_note("ruff")

    saved = json.loads(state_file.read_text())
    assert [c["notes"] for c in saved["columns"]] == [["write tests", "fix bugs"], [], ["ruff"]]
    _restart_store()
    assert _notes(board()) == {"To Do": ["write tests", "fix bugs"], "In Progress": [],
                               "Done": ["ruff"]}


def test_destroying_the_board_keeps_saved_notes(board, state_file, run_pending):
    """Rows emit 'changed' as they're destroyed; tearing down the widget (its
    notch goes away with a monitor) must not save an emptied board."""
    kanban = board()
    kanban.columns[0].add_note("keep me")
    kanban.destroy()
    run_pending()
    saved = json.loads(state_file.read_text())
    assert saved["columns"][0]["notes"] == ["keep me"]


def test_missing_file_starts_empty(board):
    assert _notes(board()) == {"To Do": [], "In Progress": [], "Done": []}


def test_corrupt_file_starts_empty_and_is_left_alone(board, state_file):
    state_file.write_text("{not json")
    assert _notes(board()) == {"To Do": [], "In Progress": [], "Done": []}
    assert state_file.read_text() == "{not json"


TEXT = "buy milk and eggs from the store tomorrow morning and some bread "


def _settle():
    from conftest import pump_until

    pump_until(lambda: False, 0.3)  # let the compositor configure the resized window


@pytest.fixture
def notch(board):
    """The board in an auto-sized layer-shell window like the notch, with the
    dashboard's size request and the real stylesheet."""
    from fabric.utils.helpers import compile_css
    from gi.repository import Gdk, Gtk

    import config.paths as paths
    from utils.stylesheet import build_stylesheet
    from widgets.wayland import WaylandWindow

    provider = Gtk.CssProvider()
    provider.load_from_data(compile_css(build_stylesheet(), base_path=str(paths.APP_DIR)).encode())
    screen = Gdk.Screen.get_default()
    Gtk.StyleContext.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    kanban = board()
    dashboard = Gtk.Box(name="dashboard")
    dashboard.set_size_request(1093, 472)
    dashboard.pack_start(kanban, True, True, 0)
    window = WaylandWindow(anchor="top", layer="top", keyboard_mode="on-demand", child=dashboard)
    window.show_all()
    _settle()
    yield window, kanban
    window.destroy()
    Gtk.StyleContext.remove_provider_for_screen(screen, provider)


def _new_todo(kanban):
    column = kanban.columns[0]
    column.on_add_clicked(column.add_btn)
    _settle()
    return column.listbox.get_children()[-1].get_children()[0]


def _display_lines(text_view):
    it = text_view.get_buffer().get_start_iter()
    lines = 1
    while text_view.forward_display_line(it):
        lines += 1
    return lines


def test_typing_a_todo_keeps_the_notch_size(notch):
    """The editor's width must not follow its text: a long line wrapped
    nowhere and the notch grew with every word."""
    window, kanban = notch
    editor = _new_todo(kanban)
    width = window.get_size().width
    buffer = editor.text_view.get_buffer()
    for i, char in enumerate(TEXT * 3):
        buffer.insert_at_cursor(char)
        if i % 16 == 15:
            _settle()
            assert window.get_size().width == width, f"notch resized after {i + 1} chars"
    assert _display_lines(editor.text_view) > 2  # wrapped instead


def test_long_todo_grows_the_editor_instead_of_scrolling(notch):
    """A fixed-height editor showed a scrollbar after two lines, taking width
    from the text (an empty box next to the buttons) and rewrapping it."""
    window, kanban = notch
    editor = _new_todo(kanban)
    editor.text_view.get_buffer().set_text(TEXT * 3)
    _settle()
    assert _display_lines(editor.text_view) > 2
    adjustment = editor.text_view.props.vadjustment
    assert adjustment.get_upper() <= adjustment.get_page_size()  # all of it shown


def test_confirming_a_todo_keeps_the_notch_size(notch):
    window, kanban = notch
    editor = _new_todo(kanban)
    width = window.get_size().width
    buffer = editor.text_view.get_buffer()
    for i, char in enumerate(TEXT * 2):
        buffer.insert_at_cursor(char)
        if i % 16 == 15:
            _settle()
    typed_width = window.get_size().width
    editor.on_confirm(None)
    _settle()
    assert window.get_size().width == typed_width == width
    assert kanban.columns[0].get_notes() == [(TEXT * 2).strip()]



def _click(window, widget, x, y):
    """Button 1 press + release at (x, y) in widget, on the GdkWindow there
    (the headless compositor has no pointer, so events go straight to GTK)."""
    from gi.repository import Gdk, Gtk

    x, y = widget.translate_coordinates(window, x, y)
    target = window.get_window()
    while child := next((c for c in reversed(target.get_children()) if c.is_visible()
                         and 0 <= x - c.get_position()[0] < c.get_width()
                         and 0 <= y - c.get_position()[1] < c.get_height()), None):
        target, x, y = child, x - child.get_position()[0], y - child.get_position()[1]
    for kind in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE):
        event = Gdk.Event.new(kind)
        event.button.window = target
        event.button.x, event.button.y = float(x), float(y)
        event.button.button = 1
        event.set_device(Gdk.Display.get_default().get_default_seat().get_pointer())
        Gtk.main_do_event(event)
    _settle()


def test_clicking_the_editor_keeps_typing_in_it(notch):
    """A click below the buttons, or in the text, focused the list row
    instead (GtkListBox's focus on click), and typing stopped."""
    window, kanban = notch
    editor = _new_todo(kanban)
    buttons = editor.button_box.get_allocation()
    _click(window, editor.button_box, buttons.width // 2, buttons.height + 6)
    assert window.get_focus() is editor.text_view
    _click(window, editor.text_view, 20, 10)
    assert window.get_focus() is editor.text_view


def test_note_text_is_left_aligned(notch):
    """Wrapped lines are narrower than the label, which centered them."""
    window, kanban = notch
    kanban.columns[0].add_note("Fix the issue with screenrecorder not recording from the screen")
    _settle()
    label = kanban.columns[0].listbox.get_children()[0].get_children()[0].label
    assert label.get_layout().get_line_count() > 1
    assert label.get_layout_offsets().x == label.get_allocation().x


def _shown(column):
    """The note texts a column's rows show."""
    return [row.get_children()[0].label.get_text() for row in column.listbox.get_children()]


def test_every_monitors_board_shows_the_same_notes(board, state_file):
    """One board per monitor: a note added, edited or deleted on one shows on all."""
    first, second = board(), board()
    first.columns[0].add_note("from the first monitor")
    second.columns[2].add_note("from the second monitor")
    for kanban in (first, second):
        assert _shown(kanban.columns[0]) == ["from the first monitor"]
        assert _shown(kanban.columns[2]) == ["from the second monitor"]
    saved = json.loads(state_file.read_text())
    assert [c["notes"] for c in saved["columns"]] == [
        ["from the first monitor"], [], ["from the second monitor"],
    ]

    note = second.columns[0].listbox.get_children()[0].get_children()[0]
    note.on_delete_clicked(note.delete_btn)
    assert _shown(first.columns[0]) == []


@pytest.mark.parametrize("source, target, expected", [
    (("To Do", 0), ("Done", 0), {"To Do": ["b", "c"], "Done": ["a"]}),
    (("To Do", 0), ("To Do", 3), {"To Do": ["b", "c", "a"], "Done": []}),  # dropped at the end
    (("To Do", 2), ("To Do", 0), {"To Do": ["c", "a", "b"], "Done": []}),
    (("To Do", 1), ("To Do", 2), {"To Do": ["a", "b", "c"], "Done": []}),  # right below itself
])
def test_moving_a_note(board, source, target, expected):
    kanban = board()
    for text in "abc":
        kanban.columns[0].add_note(text)
    kanban.store.move(*source, *target)
    assert {t: kanban.store.notes(t) for t in ("To Do", "Done")} == expected
    assert _shown(kanban.columns[0]) == expected["To Do"]


def test_dropping_a_note_on_the_other_monitors_board_moves_it(board, run_pending, monkeypatch):
    from types import SimpleNamespace

    import modules.kanban as kanban_module

    first, second = board(), board()
    first.columns[0].add_note("drag me")
    monkeypatch.setattr(kanban_module, "_dragged", ("To Do", 0))  # set by drag-begin
    target = second.columns[1]
    target.on_drag_data_received(target.listbox, None, 0, 0,
                                 SimpleNamespace(get_text=lambda: "drag me"), 0, 0)
    run_pending()
    assert _shown(first.columns[0]) == [] and _shown(first.columns[1]) == ["drag me"]
