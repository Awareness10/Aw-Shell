"""Real-GTK test environment.

Runs the shell's widgets against real GTK/Fabric in a sandbox that cannot
touch the user's session:

- private headless sway (wlroots; has the layer-shell protocol that Fabric
  windows need, which Weston and cage lack) - nothing shows on the real desktop
- private dbus-daemon, used as both session and system bus, with a fake
  UPower (tests_gtk/fake_upower.py)
- fake Hyprland IPC sockets + `hyprctl` stub (tests_gtk/fake_hyprland.py)
- temporary HOME / XDG dirs, with a copy of the install dir's config/
- stub executables for commands with side effects (systemctl, pkill, ...)

The environment is set up at import time, before anything imports gi,
because config.data opens the display when it is imported.

Run separately from the mocked unit tests: `pytest tests_gtk`.
"""

import atexit
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

if "gi" in sys.modules and not hasattr(sys.modules["gi"], "__file__"):
    pytest.exit(
        "tests_gtk needs real GTK but gi is mocked by tests/conftest.py; "
        "run it in its own process: pytest tests_gtk",
        returncode=4,
    )

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from fake_hyprland import FakeHyprland  # noqa: E402

# Commands that would act on the real system; they log to commands.log instead
STUBBED_COMMANDS = [
    "systemctl", "loginctl", "reboot", "poweroff", "shutdown",
    "pkill", "killall", "kill", "uwsm", "nohup",
    "brightnessctl", "bluetoothctl", "nmcli", "playerctl", "wpctl", "pactl",
    "notify-send", "xdg-open", "wl-copy", "wl-paste", "cliphist",
    "hyprsunset", "hyprpicker", "hyprshot", "hyprlock", "hypridle",
    "matugen", "awww", "swww", "nvtop", "play", "cava",
    "grim", "slurp", "wf-recorder", "gpu-screen-recorder", "tmux",
]

# Install-dir entries that get written to; copied instead of symlinked
COPIED_DIRS = ["config", "styles"]
# User state that should not leak into tests
SKIPPED_CONFIG_FILES = {"config.json", "dock.json", "dock.json.bak"}


