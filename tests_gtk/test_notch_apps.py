"""The notch finds apps installed after it started (it used to keep the
desktop app map from startup)."""

from types import SimpleNamespace


def test_finds_apps_installed_after_startup(monkeypatch, run_pending):
    from modules.notch import Notch
    from utils import apps

    notch = Notch(monitor_id=0)
    run_pending()
    try:
        assert notch.find_app("brand-new-app") is None
        new_app = SimpleNamespace(name="brand-new-app")
        # What the .desktop file monitor leads to: a fresh scan with the new app
        monkeypatch.setitem(apps._shared, "identifiers", {"brand-new-app": new_app})
        assert notch.find_app("Brand-New-App") is new_app
    finally:
        notch.destroy()
        run_pending()
