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


@pytest.fixture
def board(state_file, run_pending):
    from modules.kanban import Kanban

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
