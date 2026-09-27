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


class TestFetchRemoteVersion:
    def test_bypasses_cdn_cache(self):
        """Regression: raw.githubusercontent caches for 5 minutes, so right
        after a release the updater still saw the previous version.json."""
        from modules.updater import REMOTE_URL, fetch_remote_version
        with patch("modules.updater.subprocess.run") as run, \
                patch("modules.updater.time.time", return_value=1790000000.5):
            fetch_remote_version()
        assert f"{REMOTE_URL}?t=1790000000" in run.call_args.args[0]


class TestParseReleases:
    def test_grouped_releases(self):
        from modules.updater import parse_releases
        data = {"version": "1.2.0", "releases": [
            {"version": "1.2.0", "changes": ["b"]},
            {"version": "1.1.0", "changes": ["a"]},
        ]}
        assert parse_releases(data) == [
            {"version": "1.2.0", "changes": ["b"]},
            {"version": "1.1.0", "changes": ["a"]},
        ]

    def test_legacy_flat_changelog_becomes_one_release(self):
        from modules.updater import parse_releases
        data = {"version": "1.1.0", "changelog": ["<b>feat:</b> New feature"]}
        assert parse_releases(data) == [{"version": "1.1.0", "changes": ["<b>feat:</b> New feature"]}]

    def test_no_changes(self):
        from modules.updater import parse_releases
        assert parse_releases({"version": "1.1.0"}) == []


class TestNewVersions:
    RELEASES = [{"version": v, "changes": ["x"]} for v in ("1.2.6", "1.2.5", "1.2.4")]

    def test_versions_newer_than_installed(self):
        from modules.updater import new_versions
        assert new_versions(self.RELEASES, "1.2.4") == {"1.2.6", "1.2.5"}

    def test_falls_back_to_latest_when_up_to_date(self):
        from modules.updater import new_versions
        assert new_versions(self.RELEASES, "1.2.6") == {"1.2.6"}

    def test_empty(self):
        from modules.updater import new_versions
        assert new_versions([], "1.0.0") == set()


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

def _changelog_text(window):
    from PySide6.QtWidgets import QLabel
    return "\n".join(l.text() for l in window.changelog_widget.findChildren(QLabel))


def _headers(window):
    from PySide6.QtWidgets import QLabel
    return {l.text(): l.objectName() for l in window.changelog_widget.findChildren(QLabel)
            if l.objectName().startswith("releaseHeader")}


RELEASES = [
    {"version": "1.2.6", "changes": ["<b>feat:</b> Newest"]},
    {"version": "1.2.5", "changes": ["<b>fix:</b> Middle"]},
    {"version": "1.2.4", "changes": ["<b>fix:</b> Installed"]},
]


class TestGroupedChangelog:
    @pytest.fixture
    def window(self, qapp):
        from modules.updater import UpdaterWindow
        win = UpdaterWindow(latest_version="1.2.6", releases=RELEASES,
                            pkg_update=False, current_version="1.2.4")
        yield win
        win.close()

    def test_one_section_per_version_newest_first(self, window):
        text = _changelog_text(window)
        assert text.index("v1.2.6") < text.index("v1.2.5") < text.index("v1.2.4")

    def test_versions_newer_than_installed_are_marked_new(self, window):
        assert _headers(window) == {
            "v1.2.6 (new)": "releaseHeaderNew",
            "v1.2.5 (new)": "releaseHeaderNew",
            "v1.2.4": "releaseHeader",
        }

    def test_latest_marked_new_when_up_to_date(self, qapp):
        from modules.updater import UpdaterWindow
        win = UpdaterWindow(latest_version="1.2.6", releases=RELEASES,
                            pkg_update=False, current_version="1.2.6")
        assert _headers(win)["v1.2.6 (new)"] == "releaseHeaderNew"
        assert "v1.2.5" in _headers(win)
        win.close()


class TestChangeRows:
    def test_split_change(self):
        from modules.updater import split_change
        assert split_change("<b>fix:</b> Mic icon shows again") == ("fix", "Mic icon shows again")
        assert split_change("Plain entry") == (None, "Plain entry")

    def test_each_change_is_its_own_row_with_type_tag(self, qapp):
        from PySide6.QtWidgets import QLabel
        from modules.updater import UpdaterWindow
        win = UpdaterWindow(latest_version="1.2.6", releases=RELEASES,
                            pkg_update=False, current_version="1.2.4")
        tags = {l.text(): l.objectName() for l in win.changelog_widget.findChildren(QLabel)
                if l.objectName().startswith("changeTag")}
        assert tags == {"feat": "changeTag_feat", "fix": "changeTag_fix"}
        texts = [l.text() for l in win.changelog_widget.findChildren(QLabel)
                 if l.objectName() == "changeText"]
        assert texts == ["Newest", "Middle", "Installed"]
        win.close()


class TestPreviewMode:
    @pytest.fixture
    def window(self, qapp):
        from modules.updater import UpdaterWindow
        win = UpdaterWindow(latest_version="1.2.6", releases=RELEASES,
                            pkg_update=True, current_version="1.2.6", preview=True)
        yield win
        win.close()

    def test_update_shows_command_without_running_it(self, window):
        with patch("modules.updater.QProcess") as process:
            window._on_update()
        process.assert_not_called()
        assert "install.sh" in window.log_area.toPlainText()
        assert window.update_btn.isEnabled()

    def test_later_does_not_snooze(self, window):
        with patch("modules.updater.write_snooze") as snooze:
            window._on_later()
        snooze.assert_not_called()

    def test_toggle_does_not_touch_disable_flag(self, window):
        with patch("modules.updater.toggle_updater_disabled") as toggle:
            window._on_toggle_updater()
        toggle.assert_not_called()
        assert window.toggle_btn.text() == "Enable Updater"

    def test_title_marks_preview(self, window):
        from PySide6.QtWidgets import QLabel
        title = window.findChild(QLabel, "updaterTitle")
        assert "(preview)" in title.text()


class TestUpdaterWindow:
    @pytest.fixture
    def window(self, qapp):
        from modules.updater import UpdaterWindow
        win = UpdaterWindow(
            latest_version="2.0.0",
            releases=["<b>feat:</b> New feature", "<b>fix:</b> Bug fix"],  # legacy flat list
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
        text = _changelog_text(window)
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
