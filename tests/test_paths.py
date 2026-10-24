"""config/paths.py: where code and user files live."""

import importlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _restore_paths(monkeypatch):
    # Depends on monkeypatch so it tears down after the env is restored, and
    # other test modules see paths for the session's (conftest) environment
    yield
    monkeypatch.undo()
    import config.paths
    importlib.reload(config.paths)


def _reload(monkeypatch, **env):
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import config.paths
    return importlib.reload(config.paths)


def test_app_dir_is_the_code_location(monkeypatch):
    paths = _reload(monkeypatch)
    assert paths.APP_DIR == REPO
    assert (paths.APP_DIR / "main.py").is_file()


def test_user_dir_follows_xdg_config_home(monkeypatch, tmp_path):
    paths = _reload(monkeypatch, XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    assert paths.CONFIG_HOME == tmp_path / "cfg"
    assert paths.USER_DIR == tmp_path / "cfg" / "aw-shell"
    assert paths.AW_CONFIG_DIR == paths.USER_DIR / "config"
    assert paths.CONFIG_FILE == paths.USER_DIR / "config" / "config.json"
    assert paths.DOCK_FILE == paths.USER_DIR / "config" / "dock.json"
    assert paths.CSS_COLORS == paths.USER_DIR / "styles" / "colors.css"
    assert paths.USER_CSS == paths.USER_DIR / "styles" / "user.css"


@pytest.mark.parametrize("value", [None, "", "relative/dir"])
def test_invalid_xdg_falls_back_to_home(monkeypatch, tmp_path, value):
    # The XDG spec says relative paths are invalid and must be ignored
    paths = _reload(monkeypatch, HOME=str(tmp_path), XDG_CONFIG_HOME=value, XDG_CACHE_HOME=value)
    assert paths.USER_DIR == tmp_path / ".config" / "aw-shell"
    assert paths.CACHE_DIR == tmp_path / ".cache" / "aw-shell"


def test_bundled_files_come_from_app_dir(monkeypatch):
    paths = _reload(monkeypatch)
    assert paths.MAIN_CSS == REPO / "main.css"
    assert paths.MATUGEN_TEMPLATES == REPO / "config" / "matugen" / "templates"
    assert paths.HYPRLOCK_TEMPLATE == REPO / "config" / "hypr" / "hyprlock.conf"
    assert paths.SCRIPTS_DIR == REPO / "scripts"
    assert paths.DEFAULT_WALLPAPER.is_file()
    assert paths.DEFAULT_FACE_ICON.is_file()
    assert paths.DEFAULT_CSS_COLORS == REPO / "styles" / "colors.default.css"


def test_launch_command_defaults_to_the_clone_venv(monkeypatch):
    paths = _reload(monkeypatch, AW_SHELL_LAUNCH=None)
    assert paths.launch_command() == [str(REPO / ".venv" / "bin" / "python"), str(REPO / "main.py")]


def test_launch_command_from_env(monkeypatch):
    # Set by the AUR launcher and the Nix wrapper
    paths = _reload(monkeypatch, AW_SHELL_LAUNCH="/usr/bin/aw-shell --flag")
    assert paths.launch_command() == ["/usr/bin/aw-shell", "--flag"]


def test_self_updatable_needs_a_writable_git_clone(monkeypatch, tmp_path):
    paths = _reload(monkeypatch)
    monkeypatch.setattr(paths, "APP_DIR", tmp_path)
    assert not paths.self_updatable()  # no .git
    (tmp_path / ".git").mkdir()
    assert paths.self_updatable()
    monkeypatch.setattr(paths.os, "access", lambda p, mode: False)
    assert not paths.self_updatable()  # read-only, like a package install


def test_colors_css_falls_back_to_default(monkeypatch, tmp_path):
    paths = _reload(monkeypatch, XDG_CONFIG_HOME=str(tmp_path))
    assert paths.colors_css() == paths.DEFAULT_CSS_COLORS
    paths.CSS_COLORS.parent.mkdir(parents=True)
    paths.CSS_COLORS.write_text(":vars {}")
    assert paths.colors_css() == paths.CSS_COLORS


def test_data_state_runtime_follow_xdg(monkeypatch, tmp_path):
    paths = _reload(
        monkeypatch,
        XDG_DATA_HOME=str(tmp_path / "data"),
        XDG_STATE_HOME=str(tmp_path / "state"),
        XDG_RUNTIME_DIR=str(tmp_path / "run"),
    )
    assert paths.DATA_DIR == tmp_path / "data" / "aw-shell"
    assert paths.STATE_DIR == tmp_path / "state" / "aw-shell"
    assert paths.RUNTIME_DIR == tmp_path / "run" / "aw-shell"
    assert paths.KANBAN_FILE == paths.DATA_DIR / "kanban.json"
    assert paths.PINS_FILE == paths.DATA_DIR / "pins.json"
    assert paths.CALC_HISTORY == paths.STATE_DIR / "calc.json"
    assert paths.CONVERSION_HISTORY == paths.STATE_DIR / "conversion.json"
    assert paths.NOTIFICATION_HISTORY.parent == paths.NOTIFICATIONS_DIR
    assert paths.NOTIFICATIONS_DIR.parent == paths.RUNTIME_DIR
    assert paths.CAVA_FIFO.parent == paths.RUNTIME_DIR
    assert paths.REMOTE_VERSION_FILE.parent == paths.RUNTIME_DIR


@pytest.mark.parametrize("value", [None, "", "relative/dir"])
def test_data_state_runtime_fallbacks(monkeypatch, tmp_path, value):
    import os
    import tempfile

    paths = _reload(monkeypatch, HOME=str(tmp_path), XDG_DATA_HOME=value,
                    XDG_STATE_HOME=value, XDG_RUNTIME_DIR=value)
    assert paths.DATA_DIR == tmp_path / ".local" / "share" / "aw-shell"
    assert paths.STATE_DIR == tmp_path / ".local" / "state" / "aw-shell"
    # Per-user, so two users on one machine don't share it
    assert paths.RUNTIME_DIR == Path(tempfile.gettempdir()) / f"aw-shell-{os.getuid()}"


def test_ensure_dir_is_private(monkeypatch, tmp_path):
    paths = _reload(monkeypatch)
    made = paths.ensure_dir(tmp_path / "a" / "b")
    assert made.is_dir()
    # Every level it creates, not just the last (mkdir(parents=True) doesn't)
    assert made.stat().st_mode & 0o777 == 0o700
    assert made.parent.stat().st_mode & 0o777 == 0o700
    assert paths.ensure_dir(made) == made  # already there: fine


def test_user_files_cover_everything_gitignored_next_to_the_code(monkeypatch):
    """--migrate copies USER_FILES out of an old clone; a generated file that
    is gitignored but missing here would be left behind."""
    paths = _reload(monkeypatch)
    ignored = [
        line.strip() for line in (REPO / ".gitignore").read_text().splitlines()
        if line.strip().startswith(("config/", "styles/"))
    ]
    assert ignored
    assert set(ignored) <= set(paths.USER_FILES)
    assert "styles/user.css" in paths.USER_FILES
