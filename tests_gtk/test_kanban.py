"""Kanban notes are saved to ~/.kanban.json and survive a rebuild."""

import json

import pytest


@pytest.fixture
def state_file(sandbox):
    from modules.kanban import Kanban

    path = Kanban.STATE_FILE
    assert path.parent == sandbox.home  # never the user's real board
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
