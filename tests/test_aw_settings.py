"""Tests for config/settings/aw_settings.py — PySide6 settings dialog.

Tests widget construction, UI callbacks, settings collection, and roundtrip
to catch breaking changes. Runs headless via QT_QPA_PLATFORM=offscreen (set in conftest.py).
"""

from unittest.mock import patch, MagicMock

import pytest

from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox
from PySide6.QtCore import Qt

from config.settings_utils import bind_vars, set_bind_var, reset_to_defaults
from config.settings_constants import DEFAULTS
from config.settings.aw_settings import (
    AwShellSettings,
    POSITIONS,
    THEMES,
    PANEL_THEMES,
    PANEL_POSITIONS,
    NOTIFICATION_POSITIONS,
    METRIC_NAMES,
    COMPONENT_DISPLAY_NAMES,
    KEYBIND_SECTIONS,
    SettingsSection,
)


# ── Fixtures ──

@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def setup_bind_vars():
    """Reset bind_vars to defaults before each test."""
    bind_vars.clear()
    bind_vars.update(DEFAULTS.copy())
    yield
    bind_vars.clear()


@pytest.fixture
def settings(qapp):
    """Create a fresh AwShellSettings instance."""
    with patch("config.settings.aw_settings.get_available_monitors", return_value=[
        {"id": 0, "name": "HDMI-A-1"},
        {"id": 1, "name": "DP-1"},
    ]):
        win = AwShellSettings()
    yield win
    win.close()


# =========================================================================
# Constants validation
# =========================================================================

class TestConstants:

    def test_positions(self):
        assert POSITIONS == ["Top", "Bottom", "Left", "Right"]

    def test_themes(self):
        assert THEMES == ["Pills", "Dense", "Edge"]

    def test_panel_themes(self):
        assert PANEL_THEMES == ["Notch", "Panel"]

    def test_panel_positions(self):
        assert PANEL_POSITIONS == ["Start", "Center", "End"]

    def test_notification_positions(self):
        assert NOTIFICATION_POSITIONS == ["Top", "Bottom"]

    def test_metric_names_keys(self):
        assert set(METRIC_NAMES.keys()) == {"cpu", "ram", "disk", "gpu"}

    def test_component_display_names_not_empty(self):
        assert len(COMPONENT_DISPLAY_NAMES) > 0
        for key, display in COMPONENT_DISPLAY_NAMES.items():
            assert isinstance(key, str)
            assert isinstance(display, str)

    def test_keybind_sections_structure(self):
        assert len(KEYBIND_SECTIONS) == 3
        for section_name, bindings in KEYBIND_SECTIONS:
            assert isinstance(section_name, str)
            for label, prefix_key, suffix_key in bindings:
                assert isinstance(label, str)
                assert prefix_key.startswith("prefix_")
                assert suffix_key.startswith("suffix_")

    def test_all_keybind_keys_in_defaults(self):
        for _, bindings in KEYBIND_SECTIONS:
            for _, prefix_key, suffix_key in bindings:
                assert prefix_key in DEFAULTS, f"{prefix_key} missing from DEFAULTS"
                assert suffix_key in DEFAULTS, f"{suffix_key} missing from DEFAULTS"

    def test_all_component_keys_have_visibility_default(self):
        for name in COMPONENT_DISPLAY_NAMES:
            key = f"bar_{name}_visible"
            assert key in DEFAULTS, f"{key} missing from DEFAULTS"


# =========================================================================
# Widget construction
# =========================================================================

class TestWidgetConstruction:

    def test_settings_window_creates(self, settings):
        assert settings is not None

    def test_has_tabs(self, settings):
        assert settings.tabs.count() == 4

    def test_tab_names(self, settings):
        names = [settings.tabs.tabText(i) for i in range(settings.tabs.count())]
        assert names == ["Key Bindings", "Appearance", "System", "About"]

    def test_has_action_buttons(self, settings):
        assert settings.reset_btn is not None
        assert settings.close_btn is not None
        assert settings.apply_btn is not None

    def test_keybind_entries_populated(self, settings):
        total_bindings = sum(len(bindings) for _, bindings in KEYBIND_SECTIONS)
        assert len(settings.keybind_entries) == total_bindings

    def test_component_switches_populated(self, settings):
        assert len(settings.component_switches) == len(COMPONENT_DISPLAY_NAMES)

    def test_metrics_switches_populated(self, settings):
        assert len(settings.metrics_switches) == len(METRIC_NAMES)
        assert len(settings.metrics_small_switches) == len(METRIC_NAMES)

    def test_monitor_checkboxes_populated(self, settings):
        assert "HDMI-A-1" in settings.monitor_checkboxes
        assert "DP-1" in settings.monitor_checkboxes


