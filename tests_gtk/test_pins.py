"""Pins: saved to ~/.local/share/aw-shell/pins.json, and clicks open, copy or clear a pin."""

import json
import os
from types import SimpleNamespace

import pytest
from conftest import pump_until
from gi.repository import Gdk, Gtk

import modules.pins as pins


@pytest.fixture(autouse=True)
def no_favicon_download(monkeypatch):
    """URL pins fetch a favicon over the network; never in tests."""
    fetched = []
    monkeypatch.setattr(pins, "download_favicon", lambda url, callback: fetched.append(url))
    return fetched


@pytest.fixture
def save_file(sandbox):
    path = sandbox.home / ".local" / "share" / "aw-shell" / "pins.json"
    assert pins.SAVE_FILE == str(path)  # never the user's real pins
    path.unlink(missing_ok=True)
    yield path
    path.unlink(missing_ok=True)


def _restart_store():
    """Drop the shell's PinStore, as a restart would; the next board loads
    a new one from the save file."""
    if pins._store is not None:
        pins._store.stop()
    pins._store = None


@pytest.fixture
def board(save_file, run_pending):
    _restart_store()
    boards = []

    def make():
        widget = pins.Pins()
        boards.append(widget)
        run_pending()
        return widget

    yield make
    for widget in boards:
        widget.destroy()
    run_pending()
    _restart_store()


def _pin(cell, content, content_type):
    cell.store.set(cell.index, content, content_type)


def _press(cell, button, double=False, state=0):
    kind = Gdk.EventType._2BUTTON_PRESS if double else Gdk.EventType.BUTTON_PRESS
    event = Gdk.Event.new(kind)
    event.button.button = button
    event.button.state = Gdk.ModifierType(state)
    return cell.on_button_press(cell, event.button)


def _clipboard():
    return Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)


@pytest.mark.parametrize("text, expected", [
    ("https://example.com", True),
    ("http://localhost:8080/path?q=1", True),
    ("ftp://192.168.1.10/file", True),
    ("example.com", False),          # no scheme
    ("just some note", False),
    ("https://", False),
])
def test_is_url(text, expected):
    assert pins.is_url(text) is expected


def test_pins_saved_and_reloaded(board, save_file, tmp_path):
    document = tmp_path / "notes.txt"
    document.write_text("hi")
    first = board()
    _pin(first.cells[0], str(document), "file")
    _pin(first.cells[2], "remember the milk", "text")

    saved = json.loads(save_file.read_text())
    assert saved[0] == {"content_type": "file", "content": str(document)}
    assert saved[2] == {"content_type": "text", "content": "remember the milk"}
    assert saved[1] == {"content_type": None, "content": None}

    _restart_store()
    second = board()
    assert (second.cells[0].content, second.cells[0].content_type) == (str(document), "file")
    assert second.cells[2].content == "remember the milk"


def test_corrupt_save_file_starts_empty(board, save_file):
    save_file.write_text("[{broken")
    assert all(cell.content is None for cell in board().cells)


def test_double_click_opens_file(sandbox, board, tmp_path):
    document = tmp_path / "report.pdf"
    document.write_bytes(b"%PDF")
    cell = board().cells[0]
    _pin(cell, str(document), "file")
    before = len(sandbox.commands())
    _press(cell, 1)  # a single click does nothing
    _press(cell, 1, double=True)
    assert pump_until(lambda: sandbox.commands()[before:] == [f"xdg-open {document}"])


def test_right_click_clears_pin(board, save_file):
    cell = board().cells[0]
    _pin(cell, "temporary", "text")
    _press(cell, 3)
    assert (cell.content, cell.content_type) == (None, None)
    assert json.loads(save_file.read_text())[0]["content"] is None


def test_click_on_text_copies_it(sandbox, board):
    cell = board().cells[0]
    _pin(cell, "ssh me@host", "text")
    before = len(sandbox.commands())
    _press(cell, 1)
    assert _clipboard().wait_for_text() == "ssh me@host"
    assert sandbox.commands()[before:] == []


def test_click_on_url_copies_and_opens(sandbox, board, no_favicon_download):
    cell = board().cells[0]
    _pin(cell, "https://example.com/docs", "text")
    assert no_favicon_download == ["https://example.com/docs"]
    before = len(sandbox.commands())
    _press(cell, 1)
    assert _clipboard().wait_for_text() == "https://example.com/docs"
    assert pump_until(lambda: sandbox.commands()[before:] == ["xdg-open https://example.com/docs"])


def test_ctrl_click_on_url_only_copies(sandbox, board):
    cell = board().cells[0]
    _pin(cell, "https://example.com", "text")
    before = len(sandbox.commands())
    _press(cell, 1, state=Gdk.ModifierType.CONTROL_MASK)
    assert _clipboard().wait_for_text() == "https://example.com"
    pump_until(lambda: False, timeout=0.3)  # give a wrongly spawned xdg-open time to log
    assert sandbox.commands()[before:] == []


