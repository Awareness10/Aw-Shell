"""Fake Hyprland for GTK tests: IPC sockets plus a `hyprctl` stub.

Both answer from the same JSON state file and log every command, so tests
never reach the real compositor and can assert on what the shell sent.
"""

import json
import os
import socketserver
import stat
import sys
import threading
from pathlib import Path

MONITOR = {
    "id": 0,
    "name": "HEADLESS-1",
    "description": "Headless test output",
    "make": "headless",
    "model": "headless",
    "width": 1920,
    "height": 1080,
    "refreshRate": 60.0,
    "x": 0,
    "y": 0,
    "scale": 1.0,
    "transform": 0,
    "focused": True,
    "dpmsStatus": True,
    "activeWorkspace": {"id": 1, "name": "1"},
    "specialWorkspace": {"id": 0, "name": ""},
    "reserved": [0, 0, 0, 0],
}

WORKSPACE = {
    "id": 1,
    "name": "1",
    "monitor": "HEADLESS-1",
    "monitorID": 0,
    "windows": 1,
    "hasfullscreen": False,
    "lastwindow": "0x1",
    "lastwindowtitle": "Test Window",
}

CLIENT = {
    "address": "0x1",
    "mapped": True,
    "hidden": False,
    "at": [10, 10],
    "size": [800, 600],
    "workspace": {"id": 1, "name": "1"},
    "floating": False,
    "monitor": 0,
    "class": "kitty",
    "title": "Test Window",
    "initialClass": "kitty",
    "initialTitle": "Test Window",
    "pid": 1,
    "xwayland": False,
    "pinned": False,
    "fullscreen": 0,
    "focusHistoryID": 0,
}

DEFAULT_STATE = {
    "monitors": [MONITOR],
    "workspaces": [WORKSPACE],
    "activeworkspace": WORKSPACE,
    "clients": [CLIENT],
    "activewindow": CLIENT,
    "devices": {
        "mice": [],
        "keyboards": [{
            "address": "0x2",
            "name": "test-keyboard",
            "layout": "us",
            "active_keymap": "English (US)",
            "main": True,
        }],
    },
    "layers": {},
}


def reply(state: dict, request: str) -> str:
    """Answer a Hyprland request (`j/monitors`, `/dispatch ...`, `monitors -j`)."""
    words = request.replace("/", " ").split()
    as_json = "j" in words or "-j" in words
    words = [w for w in words if w not in ("j", "-j", "--batch")]
    name = words[0] if words else ""
    if name in state:
        return json.dumps(state[name]) if as_json else str(state[name])
    return "ok"


class _Commands(socketserver.BaseRequestHandler):
    def handle(self):
        request = self.request.recv(65536).decode()
        self.server.log.append(request)
        self.request.sendall(reply(self.server.read_state(), request).encode())


class _Events(socketserver.BaseRequestHandler):
    def handle(self):
        # Hold the event stream open; tests push events via FakeHyprland.emit
        self.server.clients.append(self.request)
        self.server.closed.wait()


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class FakeHyprland:
    def __init__(self, runtime_dir: Path, bin_dir: Path, signature: str = "awtest"):
        self.dir = runtime_dir / "hypr" / signature
        self.dir.mkdir(parents=True)
        self.signature = signature
        self.state_file = runtime_dir / "hypr-state.json"
        self.log_file = runtime_dir / "hyprctl.log"
        self.log: list[str] = []
        self.reset()
        self._write_hyprctl(bin_dir / "hyprctl")

        self.commands = _Server(str(self.dir / ".socket.sock"), _Commands)
        self.commands.log = self.log
        self.commands.read_state = self.read_state
        self.events = _Server(str(self.dir / ".socket2.sock"), _Events)
        self.events.clients = []
        self.events.closed = threading.Event()
        for server in (self.commands, self.events):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def read_state(self) -> dict:
        return json.loads(self.state_file.read_text())

    def reset(self) -> None:
        self.state_file.write_text(json.dumps(DEFAULT_STATE))
        self.log_file.write_text("")
        self.log.clear()

    def emit(self, event: str, data: str = "") -> None:
        """Send `event>>data` to every connected event listener."""
        for conn in self.events.clients:
            conn.sendall(f"{event}>>{data}\n".encode())

    def hyprctl_calls(self) -> list[str]:
        return [line for line in self.log_file.read_text().splitlines() if line]

    def close(self) -> None:
        self.events.closed.set()
        for server in (self.commands, self.events):
            server.shutdown()
            server.server_close()

    def _write_hyprctl(self, path: Path) -> None:
        path.write_text(
            f"#!{sys.executable}\n"
            "import sys\n"
            f"sys.path.insert(0, {str(Path(__file__).parent)!r})\n"
            "from fake_hyprland import main\n"
            "main()\n"
        )
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


def main() -> None:
    """Entry point for the `hyprctl` stub."""
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    request = " ".join(sys.argv[1:])
    with open(runtime / "hyprctl.log", "a") as f:
        f.write(request + "\n")
    state = json.loads((runtime / "hypr-state.json").read_text())
    print(reply(state, request))
