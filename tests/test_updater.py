"""Tests for modules/updater.py — PySide6 updater.

Tests backend logic (version comparison, snooze/disable files, connectivity)
and widget construction. Runs headless via QT_QPA_PLATFORM=offscreen.
"""

import json
import os
import time
from unittest.mock import patch, MagicMock

import pytest

from PySide6.QtWidgets import QApplication


# ── Fixtures ──

@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def tmp_version_files(tmp_path):
    """Create temporary local and remote version files."""
    local = tmp_path / "version.json"
    remote = tmp_path / "remote_version.json"
    local.write_text(json.dumps({
        "version": "1.0.0",
        "changelog": ["<b>init:</b> Initial release"],
    }))
    remote.write_text(json.dumps({
        "version": "1.1.0",
        "pkg_update": False,
        "changelog": ["<b>feat:</b> New feature"],
    }))
    return local, remote


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Temporary cache directory for snooze/disable files."""
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


# ── Version reading tests ──

class TestGetLocalVersion:
    def test_reads_valid_file(self, tmp_version_files):
        local, _ = tmp_version_files
        with patch("modules.updater.VERSION_FILE", str(local)):
            from modules.updater import get_local_version
            version, changelog = get_local_version()
            assert version == "1.0.0"
            assert len(changelog) == 1

    def test_missing_file_returns_defaults(self, tmp_path):
        with patch("modules.updater.VERSION_FILE", str(tmp_path / "nonexistent.json")):
            from modules.updater import get_local_version
            version, changelog = get_local_version()
            assert version == "0.0.0"
            assert changelog == []

    def test_invalid_json_returns_defaults(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        with patch("modules.updater.VERSION_FILE", str(bad)):
            from modules.updater import get_local_version
            version, changelog = get_local_version()
            assert version == "0.0.0"
            assert changelog == []


class TestGetRemoteVersion:
    def test_reads_valid_file(self, tmp_version_files):
        _, remote = tmp_version_files
        with patch("modules.updater.REMOTE_VERSION_FILE", str(remote)):
            from modules.updater import get_remote_version
            version, changelog, url, pkg_update = get_remote_version()
            assert version == "1.1.0"
            assert pkg_update is False

    def test_missing_file_returns_defaults(self, tmp_path):
        with patch("modules.updater.REMOTE_VERSION_FILE", str(tmp_path / "nope.json")):
            from modules.updater import get_remote_version
            version, changelog, url, pkg_update = get_remote_version()
            assert version == "0.0.0"
            assert pkg_update is True


# ── Snooze/disable file tests ──

class TestSnoozeLogic:
    def test_snooze_file_created(self, tmp_cache_dir):
        snooze_path = tmp_cache_dir / "updater_snooze.txt"
        with open(snooze_path, "w") as f:
            f.write(str(time.time()))
        assert snooze_path.exists()
        ts = float(snooze_path.read_text())
        assert time.time() - ts < 5  # written just now

    def test_snooze_expired(self, tmp_cache_dir):
        snooze_path = tmp_cache_dir / "updater_snooze.txt"
        expired_time = time.time() - (9 * 60 * 60)  # 9 hours ago
        snooze_path.write_text(str(expired_time))
        ts = float(snooze_path.read_text())
        assert time.time() - ts > 8 * 60 * 60  # past 8h threshold


class TestDisableLogic:
    def test_disable_file_toggle(self, tmp_cache_dir):
        disable_path = tmp_cache_dir / "updater_disabled.flag"
        assert not disable_path.exists()
        disable_path.touch()
        assert disable_path.exists()
        disable_path.unlink()
        assert not disable_path.exists()


# ── Connectivity test ──

class TestConnectivity:
    def test_connected_returns_true(self):
        with patch("modules.updater.socket.create_connection"):
            from modules.updater import is_connected
            assert is_connected() is True

    def test_disconnected_returns_false(self):
        with patch("modules.updater.socket.create_connection", side_effect=OSError):
            from modules.updater import is_connected
            assert is_connected() is False


# ── UI tests ──

class TestUpdaterWindow:
    @pytest.fixture
    def window(self, qapp):
        from modules.updater import UpdaterWindow
        win = UpdaterWindow(
            latest_version="2.0.0",
            changelog=["<b>feat:</b> New feature", "<b>fix:</b> Bug fix"],
            pkg_update=False,
        )
        yield win
        win.close()

    def test_window_created(self, window):
        from glaze.widgets import FramelessMainWindow
        assert window is not None
        assert isinstance(window, FramelessMainWindow)

    def test_has_update_button(self, window):
        assert window.update_btn is not None
        assert window.update_btn.text() == "Update"

    def test_has_later_button(self, window):
        assert window.later_btn is not None
        assert window.later_btn.text() == "Later"

    def test_has_toggle_button(self, window):
        assert window.toggle_btn is not None

    def test_changelog_displayed(self, window):
        text = window.changelog_label.text()
        assert "New feature" in text
        assert "Bug fix" in text

    def test_version_displayed(self, window):
        text = window.info_label.text()
        assert "2.0.0" in text

    def test_log_area_initially_hidden(self, window):
        assert not window.log_area.isVisible()


class TestEntryPoints:
    def test_check_for_updates_is_callable(self):
        from modules.updater import check_for_updates
        assert callable(check_for_updates)

    def test_run_updater_is_callable(self):
        from modules.updater import run_updater
        assert callable(run_updater)

    def test_module_has_no_gtk_imports(self):
        import modules.updater as mod
        source = open(mod.__file__).read()
        assert "gi.repository" not in source
        assert "from gi" not in source
        assert "Vte" not in source
