"""utils/notification_history.py: the history file, date headers, orphans."""

import json
from datetime import datetime

import pytest

from utils.notification_history import (
    HISTORY_LIMIT,
    HistoryStore,
    date_header,
    image_file_name,
    ordinal,
    orphan_images,
    parse_timestamp,
)


def _note(i):
    return {"id": f"id-{i}", "app_icon": "", "summary": f"s{i}", "body": "",
            "app_name": "app", "timestamp": "2026-10-01T12:00:00",
            "cached_image_path": None}


@pytest.mark.parametrize("n, suffix", [
    (1, "st"), (2, "nd"), (3, "rd"), (4, "th"), (11, "th"), (12, "th"), (13, "th"),
    (21, "st"), (22, "nd"), (23, "rd"), (31, "st"), (111, "th"),
])
def test_ordinal(n, suffix):
    assert ordinal(n) == suffix


NOW = datetime(2026, 11, 15, 0, 30)


@pytest.mark.parametrize("dt, header", [
    (datetime(2026, 11, 15, 0, 0), "Today"),
    (datetime(2026, 11, 14, 23, 59), "Yesterday"),  # across midnight
    (datetime(2026, 11, 13, 12, 0), "November 13th"),
    (datetime(2026, 1, 1, 12, 0), "January 1st"),
    (datetime(2025, 12, 22, 12, 0), "December 22nd, 2025"),
])
def test_date_header(dt, header):
    assert date_header(dt, now=NOW) == header


def test_orphan_images_keeps_history_images_and_other_files():
    names = [image_file_name("a"), image_file_name("b"), "notification_x.jpg", "other.png"]
    assert orphan_images(names, ["a", None]) == [image_file_name("b")]


def test_parse_timestamp_falls_back_to_now():
    assert parse_timestamp("2026-10-01T12:34:00") == datetime(2026, 10, 1, 12, 34)
    for bad in (None, "", "yesterday"):
        assert abs((parse_timestamp(bad) - datetime.now()).total_seconds()) < 5


def test_store_reads_and_writes_the_file_format(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps([_note(1)]))
    store = HistoryStore(str(path))
    assert store.load() == [_note(1)]
    store.add(_note(2))
    assert json.loads(path.read_text()) == [_note(2), _note(1)]  # newest first


@pytest.mark.parametrize("content", [None, "", "{not json", '{"a": 1}'])
def test_store_treats_a_missing_or_broken_file_as_empty(tmp_path, content):
    path = tmp_path / "history.json"
    if content is not None:
        path.write_text(content)
    assert HistoryStore(str(path)).load() == []


def test_store_keeps_the_newest_notes(tmp_path):
    store = HistoryStore(str(tmp_path / "history.json"))
    for i in range(HISTORY_LIMIT + 5):
        store.add(_note(i))
    assert len(store.notes) == HISTORY_LIMIT
    assert store.notes[0]["id"] == f"id-{HISTORY_LIMIT + 4}"


def test_store_removes_by_id_compared_as_text(tmp_path):
    path = tmp_path / "history.json"
    store = HistoryStore(str(path))
    store.notes = [_note(1), _note(2) | {"id": 7}]
    assert store.remove(["7"]) is True
    assert [n["id"] for n in json.loads(path.read_text())] == ["id-1"]
    assert store.remove(["missing"]) is False


def test_store_clear_deletes_the_file(tmp_path):
    path = tmp_path / "history.json"
    store = HistoryStore(str(path))
    store.add(_note(1))
    store.clear()
    assert store.notes == [] and not path.exists()
    store.clear()  # no file: fine