class _FakeNotch(Gtk.Window):
    """Stands in for the notch, the pins board's toplevel."""

    def __init__(self):
        super().__init__()
        self.calls = []

    def close_notch(self):
        self.calls.append("close")

    def open_notch(self, name):
        self.calls.append(f"open {name}")


@pytest.fixture
def picker(monkeypatch):
    """The portal picker; answer() delivers the user's choice."""
    pending = []
    monkeypatch.setattr(pins, "pick_file", lambda title, on_done: pending.append(on_done))

    def answer(path):
        pending.pop()(path)

    answer.pending = pending
    return answer


def test_click_on_empty_cell_picks_a_file_aside_from_the_notch(board, picker, save_file, tmp_path):
    document = tmp_path / "picked.txt"
    document.write_text("hi")
    widget = board()
    notch = _FakeNotch()
    notch.add(widget)
    cell = widget.cells[0]
    _press(cell, 1)
    # The picker opens under the overlay notch, so the notch steps aside
    assert notch.calls == ["close"] and len(picker.pending) == 1
    picker(str(document))
    assert (cell.content, cell.content_type) == (str(document), "file")
    assert json.loads(save_file.read_text())[0]["content"] == str(document)
    assert notch.calls == ["close", "open pins"]
    notch.remove(widget)
    notch.destroy()


def test_cancelled_pick_leaves_cell_empty(board, picker):
    cell = board().cells[0]
    _press(cell, 1)
    picker(None)
    assert cell.content is None


def test_a_pin_shows_on_every_monitors_board(board, tmp_path):
    """One board per monitor: a pin added on one appears on the others."""
    document = tmp_path / "shared.txt"
    document.write_text("hi")
    first, second = board(), board()
    _pin(first.cells[0], str(document), "file")
    assert (second.cells[0].content, second.cells[0].content_type) == (str(document), "file")


def test_boards_dont_overwrite_each_others_pins(board, save_file):
    """Regression: each board saved its own copy, dropping the other's pins."""
    first, second = board(), board()
    _pin(first.cells[0], "from the first monitor", "text")
    _pin(second.cells[1], "from the second monitor", "text")
    saved = json.loads(save_file.read_text())
    assert [saved[0]["content"], saved[1]["content"]] == [
        "from the first monitor", "from the second monitor",
    ]
    assert first.cells[1].content == "from the second monitor"


def test_clearing_a_pin_clears_it_everywhere(board, save_file):
    first, second = board(), board()
    _pin(first.cells[0], "temporary", "text")
    _press(second.cells[0], 3)
    assert first.cells[0].content is None
    assert json.loads(save_file.read_text())[0]["content"] is None


def test_deleted_file_is_unpinned_on_every_board(board, tmp_path):
    document = tmp_path / "gone.txt"
    document.write_text("hi")
    first, second = board(), board()
    _pin(first.cells[0], str(document), "file")
    first.store.on_file_event(SimpleNamespace(event_type="deleted", src_path=str(document)))
    assert first.cells[0].content is None and second.cells[0].content is None


def test_moved_file_stays_pinned_at_its_new_path(board, save_file, tmp_path):
    old, new = tmp_path / "old.txt", tmp_path / "new.txt"
    old.write_text("hi")
    widget = board()
    _pin(widget.cells[0], str(old), "file")
    old.rename(new)
    widget.store.on_file_event(
        SimpleNamespace(event_type="moved", src_path=str(old), dest_path=str(new))
    )
    assert widget.cells[0].content == str(new)
    assert json.loads(save_file.read_text())[0]["content"] == str(new)


def test_a_closed_board_stops_listening(board, run_pending):
    first, second = board(), board()
    second.destroy()
    run_pending()
    _pin(first.cells[0], "still works", "text")
    assert first.cells[0].content == "still works"


def test_cells_built_when_first_shown(board):
    """30 cells per monitor took ~0.06 s of every start; most starts never
    open the Pins tab."""
    from gi.repository import Gtk

    widget = board()
    assert widget._cells is None
    host = Gtk.OffscreenWindow()
    host.add(widget)
    host.show_all()
    assert widget._cells is not None and len(widget._cells) == pins.SLOTS
    host.remove(widget)
    host.destroy()


def test_cells_built_on_first_use(board):
    assert len(board().cells) == pins.SLOTS


_download_favicon = pins.download_favicon  # the real one; the fixture above replaces it


def test_favicon_download_reports_the_saved_file(monkeypatch):
    fetched, results = [], []
    monkeypatch.setattr(pins.urllib.request, "urlretrieve",
                        lambda url, path: fetched.append(url))
    _download_favicon("https://example.org/some/page", results.append)
    assert pump_until(lambda: results), "download thread never reported back"
    assert fetched == ["https://example.org/favicon.ico"]
    assert results[0].endswith(".ico")
    os.remove(results[0])
