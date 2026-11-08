"""One scan of the desktop apps, shared by the dock, launcher, notch and
overview on every monitor; scanned again after apps change."""

import pytest
from fabric.utils import helpers

import utils.apps as apps


@pytest.fixture
def scans(sandbox, monkeypatch):
    calls = []
    real = helpers.get_desktop_applications

    def scan(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(helpers, "get_desktop_applications", scan)
    apps._forget()
    yield calls
    apps._forget()


def test_scanned_once_and_shared(scans):
    first = apps.desktop_apps()
    assert apps.desktop_apps() is first
    assert apps.app_identifiers() is apps.app_identifiers()
    assert len(scans) == 1


def test_scanned_again_after_apps_change(scans):
    from gi.repository import Gio

    first = apps.desktop_apps()
    identifiers = apps.app_identifiers()
    Gio.AppInfoMonitor.get().emit("changed")  # an app was installed or removed
    assert apps.desktop_apps() is not first
    assert apps.app_identifiers() is not identifiers
    assert len(scans) == 2


def test_shell_widgets_share_one_scan(scans):
    from modules.dock import Dock
    from modules.notch import Notch

    widgets = [Notch(monitor_id=0), Dock(monitor_id=0), Notch(monitor_id=1), Dock(monitor_id=1)]
    widgets[1].update_dock()  # runs on every window opening or closing
    try:
        assert len(scans) == 1
    finally:
        for widget in widgets:
            widget.destroy()
