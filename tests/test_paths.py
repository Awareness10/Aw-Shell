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
