"""config/legacy.py: files older versions kept elsewhere move to their new place."""

from pathlib import Path

import config.paths as paths
from config.legacy import LEGACY_FILES, move_legacy_files


def test_moves_when_only_the_old_file_exists(tmp_path):
    old, new = tmp_path / ".kanban.json", tmp_path / "data" / "aw-shell" / "kanban.json"
    old.write_text('{"columns": []}')
    assert move_legacy_files([(old, new)]) == [(old, new)]
    assert not old.exists()
    assert new.read_text() == '{"columns": []}'


def test_never_overwrites(tmp_path):
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text("old")
    new.write_text("new")
    assert move_legacy_files([(old, new)]) == []
    assert old.read_text() == "old"
    assert new.read_text() == "new"


def test_nothing_to_move(tmp_path):
    old, new = tmp_path / "old.json", tmp_path / "sub" / "new.json"
    assert move_legacy_files([(old, new)]) == []
    assert not new.parent.exists()


def test_a_failed_move_does_not_stop_the_rest(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where a folder should be")
    bad_old, bad_new = tmp_path / "a.json", blocker / "a.json"
    good_old, good_new = tmp_path / "b.json", tmp_path / "ok" / "b.json"
    bad_old.write_text("a")
    good_old.write_text("b")
    assert move_legacy_files([(bad_old, bad_new), (good_old, good_new)]) == [(good_old, good_new)]
    assert bad_old.read_text() == "a"  # left where it was
    assert good_new.read_text() == "b"


def test_known_old_locations():
    home = Path.home()
    assert (home / ".kanban.json", paths.KANBAN_FILE) in LEGACY_FILES
    assert (home / ".pins.json", paths.PINS_FILE) in LEGACY_FILES
    assert (paths.CACHE_DIR / "calc.json", paths.CALC_HISTORY) in LEGACY_FILES
    assert (paths.CACHE_DIR / "conversion.json", paths.CONVERSION_HISTORY) in LEGACY_FILES
    old_history = Path("/tmp/aw-shell/notifications/notification_history.json")
    assert (old_history, paths.NOTIFICATION_HISTORY) in LEGACY_FILES
