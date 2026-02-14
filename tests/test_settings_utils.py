"""Tests for config/settings_utils.py — bind_vars management, config generation, file ops."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from config.settings_utils import (
    get_bind_var,
    set_bind_var,
    set_all_bind_vars,
    reset_to_defaults,
    load_bind_vars,
    save_bind_vars,
    get_available_monitors,
    apply_and_restart,
    ensure_matugen_config,
    ensure_face_icon,
    start_config,
    generate_hyprconf,
    deep_update,
    backup_and_replace,
    bind_vars,
)
from config.settings_constants import DEFAULTS


@pytest.fixture(autouse=True)
def reset_bind_vars():
    """Reset bind_vars to defaults before each test."""
    bind_vars.clear()
    bind_vars.update(DEFAULTS.copy())
    yield
    bind_vars.clear()


# =========================================================================
# get_bind_var / set_bind_var / set_all_bind_vars
# =========================================================================

class TestBindVarAccessors:

    def test_get_existing_key(self):
        assert get_bind_var("bar_position") == "Top"

    def test_get_with_explicit_default(self):
        assert get_bind_var("nonexistent_key", "fallback") == "fallback"

    def test_get_falls_back_to_DEFAULTS(self):
        # Key in DEFAULTS but not overridden
        assert get_bind_var("bar_theme") == "Pills"

    def test_set_bind_var(self):
        set_bind_var("bar_position", "Bottom")
        assert get_bind_var("bar_position") == "Bottom"

    def test_set_all_replaces_everything(self):
        set_all_bind_vars({"only_key": "only_value"})
        assert get_bind_var("only_key") == "only_value"
        assert get_bind_var("bar_position", "missing") == "missing"

    def test_get_nested_dict(self):
        assert isinstance(get_bind_var("metrics_visible"), dict)
        assert get_bind_var("metrics_visible")["cpu"] is True


# =========================================================================
# reset_to_defaults
# =========================================================================

class TestResetToDefaults:

    def test_resets_modified_values(self):
        set_bind_var("bar_position", "Left")
        set_bind_var("custom_key", "custom_value")
        reset_to_defaults()
        assert get_bind_var("bar_position") == "Top"
        assert get_bind_var("custom_key", "gone") == "gone"

    def test_reset_matches_DEFAULTS(self):
        set_bind_var("bar_theme", "Dense")
        reset_to_defaults()
        for key, value in DEFAULTS.items():
            assert get_bind_var(key) == value


# =========================================================================
# load_bind_vars
# =========================================================================

class TestLoadBindVars:

    def test_loads_defaults_when_no_file(self, tmp_path):
        config_file = tmp_path / "config.json"
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        assert get_bind_var("bar_position") == "Top"
        assert get_bind_var("bar_theme") == "Pills"

    def test_merges_saved_over_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"bar_position": "Bottom", "custom": 42}))
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        assert get_bind_var("bar_position") == "Bottom"
        assert get_bind_var("custom") == 42
        # Defaults still present for unset keys
        assert get_bind_var("bar_theme") == "Pills"

    def test_handles_invalid_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json{{{")
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        # Should fall back to defaults
        assert get_bind_var("bar_position") == "Top"

    def test_ensures_nested_metrics_structure(self, tmp_path):
        config_file = tmp_path / "config.json"
        # Save config with metrics_visible as a non-dict (corrupt)
        config_file.write_text(json.dumps({"metrics_visible": "broken"}))
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        # Should restore the default dict structure
        mv = get_bind_var("metrics_visible")
        assert isinstance(mv, dict)
        assert "cpu" in mv

    def test_preserves_partial_metrics_overrides(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"metrics_visible": {"cpu": False}}))
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        mv = get_bind_var("metrics_visible")
        assert mv["cpu"] is False
        assert mv["ram"] is True  # Default preserved


# =========================================================================
# generate_hyprconf
# =========================================================================

class TestGenerateHyprconf:

    def test_contains_keybindings(self):
        conf = generate_hyprconf()
        assert "bind =" in conf
        assert get_bind_var("suffix_restart") in conf
        assert get_bind_var("suffix_launcher") in conf

    def test_horizontal_animation_for_top(self):
        set_bind_var("bar_position", "Top")
        conf = generate_hyprconf()
        assert "slidefade " in conf
        assert "slidefadevert" not in conf

    def test_vertical_animation_for_left(self):
        set_bind_var("bar_position", "Left")
        conf = generate_hyprconf()
        assert "slidefadevert" in conf

    def test_contains_wallpapers_dir_comment(self):
        set_bind_var("wallpapers_dir", "/home/user/walls")
        conf = generate_hyprconf()
        assert "/home/user/walls" in conf

    def test_contains_hyprland_sections(self):
        conf = generate_hyprconf()
        assert "general {" in conf
        assert "decoration {" in conf
        assert "animations {" in conf


# =========================================================================
# backup_and_replace
# =========================================================================

class TestBackupAndReplace:

    def test_replaces_existing_with_backup(self, tmp_path):
        src = tmp_path / "source.conf"
        dest = tmp_path / "dest.conf"
        src.write_text("new content")
        dest.write_text("old content")

        backup_and_replace(src, dest, "TestConfig")

        assert dest.read_text() == "new content"
        backup = tmp_path / "dest.conf.bak"
        assert backup.exists()
        assert backup.read_text() == "old content"

    def test_creates_dest_when_missing(self, tmp_path):
        src = tmp_path / "source.conf"
        dest = tmp_path / "subdir" / "dest.conf"
        src.write_text("new content")

        backup_and_replace(src, dest, "TestConfig")

        assert dest.read_text() == "new content"

    def test_no_backup_when_dest_missing(self, tmp_path):
        src = tmp_path / "source.conf"
        dest = tmp_path / "dest.conf"
        src.write_text("content")

        backup_and_replace(src, dest, "TestConfig")

        assert not (tmp_path / "dest.conf.bak").exists()


# =========================================================================
# deep_update (imported from settings_utils, already tested separately
# but verifying it's the same function)
# =========================================================================

class TestDeepUpdateImport:

    def test_basic_merge(self):
        target = {"a": 1, "b": {"x": 1}}
        deep_update(target, {"b": {"y": 2}})
        assert target == {"a": 1, "b": {"x": 1, "y": 2}}

    def test_overwrite_non_dict(self):
        target = {"a": "old"}
        deep_update(target, {"a": "new"})
        assert target == {"a": "new"}

    def test_add_new_key(self):
        target = {"a": 1}
        deep_update(target, {"b": 2})
        assert target == {"a": 1, "b": 2}


# =========================================================================
# save_bind_vars
# =========================================================================

class TestSaveBindVars:

    def test_saves_json_to_file(self, tmp_path):
        config_file = tmp_path / "config.json"
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            set_bind_var("bar_position", "Bottom")
            save_bind_vars()
        saved = json.loads(config_file.read_text())
        assert saved["bar_position"] == "Bottom"

    def test_creates_parent_dirs(self, tmp_path):
        config_file = tmp_path / "sub" / "dir" / "config.json"
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            save_bind_vars()
        assert config_file.exists()

    def test_handles_write_error(self, tmp_path, capsys):
        config_file = tmp_path / "config.json"
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            with patch.object(Path, "write_text", side_effect=PermissionError("denied")):
                save_bind_vars()
        assert "Error saving config" in capsys.readouterr().out


# =========================================================================
# get_available_monitors
# =========================================================================

class TestGetAvailableMonitors:

    def test_returns_parsed_monitors(self):
        monitors_json = json.dumps([
            {"id": 0, "name": "HDMI-A-1"},
            {"id": 1, "name": "DP-1"},
        ])
        mock_result = MagicMock(returncode=0, stdout=monitors_json)
        with patch("config.settings_utils.subprocess.run", return_value=mock_result):
            result = get_available_monitors()
        assert result == [
            {"id": 0, "name": "HDMI-A-1"},
            {"id": 1, "name": "DP-1"},
        ]

    def test_returns_default_on_failure(self):
        mock_result = MagicMock(returncode=1, stdout="")
        with patch("config.settings_utils.subprocess.run", return_value=mock_result):
            result = get_available_monitors()
        assert result == [{"id": 0, "name": "default"}]

    def test_returns_default_on_exception(self):
        with patch("config.settings_utils.subprocess.run", side_effect=FileNotFoundError):
            result = get_available_monitors()
        assert result == [{"id": 0, "name": "default"}]

    def test_handles_missing_name_field(self):
        monitors_json = json.dumps([{"id": 2}])
        mock_result = MagicMock(returncode=0, stdout=monitors_json)
        with patch("config.settings_utils.subprocess.run", return_value=mock_result):
            result = get_available_monitors()
        assert result == [{"id": 2, "name": "monitor-2"}]


# =========================================================================
# apply_and_restart
# =========================================================================

class TestApplyAndRestart:

    @pytest.fixture
    def ar_env(self, tmp_path):
        """Set up tmp paths for apply_and_restart tests."""
        aw_config_dir = tmp_path / "aw-shell" / "config"
        config_dir = tmp_path / "config"
        config_file = aw_config_dir / "config.json"
        return tmp_path, aw_config_dir, config_dir, config_file

    def _patches(self, aw_config_dir, config_dir, config_file):
        """Stack of patch context managers for apply_and_restart."""
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("config.settings_utils.AW_CONFIG_DIR", aw_config_dir))
        stack.enter_context(patch("config.settings_utils.CONFIG_DIR", config_dir))
        stack.enter_context(patch("config.settings_utils.CONFIG_FILE", config_file))
        return stack

    def test_saves_and_writes_hyprconf(self, ar_env):
        tmp_path, aw_config_dir, config_dir, config_file = ar_env
        set_bind_var("auto_append_hyprland", False)
        mock_popen = MagicMock()
        mock_popen.return_value.wait.return_value = None
        with self._patches(aw_config_dir, config_dir, config_file):
            with patch("config.settings_utils.subprocess.run"):
                with patch("config.settings_utils.subprocess.Popen", mock_popen):
                    apply_and_restart()
        assert config_file.exists()
        hypr_conf = aw_config_dir / "hypr" / "aw-shell.conf"
        assert hypr_conf.exists()
        assert "bind =" in hypr_conf.read_text()

    def test_replace_lock(self, ar_env):
        tmp_path, aw_config_dir, config_dir, config_file = ar_env
        set_bind_var("auto_append_hyprland", False)
        lock_src = aw_config_dir / "hypr" / "hyprlock.conf"
        lock_src.parent.mkdir(parents=True, exist_ok=True)
        lock_src.write_text("lock config")
        mock_popen = MagicMock()
        mock_popen.return_value.wait.return_value = None
        with self._patches(aw_config_dir, config_dir, config_file):
            with patch("config.settings_utils.subprocess.run"):
                with patch("config.settings_utils.subprocess.Popen", mock_popen):
                    apply_and_restart(replace_lock=True)
        lock_dest = config_dir / "hypr" / "hyprlock.conf"
        assert lock_dest.exists()
        assert lock_dest.read_text() == "lock config"

    def test_replace_idle(self, ar_env):
        tmp_path, aw_config_dir, config_dir, config_file = ar_env
        set_bind_var("auto_append_hyprland", False)
        idle_src = aw_config_dir / "hypr" / "hypridle.conf"
        idle_src.parent.mkdir(parents=True, exist_ok=True)
        idle_src.write_text("idle config")
        mock_popen = MagicMock()
        mock_popen.return_value.wait.return_value = None
        with self._patches(aw_config_dir, config_dir, config_file):
            with patch("config.settings_utils.subprocess.run"):
                with patch("config.settings_utils.subprocess.Popen", mock_popen):
                    apply_and_restart(replace_idle=True)
        idle_dest = config_dir / "hypr" / "hypridle.conf"
        assert idle_dest.exists()
        assert idle_dest.read_text() == "idle config"

    def test_auto_append_hyprland_conf(self, ar_env):
        tmp_path, aw_config_dir, config_dir, config_file = ar_env
        set_bind_var("auto_append_hyprland", True)
        hypr_path = config_dir / "hypr" / "hyprland.conf"
        hypr_path.parent.mkdir(parents=True, exist_ok=True)
        hypr_path.write_text("# existing config")
        mock_popen = MagicMock()
        mock_popen.return_value.wait.return_value = None
        with self._patches(aw_config_dir, config_dir, config_file):
            with patch("config.settings_utils.subprocess.run"):
                with patch("config.settings_utils.subprocess.Popen", mock_popen):
                    apply_and_restart()
        content = hypr_path.read_text()
        assert "source =" in content
        assert "aw-shell.conf" in content

    def test_no_duplicate_append(self, ar_env):
        tmp_path, aw_config_dir, config_dir, config_file = ar_env
        set_bind_var("auto_append_hyprland", True)
        hypr_path = config_dir / "hypr" / "hyprland.conf"
        hypr_path.parent.mkdir(parents=True, exist_ok=True)
        source_line = f"source = {aw_config_dir}/hypr/aw-shell.conf"
        hypr_path.write_text(source_line)
        mock_popen = MagicMock()
        mock_popen.return_value.wait.return_value = None
        with self._patches(aw_config_dir, config_dir, config_file):
            with patch("config.settings_utils.subprocess.run"):
                with patch("config.settings_utils.subprocess.Popen", mock_popen):
                    apply_and_restart()
        assert hypr_path.read_text().count("source =") == 1

    def test_creates_hyprland_conf_if_missing(self, ar_env):
        tmp_path, aw_config_dir, config_dir, config_file = ar_env
        set_bind_var("auto_append_hyprland", True)
        mock_popen = MagicMock()
        mock_popen.return_value.wait.return_value = None
        with self._patches(aw_config_dir, config_dir, config_file):
            with patch("config.settings_utils.subprocess.run"):
                with patch("config.settings_utils.subprocess.Popen", mock_popen):
                    apply_and_restart()
        hypr_path = config_dir / "hypr" / "hyprland.conf"
        assert hypr_path.exists()
        assert "source =" in hypr_path.read_text()

    def test_killall_timeout_handled(self, ar_env):
        import subprocess as sp
        tmp_path, aw_config_dir, config_dir, config_file = ar_env
        set_bind_var("auto_append_hyprland", False)
        mock_popen = MagicMock()
        kill_proc = MagicMock()
        kill_proc.wait.side_effect = sp.TimeoutExpired("killall", 2)
        restart_proc = MagicMock()
        mock_popen.side_effect = [kill_proc, restart_proc]
        with self._patches(aw_config_dir, config_dir, config_file):
            with patch("config.settings_utils.subprocess.run"):
                with patch("config.settings_utils.subprocess.Popen", mock_popen):
                    apply_and_restart()  # Should not raise


# =========================================================================
# ensure_face_icon
# =========================================================================

class TestEnsureFaceIcon:

    def test_copies_when_missing(self, tmp_path):
        face_icon = tmp_path / ".face.icon"
        default_icon = tmp_path / "default.png"
        default_icon.write_text("icon data")
        with patch("config.settings_utils.FACE_ICON", face_icon):
            with patch("config.settings_utils.DEFAULT_FACE_ICON", default_icon):
                ensure_face_icon()
        assert face_icon.exists()
        assert face_icon.read_text() == "icon data"

    def test_skips_when_exists(self, tmp_path):
        face_icon = tmp_path / ".face.icon"
        face_icon.write_text("existing")
        default_icon = tmp_path / "default.png"
        default_icon.write_text("default")
        with patch("config.settings_utils.FACE_ICON", face_icon):
            with patch("config.settings_utils.DEFAULT_FACE_ICON", default_icon):
                ensure_face_icon()
        assert face_icon.read_text() == "existing"

    def test_skips_when_no_default(self, tmp_path):
        face_icon = tmp_path / ".face.icon"
        default_icon = tmp_path / "nonexistent.png"
        with patch("config.settings_utils.FACE_ICON", face_icon):
            with patch("config.settings_utils.DEFAULT_FACE_ICON", default_icon):
                ensure_face_icon()
        assert not face_icon.exists()

    def test_handles_copy_error(self, tmp_path, capsys):
        face_icon = tmp_path / ".face.icon"
        default_icon = tmp_path / "default.png"
        default_icon.write_text("icon data")
        with patch("config.settings_utils.FACE_ICON", face_icon):
            with patch("config.settings_utils.DEFAULT_FACE_ICON", default_icon):
                with patch("config.settings_utils.shutil.copy", side_effect=OSError("nope")):
                    ensure_face_icon()
        assert "Error copying default face icon" in capsys.readouterr().out


# =========================================================================
# ensure_matugen_config
# =========================================================================

class TestEnsureMatugenConfig:

    @pytest.fixture
    def matugen_env(self, tmp_path):
        """Set up filesystem for matugen tests."""
        home = tmp_path / "home"
        config_dir = home / ".config"
        aw_dir = config_dir / "aw-shell" / "config"
        current_wall = home / ".current.wall"
        hypr_colors = aw_dir / "hypr" / "colors.conf"
        css_colors = aw_dir / "styles" / "colors.css"
        return tmp_path, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors

    def _matugen_patches(self, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("config.settings_utils.HOME_DIR", home))
        stack.enter_context(patch("config.settings_utils.CONFIG_DIR", config_dir))
        stack.enter_context(patch("config.settings_utils.AW_CONFIG_DIR", aw_dir))
        stack.enter_context(patch("config.settings_utils.CURRENT_WALL", current_wall))
        stack.enter_context(patch("config.settings_utils.HYPR_COLORS", hypr_colors))
        stack.enter_context(patch("config.settings_utils.CSS_COLORS", css_colors))
        return stack

    def test_creates_config_when_missing(self, matugen_env):
        tmp_path, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors = matugen_env
        matugen_config = config_dir / "matugen" / "config.toml"
        with self._matugen_patches(home, config_dir, aw_dir, current_wall, hypr_colors, css_colors):
            with patch("config.settings_utils.os.path.expanduser",
                       return_value=str(matugen_config)):
                with patch("config.settings_utils.exec_shell_command_async"):
                    ensure_matugen_config()
        assert matugen_config.exists()

    def test_merges_with_existing_config(self, matugen_env):
        import toml
        tmp_path, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors = matugen_env
        matugen_config = config_dir / "matugen" / "config.toml"
        matugen_config.parent.mkdir(parents=True, exist_ok=True)
        existing = {"config": {"custom_key": "custom_value"}}
        matugen_config.write_text(toml.dumps(existing))
        with self._matugen_patches(home, config_dir, aw_dir, current_wall, hypr_colors, css_colors):
            with patch("config.settings_utils.os.path.expanduser",
                       return_value=str(matugen_config)):
                with patch("config.settings_utils.exec_shell_command_async"):
                    ensure_matugen_config()
        result = toml.loads(matugen_config.read_text())
        assert result["config"]["custom_key"] == "custom_value"
        assert result["config"]["reload_apps"] is True

    def test_handles_corrupt_toml(self, matugen_env, capsys):
        tmp_path, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors = matugen_env
        matugen_config = config_dir / "matugen" / "config.toml"
        matugen_config.parent.mkdir(parents=True, exist_ok=True)
        matugen_config.write_text("not valid [[[toml")
        with self._matugen_patches(home, config_dir, aw_dir, current_wall, hypr_colors, css_colors):
            with patch("config.settings_utils.os.path.expanduser",
                       return_value=str(matugen_config)):
                with patch("config.settings_utils.exec_shell_command_async"):
                    ensure_matugen_config()
        assert "Warning: Could not decode TOML" in capsys.readouterr().out

    def test_uses_symlinked_wallpaper(self, matugen_env):
        tmp_path, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors = matugen_env
        wall = tmp_path / "wall.jpg"
        wall.write_text("image data")
        current_wall.parent.mkdir(parents=True, exist_ok=True)
        current_wall.symlink_to(wall)
        matugen_config = config_dir / "matugen" / "config.toml"
        mock_exec = MagicMock()
        with self._matugen_patches(home, config_dir, aw_dir, current_wall, hypr_colors, css_colors):
            with patch("config.settings_utils.os.path.expanduser",
                       return_value=str(matugen_config)):
                with patch("config.settings_utils.exec_shell_command_async", mock_exec):
                    ensure_matugen_config()
        mock_exec.assert_called_once()
        assert "matugen image" in mock_exec.call_args[0][0]

    def test_creates_default_symlink_when_no_wallpaper(self, matugen_env):
        tmp_path, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors = matugen_env
        example = config_dir / "aw-shell" / "assets" / "wallpapers_example" / "example-1.jpg"
        example.parent.mkdir(parents=True, exist_ok=True)
        example.write_text("example image")
        current_wall.parent.mkdir(parents=True, exist_ok=True)
        matugen_config = config_dir / "matugen" / "config.toml"
        mock_exec = MagicMock()
        with self._matugen_patches(home, config_dir, aw_dir, current_wall, hypr_colors, css_colors):
            with patch("config.settings_utils.os.path.expanduser",
                       return_value=str(matugen_config)):
                with patch("config.settings_utils.exec_shell_command_async", mock_exec):
                    ensure_matugen_config()
        assert current_wall.is_symlink()
        mock_exec.assert_called_once()

    def test_no_wallpaper_no_example(self, matugen_env, capsys):
        tmp_path, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors = matugen_env
        current_wall.parent.mkdir(parents=True, exist_ok=True)
        matugen_config = config_dir / "matugen" / "config.toml"
        with self._matugen_patches(home, config_dir, aw_dir, current_wall, hypr_colors, css_colors):
            with patch("config.settings_utils.os.path.expanduser",
                       return_value=str(matugen_config)):
                with patch("config.settings_utils.exec_shell_command_async"):
                    ensure_matugen_config()
        output = capsys.readouterr().out
        assert "Example wallpaper not found" in output

    def test_matugen_command_not_found(self, matugen_env, capsys):
        tmp_path, home, config_dir, aw_dir, current_wall, hypr_colors, css_colors = matugen_env
        wall = tmp_path / "wall.jpg"
        wall.write_text("image")
        current_wall.parent.mkdir(parents=True, exist_ok=True)
        current_wall.symlink_to(wall)
        matugen_config = config_dir / "matugen" / "config.toml"
        with self._matugen_patches(home, config_dir, aw_dir, current_wall, hypr_colors, css_colors):
            with patch("config.settings_utils.os.path.expanduser",
                       return_value=str(matugen_config)):
                with patch("config.settings_utils.exec_shell_command_async",
                           side_effect=FileNotFoundError):
                    ensure_matugen_config()
        assert "matugen command not found" in capsys.readouterr().out


# =========================================================================
# load_bind_vars — additional edge cases
# =========================================================================

class TestLoadBindVarsEdgeCases:

    def test_fills_missing_metrics_subkeys(self, tmp_path):
        config_file = tmp_path / "config.json"
        # metrics_visible has cpu but missing ram, disk, gpu
        config_file.write_text(json.dumps({"metrics_visible": {"cpu": False}}))
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        mv = get_bind_var("metrics_visible")
        assert mv["cpu"] is False
        assert mv["ram"] is True
        assert mv["disk"] is True
        assert mv["gpu"] is True

    def test_handles_generic_exception(self, tmp_path, capsys):
        config_file = tmp_path / "config.json"
        config_file.write_text("content")
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            with patch.object(Path, "read_text", side_effect=OSError("disk error")):
                load_bind_vars()
        assert "Error reading" in capsys.readouterr().out
        # Should fall back to defaults
        assert get_bind_var("bar_position") == "Top"

    def test_metrics_small_visible_subkey_fill(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"metrics_small_visible": {"gpu": False}}))
        with patch("config.settings_utils.CONFIG_FILE", config_file):
            load_bind_vars()
        msv = get_bind_var("metrics_small_visible")
        assert msv["gpu"] is False
        assert msv["cpu"] is True  # filled from defaults


# =========================================================================
# backup_and_replace — error path
# =========================================================================

class TestBackupAndReplaceErrors:

    def test_handles_copy_error(self, tmp_path, capsys):
        src = tmp_path / "source.conf"
        dest = tmp_path / "dest.conf"
        src.write_text("new")
        with patch("config.settings_utils.shutil.copy", side_effect=OSError("fail")):
            backup_and_replace(src, dest, "TestConfig")
        assert "Error backing up/replacing" in capsys.readouterr().out


# =========================================================================
# start_config
# =========================================================================

class TestStartConfig:

    def _sc_patches(self, aw_config_dir, config_dir):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch("config.settings_utils.AW_CONFIG_DIR", aw_config_dir))
        stack.enter_context(patch("config.settings_utils.CONFIG_DIR", config_dir))
        return stack

    def test_orchestrates_all_steps(self, tmp_path):
        aw_config_dir = tmp_path / "aw-shell" / "config"
        config_dir = tmp_path / "config"
        mock_matugen = MagicMock()
        mock_face = MagicMock()
        mock_exec = MagicMock()
        with self._sc_patches(aw_config_dir, config_dir):
            with patch("config.settings_utils.ensure_matugen_config", mock_matugen):
                with patch("config.settings_utils.ensure_face_icon", mock_face):
                    with patch("config.settings_utils.exec_shell_command_async", mock_exec):
                        start_config()
        mock_matugen.assert_called_once()
        mock_face.assert_called_once()
        mock_exec.assert_called_once_with("hyprctl reload")

    def test_writes_hyprconf_file(self, tmp_path):
        aw_config_dir = tmp_path / "aw-shell" / "config"
        config_dir = tmp_path / "config"
        with self._sc_patches(aw_config_dir, config_dir):
            with patch("config.settings_utils.ensure_matugen_config"):
                with patch("config.settings_utils.ensure_face_icon"):
                    with patch("config.settings_utils.exec_shell_command_async"):
                        start_config()
        hypr_conf = aw_config_dir / "hypr" / "aw-shell.conf"
        assert hypr_conf.exists()
        assert "bind =" in hypr_conf.read_text()

    def test_handles_write_error(self, tmp_path, capsys):
        aw_config_dir = tmp_path / "aw-shell" / "config"
        config_dir = tmp_path / "config"
        with self._sc_patches(aw_config_dir, config_dir):
            with patch("config.settings_utils.ensure_matugen_config"):
                with patch("config.settings_utils.ensure_face_icon"):
                    with patch("config.settings_utils.exec_shell_command_async"):
                        with patch.object(Path, "write_text", side_effect=OSError("nope")):
                            start_config()
        assert "Error writing Hyprland config" in capsys.readouterr().out