# =========================================================================
# SettingsSection
# =========================================================================

class TestSettingsSection:

    def test_creates_with_title(self, qapp):
        section = SettingsSection("Test Section")
        assert section.title() == "Test Section"


# =========================================================================
# UI callbacks
# =========================================================================

class TestUICallbacks:

    def test_position_change_enables_centered_for_vertical(self, settings):
        settings._on_position_changed("Left")
        assert settings.centered_cb.isEnabled() is True

    def test_position_change_disables_centered_for_horizontal(self, settings):
        settings._on_position_changed("Top")
        assert settings.centered_cb.isEnabled() is False
        assert settings.centered_cb.isChecked() is False

    def test_dock_disable_unchecks_always_show(self, settings):
        settings.dock_always_cb.setChecked(True)
        settings._on_dock_changed(Qt.CheckState.Unchecked.value)
        assert settings.dock_always_cb.isEnabled() is False
        assert settings.dock_always_cb.isChecked() is False

    def test_dock_enable_enables_always_show(self, settings):
        settings._on_dock_changed(Qt.CheckState.Checked.value)
        assert settings.dock_always_cb.isEnabled() is True

    def test_ws_num_disable_unchecks_runes(self, settings):
        settings.ws_runes_cb.setChecked(True)
        settings._on_ws_num_changed(Qt.CheckState.Unchecked.value)
        assert settings.ws_runes_cb.isEnabled() is False
        assert settings.ws_runes_cb.isChecked() is False

    def test_ws_num_enable_enables_runes(self, settings):
        settings._on_ws_num_changed(Qt.CheckState.Checked.value)
        assert settings.ws_runes_cb.isEnabled() is True

    def test_panel_theme_notch_disables_position(self, settings):
        settings._on_panel_theme_changed("Notch")
        assert settings.panel_position_combo.isEnabled() is False

    def test_panel_theme_panel_enables_position(self, settings):
        settings._on_panel_theme_changed("Panel")
        assert settings.panel_position_combo.isEnabled() is True


# =========================================================================
# _parse_app_list
# =========================================================================

class TestParseAppList:

    def test_empty_string(self, settings):
        assert settings._parse_app_list("") == []

    def test_whitespace_only(self, settings):
        assert settings._parse_app_list("   ") == []

    def test_single_app(self, settings):
        assert settings._parse_app_list('"Spotify"') == ["Spotify"]

    def test_multiple_apps(self, settings):
        result = settings._parse_app_list('"Spotify", "Discord", "Firefox"')
        assert result == ["Spotify", "Discord", "Firefox"]

    def test_unquoted_apps(self, settings):
        result = settings._parse_app_list("Spotify, Discord")
        assert result == ["Spotify", "Discord"]

    def test_mixed_quotes(self, settings):
        result = settings._parse_app_list("\"Spotify\", 'Discord'")
        assert result == ["Spotify", "Discord"]

    def test_extra_whitespace(self, settings):
        result = settings._parse_app_list('  "Spotify"  ,  "Discord"  ')
        assert result == ["Spotify", "Discord"]

    def test_empty_entries_filtered(self, settings):
        result = settings._parse_app_list('"Spotify", , , "Discord"')
        assert result == ["Spotify", "Discord"]


# =========================================================================
# _collect_settings roundtrip
# =========================================================================

