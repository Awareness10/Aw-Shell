"""Notification history: what ends up in it, and what survives a restart."""

import json
from datetime import datetime, timedelta

import pytest
from conftest import close_notification, notify, pump, pump_until
from gi.repository import Gio

import modules.notifications as notifications


@pytest.fixture
def history_file(sandbox):
    path = notifications.PERSISTENT_HISTORY_FILE
    assert path.startswith(str(sandbox.root))  # redirected away from /tmp/aw-shell
    if notifications.os.path.exists(path):
        notifications.os.remove(path)
    yield path
    if notifications.os.path.exists(path):
        notifications.os.remove(path)


@pytest.fixture
def shell(history_file):
    """A popup container and its history panel, as the notch builds them."""
    history = notifications.NotificationHistory()
    container = notifications.NotificationContainer(history)
    pump()
    yield container, history
    container.destroy()
    history.destroy()
    pump()


def _saved(history_file):
    with open(history_file) as f:
        return json.load(f)


def _write(history_file, notes):
    with open(history_file, "w") as f:
        json.dump(notes, f)


def _note(i, app="app"):
    stamp = datetime(2026, 10, 1, 12, 0) - timedelta(minutes=i)
    return {"id": f"note-{i}", "app_icon": "", "summary": f"summary {i}", "body": "",
            "app_name": app, "timestamp": stamp.isoformat(), "cached_image_path": None}


def _closed_signals():
    """NotificationClosed (id, reason) signals the server sends to apps."""
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    received = []
    bus.signal_subscribe(
        None, "org.freedesktop.Notifications", "NotificationClosed",
        "/org/freedesktop/Notifications", None, Gio.DBusSignalFlags.NONE,
        lambda *args: received.append(args[5].unpack()),
    )
    return received


def test_withdrawn_notification_moves_to_history(shell, history_file):
    container, history = shell
    closed = _closed_signals()
    nid = notify("Build finished", "all green", app_name="ci")
    assert pump_until(lambda: len(container.notifications) == 1)

    close_notification(nid)
    # Well within the 5 s display timeout, so this isn't just expiry
    assert pump_until(lambda: len(history.containers) == 1, timeout=2)
    assert pump_until(lambda: (nid, 3) in closed)  # 3: closed by CloseNotification
    assert container.notifications == []
    saved = _saved(history_file)
    assert [(n["summary"], n["body"], n["app_name"]) for n in saved] == \
        [("Build finished", "all green", "ci")]


def test_expired_notification_moves_to_history(shell):
    container, history = shell
    notify("Battery low")
    assert pump_until(lambda: len(container.notifications) == 1)
    container.notifications[0].close_notification()  # what its timeout runs
    assert pump_until(lambda: len(history.containers) == 1)


def test_dismissed_notification_is_not_kept(shell, history_file):
    container, history = shell
    notify("Seen it")
    assert pump_until(lambda: len(container.notifications) == 1)
    container.notifications[0].close_button.clicked()
    assert pump_until(lambda: container.notifications == [])
    pump()
    assert history.containers == []
    assert not notifications.os.path.exists(history_file)


def test_do_not_disturb_goes_straight_to_history(shell):
    container, history = shell
    history.do_not_disturb_enabled = True
    notify("Quiet please")
    assert pump_until(lambda: len(history.containers) == 1)
    assert container.notifications == []


def test_ignored_app_is_not_kept(shell, monkeypatch):
    container, history = shell
    monkeypatch.setattr(notifications, "get_history_ignored_apps", lambda: ["spam"])
    history.do_not_disturb_enabled = True
    notify("Buy now", app_name="spam")
    notify("Real one", app_name="mail")
    assert pump_until(lambda: len(history.containers) == 1)
    assert [n["app_name"] for n in history.persistent_notifications] == ["mail"]


def test_history_reloads_on_start(history_file):
    _write(history_file, [_note(0), _note(1), _note(2)])
    history = notifications.NotificationHistory()
    try:
        assert pump_until(lambda: len(history.containers) == 3)
        assert [n["id"] for n in history.persistent_notifications] == \
            ["note-0", "note-1", "note-2"]
    finally:
        history.destroy()
        pump()


def test_history_keeps_newest_50(shell, history_file):
    _write(history_file, [_note(i) for i in range(50)])
    container, _ = shell
    history = notifications.NotificationHistory()  # loads the 50
    container.notification_history = history
    try:
        assert pump_until(lambda: len(history.containers) == 50)
        history.do_not_disturb_enabled = True
        notify("Newest")
        assert pump_until(lambda: history.persistent_notifications[0]["summary"] == "Newest")
        saved = _saved(history_file)
        assert len(saved) == 50
        assert saved[0]["summary"] == "Newest"
        assert "note-49" not in [n["id"] for n in saved]  # oldest dropped
    finally:
        history.destroy()
        pump()


def test_clear_history_deletes_file(shell, history_file):
    _, history = shell
    history.do_not_disturb_enabled = True
    notify("Something")
    assert pump_until(lambda: len(history.containers) == 1)
    history.clear_history()
    assert history.containers == []
    assert not notifications.os.path.exists(history_file)
