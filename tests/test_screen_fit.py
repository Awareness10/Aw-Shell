"""Tests for config/screen_fit.py and the windows sized with it."""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget

from config.screen_fit import ScreenFit, fit_size, target_screen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def fake_screen(w, h):
    screen = MagicMock()
    screen.availableGeometry.return_value = QRect(0, 0, w, h)
    return screen


class TestFitSize:
    @pytest.mark.parametrize("screen_w,screen_h,expected", [
        (1920, 1080, (648, 1004)),
        (3440, 1440, (864, 1339)),
        (1366, 768, (461, 714)),
    ])
    def test_settings_proportions(self, screen_w, screen_h, expected):
        assert fit_size(fake_screen(screen_w, screen_h), 0.93, 0.645, (400, 380)) == expected

    def test_tiny_screen_respects_minimum(self):
        assert fit_size(fake_screen(320, 240), 0.93, 0.645, (400, 380)) == (400, 380)

    def test_width_capped_by_screen(self):
        assert fit_size(fake_screen(500, 1440), 0.93, 0.645, (400, 380)) == (500, 1339)


class TestTargetScreen:
    def test_matches_focused_monitor(self, qapp):
        screens = QApplication.screens()
        with patch("config.screen_fit.get_focused_monitor_name", return_value=screens[-1].name()):
            assert target_screen() is screens[-1]

    def test_falls_back_to_primary(self, qapp):
        with patch("config.screen_fit.get_focused_monitor_name", return_value=None):
            assert target_screen() is QApplication.primaryScreen()


class TestScreenFit:
    def test_locks_size_until_shown_then_releases(self, qapp):
        win = QWidget()
        with patch("config.screen_fit.target_screen", return_value=fake_screen(1920, 1080)):
            ScreenFit(win, 0.93, 0.645, (400, 380))
        assert (win.width(), win.height()) == (648, 1004)
        assert win.minimumSize() == win.maximumSize()
        with patch("config.screen_fit.QTimer.singleShot") as single_shot:
            win.show()
        release = single_shot.call_args.args[1]
        release()
        assert win.minimumSize().width() == 400
        assert win.maximumSize().width() > 10000
        win.close()


class TestWindows:
    def test_settings_window_size(self, qapp):
        from config.settings.aw_settings import AwShellSettings
        with patch("config.screen_fit.target_screen", return_value=fake_screen(1920, 1080)), \
             patch("config.settings.aw_settings.get_available_monitors", return_value=[]):
            win = AwShellSettings()
        assert (win.width(), win.height()) == (648, 1004)
        win.close()

    @pytest.mark.parametrize("screen_w,screen_h,expected", [
        (1920, 1080, (486, 648)),
        (3440, 1440, (648, 864)),
    ])
    def test_updater_window_size(self, qapp, screen_w, screen_h, expected):
        from modules.updater import UpdaterWindow
        with patch("config.screen_fit.target_screen", return_value=fake_screen(screen_w, screen_h)):
            win = UpdaterWindow(latest_version="1.2.6", releases=[], current_version="1.2.6", preview=True)
        assert (win.width(), win.height()) == expected
        win.close()