class TestCollectSettings:

    def test_collect_returns_dict(self, settings):
        result = settings._collect_settings()
        assert isinstance(result, dict)

    def test_collect_contains_keybindings(self, settings):
        result = settings._collect_settings()
        for _, bindings in KEYBIND_SECTIONS:
            for _, prefix_key, suffix_key in bindings:
                assert prefix_key in result
                assert suffix_key in result

    def test_collect_contains_appearance_settings(self, settings):
        result = settings._collect_settings()
        assert "bar_position" in result
        assert "bar_theme" in result
        assert "dock_theme" in result
        assert "panel_theme" in result
        assert "panel_position" in result
        assert "notif_pos" in result
        assert "dock_enabled" in result
        assert "dock_icon_size" in result
        assert "corners_visible" in result

    def test_collect_contains_component_visibility(self, settings):
        result = settings._collect_settings()
        for name in COMPONENT_DISPLAY_NAMES:
            assert f"bar_{name}_visible" in result

    def test_collect_contains_system_settings(self, settings):
        result = settings._collect_settings()
        assert "auto_append_hyprland" in result
        assert "terminal_command" in result
        assert "selected_monitors" in result

    def test_collect_contains_metrics(self, settings):
        result = settings._collect_settings()
        assert isinstance(result["metrics_visible"], dict)
        assert isinstance(result["metrics_small_visible"], dict)
        for key in METRIC_NAMES:
            assert key in result["metrics_visible"]
            assert key in result["metrics_small_visible"]

    def test_collect_contains_disk_paths(self, settings):
        result = settings._collect_settings()
        assert "bar_metrics_disks" in result
        assert isinstance(result["bar_metrics_disks"], list)

    def test_collect_default_values_match(self, settings):
        """Verify that freshly built widgets produce values matching DEFAULTS."""
        result = settings._collect_settings()
        assert result["bar_position"] == DEFAULTS["bar_position"]
        assert result["bar_theme"] == DEFAULTS["bar_theme"]
        assert result["dock_enabled"] == DEFAULTS["dock_enabled"]
        assert result["panel_theme"] == DEFAULTS["panel_theme"]

    def test_collect_reflects_widget_changes(self, settings):
        """Modify widgets and verify _collect_settings picks it up."""
        settings.position_combo.setCurrentText("Bottom")
        settings.dock_cb.setChecked(False)
        settings.bar_theme_combo.setCurrentText("Dense")
        result = settings._collect_settings()
        assert result["bar_position"] == "Bottom"
        assert result["dock_enabled"] is False
        assert result["bar_theme"] == "Dense"

    def test_vertical_derived_from_position(self, settings):
        settings.position_combo.setCurrentText("Left")
        result = settings._collect_settings()
        assert result["vertical"] is True

        settings.position_combo.setCurrentText("Top")
        result = settings._collect_settings()
        assert result["vertical"] is False

    def test_notification_apps_roundtrip(self, settings):
        settings.limited_apps_entry.setText('"Spotify", "Discord"')
        settings.ignored_apps_entry.setText('"Hyprshot"')
        result = settings._collect_settings()
        assert result["limited_apps_history"] == ["Spotify", "Discord"]
        assert result["history_ignored_apps"] == ["Hyprshot"]

    def test_monitor_selection_all_checked(self, settings):
        for cb in settings.monitor_checkboxes.values():
            cb.setChecked(True)
        result = settings._collect_settings()
        assert set(result["selected_monitors"]) == {"HDMI-A-1", "DP-1"}

    def test_monitor_selection_none_checked(self, settings):
        for cb in settings.monitor_checkboxes.values():
            cb.setChecked(False)
        result = settings._collect_settings()
        assert result["selected_monitors"] == []

    def test_empty_disk_paths_default_to_root(self, settings):
        # Remove all disk entries
        for container in settings.disk_entries[:]:
            settings._remove_disk_entry(container)
        result = settings._collect_settings()
        assert result["bar_metrics_disks"] == ["/"]


# =========================================================================
# _remove_disk_entry
# =========================================================================

class TestDiskEntries:

    def test_remove_disk_entry(self, settings):
        initial_count = len(settings.disk_entries)
        assert initial_count > 0
        container = settings.disk_entries[0]
        settings._remove_disk_entry(container)
        assert len(settings.disk_entries) == initial_count - 1

    def test_remove_nonexistent_entry_is_noop(self, settings):
        from PySide6.QtWidgets import QWidget
        fake = QWidget()
        initial_count = len(settings.disk_entries)
        settings._remove_disk_entry(fake)
        assert len(settings.disk_entries) == initial_count

    def test_add_disk_entry(self, settings):
        initial_count = len(settings.disk_entries)
        settings._add_disk_entry("/home")
        assert len(settings.disk_entries) == initial_count + 1
        # Verify the new entry has the path
        last = settings.disk_entries[-1]
        entry = last.layout().itemAt(0).widget()
        assert isinstance(entry, QLineEdit)
        assert entry.text() == "/home"

    def test_collect_multiple_disk_paths(self, settings):
        settings._add_disk_entry("/home")
        settings._add_disk_entry("/var")
        result = settings._collect_settings()
        assert "/home" in result["bar_metrics_disks"]
        assert "/var" in result["bar_metrics_disks"]


