"""The sandbox must keep tests away from the user's real session."""

import os
import shutil
import subprocess
from pathlib import Path

from gi.repository import Gdk, Gio


def test_home_is_temporary(sandbox):
    assert Path.home() == sandbox.home
    assert str(sandbox.root).startswith(os.environ.get("TMPDIR", "/tmp"))


def test_config_data_uses_sandbox_paths(sandbox):
    import config.data as data

    assert data.AW_CONFIG_DIR == sandbox.home / ".config" / "aw-shell" / "config"
    assert not data.AW_CONFIG_DIR.is_symlink()


def test_display_is_sandbox_compositor(sandbox):
    display = Gdk.Display.get_default()
    assert display.get_name() == os.environ["WAYLAND_DISPLAY"]
    assert (sandbox.runtime / display.get_name()).is_socket()
    monitor = display.get_monitor(0)
    assert monitor.get_geometry().width == 1920


def test_hyprctl_is_the_stub(sandbox):
    assert Path(shutil.which("hyprctl")).parent == sandbox.bin
    out = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True).stdout
    assert "HEADLESS-1" in out
    assert sandbox.hyprland.hyprctl_calls() == ["monitors -j"]


def test_hyprland_socket_is_fake(sandbox):
    from fabric.hyprland.service import Hyprland

    reply = Hyprland.send_command("j/monitors").reply.decode()
    assert "HEADLESS-1" in reply
    assert sandbox.hyprland.log == ["j/monitors"]


def test_side_effect_commands_are_stubbed(sandbox):
    for name in ("systemctl", "pkill", "brightnessctl", "uwsm"):
        assert Path(shutil.which(name)).parent == sandbox.bin
    subprocess.run(["systemctl", "suspend"])
    assert "systemctl suspend" in sandbox.commands()


def test_dbus_buses_are_private():
    session = Gio.bus_get_sync(Gio.BusType.SESSION)
    system = Gio.bus_get_sync(Gio.BusType.SYSTEM)
    assert session.get_unique_name() is not None
    names = session.call_sync(
        "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "ListNames", None, None, Gio.DBusCallFlags.NONE, -1, None,
    ).unpack()[0]
    # A real session bus would have the notification daemon, portals, etc.
    assert "org.freedesktop.Notifications" not in names
    assert os.environ["DBUS_SYSTEM_BUS_ADDRESS"] == os.environ["DBUS_SESSION_BUS_ADDRESS"]
    assert system is not None


def test_notification_history_redirected(sandbox):
    import modules.notifications as notifications

    assert notifications.PERSISTENT_HISTORY_FILE.startswith(str(sandbox.root))
