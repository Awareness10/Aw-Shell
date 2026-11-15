"""History rows: what a row shows, for a notification that moved to history
this session and for one restored from the history file, and what its close
button does."""

import json

import pytest
from conftest import _call_notifications, notify, pump, pump_until
from gi.repository import GLib

import modules.notifications as notifications


@pytest.fixture
def history_file(sandbox):
    path = notifications.PERSISTENT_HISTORY_FILE
    if notifications.os.path.exists(path):
        notifications.os.remove(path)
    yield path
    if notifications.os.path.exists(path):
        notifications.os.remove(path)


@pytest.fixture
def shell(history_file):
    history = notifications.NotificationHistory()
    container = notifications.NotificationContainer(history)
    pump()
    yield container, history
    container.destroy()
    history.destroy()
    pump()


def _walk(widget):
    yield widget
    if hasattr(widget, "get_children"):
        for child in widget.get_children():
            yield from _walk(child)


def _named(widget, name):
    return [w for w in _walk(widget) if w.get_name() == name]


def _label(widget, name):
    (label,) = _named(widget, name)
    return label.get_label()


def _row_content(row):
    """What a history row shows."""
    body = [w for w in _walk(row) if w.get_name() == "notification-body"]
    return {
        "summary": _label(row, "notification-summary"),
        "app": _label(row, "notification-app-name"),
        "time": _label(row, "notification-timestamp"),
        "body": body[0].get_label() if body else None,
        "images": len(_named(row, "notification-image")),
        "close_buttons": len(_named(row, "notif-close-button")),
        "separators": len(_named(row, "notif-sep")),
        "framed": len(_named(row, "notification-box-hist")),
    }


def _saved(history_file):
    with open(history_file) as f:
        return json.load(f)


def _move_to_history(container, history, summary, body=""):
    notify(summary, body=body, app_name="mail")
    assert pump_until(lambda: len(container.notifications) == 1)
    container.notifications[0].close_notification()  # expires -> history
    assert pump_until(lambda: len(history.containers) == 1)
    return history.containers[0]


def test_row_for_a_notification_moved_to_history(shell):
    container, history = shell
    row = _move_to_history(container, history, "Hello", body="World")
    time = row.arrival_time.strftime("%H:%M")
    assert _row_content(row) == {
        "summary": "Hello", "app": "mail", "time": time, "body": "World",
        "images": 0, "close_buttons": 1, "separators": 2, "framed": 1,
    }


def test_row_restored_from_the_history_file(history_file):
    with open(history_file, "w") as f:
        json.dump([{"id": "note-1", "app_icon": "", "summary": "Hello", "body": "World",
                    "app_name": "mail", "timestamp": "2026-10-01T12:34:00",
                    "cached_image_path": None}], f)
    history = notifications.NotificationHistory()
    try:
        assert pump_until(lambda: len(history.containers) == 1)
        assert _row_content(history.containers[0]) == {
            "summary": "Hello", "app": "mail", "time": "12:34", "body": "World",
            "images": 0, "close_buttons": 1, "separators": 2, "framed": 1,
        }
    finally:
        history.destroy()
        pump()


def test_closing_a_restored_row_removes_it_from_the_file(history_file):
    notes = [{"id": f"note-{i}", "app_icon": "", "summary": f"s{i}", "body": "",
              "app_name": "mail", "timestamp": "2026-10-01T12:00:00",
              "cached_image_path": None} for i in range(2)]
    with open(history_file, "w") as f:
        json.dump(notes, f)
    history = notifications.NotificationHistory()
    try:
        assert pump_until(lambda: len(history.containers) == 2)
        row = next(c for c in history.containers
                   if _label(c, "notification-summary") == "s0")
        _named(row, "notif-close-button")[0].clicked()
        pump()
        assert [n["id"] for n in _saved(history_file)] == ["note-1"]
        assert [_label(c, "notification-summary") for c in history.containers] == ["s1"]
    finally:
        history.destroy()
        pump()


def test_closing_a_row_moved_to_history_removes_it_everywhere(shell, history_file):
    """It used to stay in the file (back after a restart) and its close
    handler ran twice, the second time raising."""
    container, history = shell
    row = _move_to_history(container, history, "Hello")
    assert [n["summary"] for n in _saved(history_file)] == ["Hello"]
    _named(row, "notif-close-button")[0].clicked()
    pump()
    assert history.containers == []
    assert _saved(history_file) == []


def test_notification_with_a_missing_image_file_still_shows(shell):
    """An app's image-path hint pointing at a file that doesn't exist made
    the box raise while being built, so the notification never appeared."""
    container, history = shell
    hints = {"image-path": GLib.Variant("s", "/nonexistent/aw-shell-test.png")}
    args = GLib.Variant("(susssasa{sv}i)", ("mail", 0, "", "Hi", "", [], hints, -1))
    _call_notifications("Notify", args)
    assert pump_until(lambda: len(container.notifications) == 1)
    assert _named(container.notifications[0], "notification-image") == []
    container.notifications[0].close_notification()
    assert pump_until(lambda: len(history.containers) == 1)