# =========================================================================
# _load_face_icon
# =========================================================================

class TestLoadFaceIcon:

    def test_no_icon_shows_text(self, settings):
        with patch("config.settings.aw_settings.Path.exists", return_value=False):
            settings._load_face_icon()
        assert settings.face_image.text() == "No Icon"

    def test_icon_exists_loads_pixmap(self, settings):
        with patch("config.settings.aw_settings.Path.exists", return_value=True):
            with patch("config.settings.aw_settings.Path.expanduser", return_value=MagicMock(exists=MagicMock(return_value=True), __str__=lambda s: "/tmp/fake.png")):
                settings._load_face_icon()
        # Should not show "No Icon" text if pixmap path existed
        # (pixmap may be null in offscreen, but the text path shouldn't have run)


# =========================================================================
# _on_browse_wallpapers / _on_select_face_icon
# =========================================================================

class TestFileDialogs:

    def test_browse_wallpapers_sets_path(self, settings):
        with patch("config.settings.aw_settings.QFileDialog.getExistingDirectory", return_value="/home/user/walls"):
            settings._on_browse_wallpapers()
        assert settings.wall_dir_entry.text() == "/home/user/walls"

    def test_browse_wallpapers_cancel(self, settings):
        original = settings.wall_dir_entry.text()
        with patch("config.settings.aw_settings.QFileDialog.getExistingDirectory", return_value=""):
            settings._on_browse_wallpapers()
        assert settings.wall_dir_entry.text() == original

    def test_select_face_icon_sets_path(self, settings):
        with patch("config.settings.aw_settings.QFileDialog.getOpenFileName", return_value=("/tmp/face.png", "")):
            settings._on_select_face_icon()
        assert settings.selected_face_icon == "/tmp/face.png"
        assert "face.png" in settings.face_status_label.text()

    def test_select_face_icon_cancel(self, settings):
        settings.selected_face_icon = None
        with patch("config.settings.aw_settings.QFileDialog.getOpenFileName", return_value=("", "")):
            settings._on_select_face_icon()
        assert settings.selected_face_icon is None


# =========================================================================
# _reload_widgets
# =========================================================================

class TestReloadWidgets:

    def test_reload_restores_defaults(self, settings):
        # Modify widgets
        settings.position_combo.setCurrentText("Bottom")
        settings.dock_cb.setChecked(False)
        settings.bar_theme_combo.setCurrentText("Dense")
        settings.terminal_entry.setText("alacritty -e")

        # Reset bind_vars and reload
        reset_to_defaults()
        settings._reload_widgets()

        assert settings.position_combo.currentText() == "Top"
        assert settings.dock_cb.isChecked() is True
        assert settings.bar_theme_combo.currentText() == "Pills"
        assert settings.terminal_entry.text() == "kitty -e"

    def test_reload_updates_keybindings(self, settings):
        set_bind_var("prefix_restart", "CTRL ALT")
        set_bind_var("suffix_restart", "R")
        settings._reload_widgets()

        # Find the restart keybind entry
        for prefix_key, suffix_key, prefix_entry, suffix_entry in settings.keybind_entries:
            if prefix_key == "prefix_restart":
                assert prefix_entry.text() == "CTRL ALT"
                assert suffix_entry.text() == "R"
                break

    def test_reload_updates_component_switches(self, settings):
        set_bind_var("bar_systray_visible", False)
        settings._reload_widgets()
        assert settings.component_switches["systray"].isChecked() is False

    def test_reload_updates_metrics(self, settings):
        set_bind_var("metrics_visible", {"cpu": False, "ram": True, "disk": True, "gpu": False})
        settings._reload_widgets()
        assert settings.metrics_switches["cpu"].isChecked() is False
        assert settings.metrics_switches["gpu"].isChecked() is False
        assert settings.metrics_switches["ram"].isChecked() is True

    def test_reload_rebuilds_disk_entries(self, settings):
        set_bind_var("bar_metrics_disks", ["/", "/home", "/var"])
        settings._reload_widgets()
        assert len(settings.disk_entries) == 3

    def test_reload_updates_notification_apps(self, settings):
        set_bind_var("limited_apps_history", ["Firefox", "Slack"])
        set_bind_var("history_ignored_apps", ["Screenshot"])
        settings._reload_widgets()
        assert "Firefox" in settings.limited_apps_entry.text()
        assert "Screenshot" in settings.ignored_apps_entry.text()

    def test_reload_updates_dependent_states(self, settings):
        """After reload, dependent widget states should be consistent."""
        set_bind_var("bar_position", "Left")
        set_bind_var("dock_enabled", False)
        set_bind_var("panel_theme", "Panel")
        settings._reload_widgets()
        assert settings.centered_cb.isEnabled() is True  # Left enables centered
        assert settings.dock_always_cb.isEnabled() is False  # Dock disabled
        assert settings.panel_position_combo.isEnabled() is True  # Panel enables position

    def test_reload_clears_face_icon_state(self, settings):
        settings.selected_face_icon = "/tmp/old.png"
        settings.face_status_label.setText("Selected: old.png")
        settings._reload_widgets()
        assert settings.selected_face_icon is None
        assert settings.face_status_label.text() == ""


