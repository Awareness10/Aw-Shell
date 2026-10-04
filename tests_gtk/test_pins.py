"""Pins: saved to ~/.pins.json, and clicks open, copy or clear a pin."""

import json

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
    path = sandbox.home / ".pins.json"
    assert pins.SAVE_FILE == str(path)  # never the user's real pins
    path.unlink(missing_ok=True)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def board(save_file, run_pending):
    boards = []

    def make():
        widget = pins.Pins()
        boards.append(widget)
        run_pending()
        return widget

    yield make
    for widget in boards:
        widget.observer.stop()
        widget.destroy()
    run_pending()


def _pin(cell, content, content_type):
    cell.content, cell.content_type = content, content_type
    cell.update_display()


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
