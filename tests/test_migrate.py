"""config/migrate.py: old installs (a clone or a dev symlink at
~/.config/aw-shell) move to the new layout without losing anything."""

from datetime import date
from unittest.mock import patch

import pytest

from config.migrate import MigrationError, main, migrate, old_install_notice

TODAY = date(2026, 10, 24)


def _clone(path, settings='{"bar_theme": "Dense"}'):
    """An old-style install: code plus the user's files next to it."""
    (path / "config" / "hypr").mkdir(parents=True)
    (path / "styles").mkdir()
    (path / "main.py").write_text("# shell")
    (path / "config" / "config.json").write_text(settings)
    (path / "config" / "hypr" / "colors.lua").write_text("return {}")
    (path / "styles" / "colors.css").write_text(":vars {}")
    (path / "my-edit.py").write_text("# a user's own change")
    return path


@pytest.fixture
def home(tmp_path):
    (tmp_path / ".config").mkdir()
    return tmp_path


def test_dev_symlink_becomes_a_real_folder(home):
    repo = _clone(home / "repo")
    user_dir = home / ".config" / "aw-shell"
    user_dir.symlink_to(repo)
    lines = migrate(user_dir, app_dir=repo, today=TODAY)
    assert not user_dir.is_symlink() and user_dir.is_dir()
    assert (user_dir / "config" / "config.json").read_text() == '{"bar_theme": "Dense"}'
    assert (user_dir / "styles" / "colors.css").exists()
    assert not (user_dir / "main.py").exists()  # only user files
    assert (repo / "main.py").exists() and (repo / "config" / "config.json").exists()
    assert any("config/config.json" in line for line in lines)


def test_old_clone_is_kept_as_a_backup(home):
    user_dir = _clone(home / ".config" / "aw-shell")
    package = home / "usr-share-aw-shell"
    package.mkdir()
    migrate(user_dir, app_dir=package, today=TODAY)
    backup = home / ".config" / "aw-shell.bak-2026-10-24"
    assert (backup / "my-edit.py").exists()  # user edits kept
    assert (backup / "config" / "config.json").exists()
    assert (user_dir / "config" / "config.json").read_text() == '{"bar_theme": "Dense"}'
    assert not (user_dir / "main.py").exists()


def test_backup_name_never_reused(home):
    user_dir = _clone(home / ".config" / "aw-shell")
    (home / ".config" / "aw-shell.bak-2026-10-24").mkdir()
    migrate(user_dir, app_dir=home / "pkg", today=TODAY)
    assert (home / ".config" / "aw-shell.bak-2026-10-24-2" / "main.py").exists()


def test_refuses_to_move_the_running_clone(home):
    user_dir = _clone(home / ".config" / "aw-shell")
    with pytest.raises(MigrationError, match="install.sh"):
        migrate(user_dir, app_dir=user_dir, today=TODAY)
    assert (user_dir / "main.py").exists()  # untouched


def test_clone_moved_by_install_sh(home):
    moved = _clone(home / ".local" / "src" / "aw-shell")
    user_dir = home / ".config" / "aw-shell"
    migrate(user_dir, app_dir=moved, today=TODAY)
    assert (user_dir / "config" / "config.json").read_text() == '{"bar_theme": "Dense"}'
    assert (user_dir / "config" / "hypr" / "colors.lua").exists()


def test_never_overwrites(home):
    moved = _clone(home / "src")
    user_dir = home / ".config" / "aw-shell"
    (user_dir / "styles").mkdir(parents=True)
    (user_dir / "styles" / "colors.css").write_text("mine")
    migrate(user_dir, app_dir=moved, today=TODAY)
    assert (user_dir / "styles" / "colors.css").read_text() == "mine"
    assert (user_dir / "config" / "config.json").exists()  # missing ones still copied


def test_nothing_to_do(home):
    user_dir = home / ".config" / "aw-shell"
    (user_dir / "config").mkdir(parents=True)
    (user_dir / "config" / "config.json").write_text("{}")
    assert migrate(user_dir, app_dir=home / "pkg", today=TODAY) == []
    assert migrate(home / ".config" / "fresh", app_dir=home / "pkg", today=TODAY) == []


@pytest.mark.parametrize("error, code", [(None, 0), (MigrationError("no"), 1)])
def test_main_runs_every_step(tmp_path, capsys, error, code):
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")
    with patch("config.migrate.migrate", side_effect=error, return_value=["Copied x"]), \
            patch("config.migrate.move_legacy_files", return_value=[]) as legacy, \
            patch("config.migrate.write_generated_config") as generated, \
            patch("config.migrate.paths.CONFIG_FILE", config_file):
        assert main() == code
    out = capsys.readouterr().out
    if error:
        assert "no" in out
        legacy.assert_not_called()
    else:
        assert "Copied x" in out and "Restart" in out
        legacy.assert_called_once_with()
        generated.assert_called_once_with()


def test_main_skips_generated_config_without_settings(tmp_path):
    with patch("config.migrate.migrate", return_value=[]), \
            patch("config.migrate.move_legacy_files", return_value=[]), \
            patch("config.migrate.write_generated_config") as generated, \
            patch("config.migrate.paths.CONFIG_FILE", tmp_path / "missing.json"):
        assert main() == 0
    generated.assert_not_called()


def test_notice_for_an_old_clone_next_to_a_new_install(home):
    user_dir = _clone(home / ".config" / "aw-shell")
    assert "--migrate" in old_install_notice(user_dir, app_dir=home / "pkg")
    assert old_install_notice(user_dir, app_dir=user_dir) is None  # it is the install


def test_no_notice_in_dev_mode_or_when_clean(home):
    repo = _clone(home / "repo")
    link = home / ".config" / "aw-shell"
    link.symlink_to(repo)
    assert old_install_notice(link, app_dir=repo) is None
    assert old_install_notice(home / ".config" / "clean", app_dir=repo) is None