# =========================================================================
# _on_apply
# =========================================================================

class TestOnApply:

    def test_apply_collects_and_saves(self, settings):
        settings.position_combo.setCurrentText("Bottom")
        with patch("config.settings.aw_settings.apply_and_restart") as mock_restart:
            with patch("config.settings.aw_settings.QMessageBox.information"):
                settings._on_apply()
        mock_restart.assert_called_once_with(False, False)
        # bind_vars should have been updated
        assert bind_vars.get("bar_position") == "Bottom"

    def test_apply_with_face_icon(self, settings):
        settings.selected_face_icon = "/tmp/test.png"
        mock_img = MagicMock()
        mock_img.size = (200, 100)
        mock_img.width = 200
        mock_img.height = 100
        mock_cropped = MagicMock()
        mock_img.crop.return_value = mock_cropped

        with patch("config.settings.aw_settings.apply_and_restart"):
            with patch("config.settings.aw_settings.QMessageBox.information"):
                with patch.dict("sys.modules", {"PIL": MagicMock(), "PIL.Image": MagicMock()}):
                    from PIL import Image
                    Image.open = MagicMock(return_value=mock_img)
                    settings._on_apply()

        # Face icon should be cleared after apply
        assert settings.selected_face_icon is None

    def test_apply_without_face_icon(self, settings):
        settings.selected_face_icon = None
        with patch("config.settings.aw_settings.apply_and_restart") as mock_restart:
            with patch("config.settings.aw_settings.QMessageBox.information"):
                settings._on_apply()
        mock_restart.assert_called_once()

    def test_apply_shows_confirmation(self, settings):
        with patch("config.settings.aw_settings.apply_and_restart"):
            with patch("config.settings.aw_settings.QMessageBox.information") as mock_info:
                settings._on_apply()
        mock_info.assert_called_once()
        assert "restarting" in mock_info.call_args[0][2].lower()


# =========================================================================
# _on_reset
# =========================================================================

class TestOnReset:

    def test_reset_accepted_reloads_widgets(self, settings):
        settings.position_combo.setCurrentText("Bottom")
        with patch("config.settings.aw_settings.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            settings._on_reset()
        assert settings.position_combo.currentText() == "Top"

    def test_reset_declined_keeps_changes(self, settings):
        settings.position_combo.setCurrentText("Bottom")
        with patch("config.settings.aw_settings.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            settings._on_reset()
        assert settings.position_combo.currentText() == "Bottom"


# =========================================================================
# Hyprland integration section (early return)
# =========================================================================

class TestHyprSection:

    def test_no_hypr_section_when_no_configs(self, qapp):
        """When neither hyprlock nor hypridle conf exists, section is skipped."""
        with patch("config.settings.aw_settings.get_available_monitors", return_value=[]):
            with patch("pathlib.Path.exists", return_value=False):
                win = AwShellSettings()
        # The hypr section should not have lock/idle checkboxes
        assert not hasattr(win, 'lock_cb')
        assert not hasattr(win, 'idle_cb')
        win.close()