class Sandbox:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="aw-gtk-tests-"))
        self.home = self.root / "home"
        self.runtime = self.root / "runtime"
        self.bin = self.root / "bin"
        for d in (self.home, self.runtime, self.bin):
            d.mkdir()
        self.runtime.chmod(0o700)
        self.procs: list[subprocess.Popen] = []

    def setup(self):
        self._set_env()
        self._install_dir()
        self._wallpaper()
        self._stub_commands()
        self.hyprland = FakeHyprland(self.runtime, self.bin)
        self._start_dbus()
        self._start_fake_upower()
        self._start_compositor()
        atexit.register(self.teardown)

    def _set_env(self):
        for var in ("DISPLAY", "WAYLAND_SOCKET", "SWAYSOCK", "DBUS_SESSION_BUS_ADDRESS",
                    "DBUS_SYSTEM_BUS_ADDRESS", "PULSE_SERVER", "PIPEWIRE_REMOTE"):
            os.environ.pop(var, None)
        os.environ.update({
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_DATA_HOME": str(self.home / ".local" / "share"),
            "XDG_STATE_HOME": str(self.home / ".local" / "state"),
            "XDG_RUNTIME_DIR": str(self.runtime),
            "GDK_BACKEND": "wayland",
            "HYPRLAND_INSTANCE_SIGNATURE": "awtest",
            "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "GSETTINGS_BACKEND": "memory",
            "NO_AT_BRIDGE": "1",
        })

    def _install_dir(self):
        """Mirror ~/.config/aw-shell: symlink the repo, copy what gets written."""
        install = self.home / ".config" / "aw-shell"
        install.mkdir(parents=True)
        for entry in REPO.iterdir():
            if entry.name.startswith(".") or entry.name in COPIED_DIRS:
                continue
            (install / entry.name).symlink_to(entry)
        for name in COPIED_DIRS:
            shutil.copytree(
                REPO / name, install / name, symlinks=True,
                ignore=lambda d, names: [n for n in names
                                         if n in SKIPPED_CONFIG_FILES or n == "__pycache__"],
            )

    def _wallpaper(self):
        """~/.current.wall always exists on a real install (see modules/wallpapers.py)."""
        example = sorted((REPO / "assets" / "wallpapers_example").glob("*.jpg"))[0]
        (self.home / ".current.wall").symlink_to(example)

    def _stub_commands(self):
        log = self.runtime / "commands.log"
        for name in STUBBED_COMMANDS:
            path = self.bin / name
            path.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n')
            path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def _start_dbus(self):
        proc = subprocess.Popen(
            ["dbus-daemon", "--session", "--nofork", "--print-address=1"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.procs.append(proc)
        address = proc.stdout.readline().strip()
        if not address:
            raise RuntimeError(f"dbus-daemon failed to start:\n{proc.stderr.read()}")
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
        os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = address

    def _start_fake_upower(self):
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).parent / "fake_upower.py")],
            stdout=subprocess.PIPE, text=True,
        )
        self.procs.append(proc)
        if proc.stdout.readline().strip() != "ready":
            raise RuntimeError("fake UPower failed to start")

    def _start_compositor(self):
        if shutil.which("sway") is None:
            pytest.exit("tests_gtk needs sway for a headless layer-shell compositor "
                        "(pacman -S sway / apt install sway)", returncode=4)
        config = self.root / "sway.conf"
        config.write_text("xwayland disable\noutput HEADLESS-1 resolution 1920x1080\n")
        env = dict(os.environ, WLR_BACKENDS="headless", WLR_RENDERER="pixman",
                   WLR_LIBINPUT_NO_DEVICES="1")
        env.pop("WAYLAND_DISPLAY", None)
        log = open(self.root / "sway.log", "w")
        # --unsupported-gpu: sway refuses to start when the host has the Nvidia
        # module loaded, even though the headless pixman backend never uses it
        proc = subprocess.Popen(["sway", "--unsupported-gpu", "--config", str(config)], env=env,
                                stdout=log, stderr=log)
        self.procs.append(proc)
        deadline = time.monotonic() + 10
        while not (sockets := sorted(p.name for p in self.runtime.glob("wayland-*")
                                     if not p.name.endswith(".lock"))):
            if proc.poll() is not None or time.monotonic() > deadline:
                log.flush()
                tail = (self.root / "sway.log").read_text()[-2000:]
                raise RuntimeError(f"sway failed to start:\n{tail}")
            time.sleep(0.05)
        os.environ["WAYLAND_DISPLAY"] = sockets[0]

    def commands(self) -> list[str]:
        log = self.runtime / "commands.log"
        return log.read_text().splitlines() if log.exists() else []

    def teardown(self):
        self.hyprland.close()
        for proc in reversed(self.procs):
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self.procs.clear()
        shutil.rmtree(self.root, ignore_errors=True)


SANDBOX = Sandbox()
SANDBOX.setup()

# Hardcoded outside HOME and shared with a running shell; redirect it
import modules.notifications as _notifications  # noqa: E402

_notifications.PERSISTENT_DIR = str(SANDBOX.root / "notifications")
_notifications.PERSISTENT_HISTORY_FILE = str(SANDBOX.root / "notifications" / "history.json")

from gi.repository import GLib  # noqa: E402


@pytest.fixture
def sandbox():
    """The isolated environment: .hyprland, .commands(), .home, .root."""
    return SANDBOX


@pytest.fixture(autouse=True)
def _reset_hyprland():
    SANDBOX.hyprland.reset()
    yield


def pump(iterations: int = 50) -> None:
    """Run pending GLib callbacks (idle handlers, timeouts that are due)."""
    context = GLib.MainContext.default()
    for _ in range(iterations):
        if not context.iteration(False):
            break


@pytest.fixture
def run_pending():
    return pump
