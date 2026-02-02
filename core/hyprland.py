"""
Hyprland IPC listener for the PySide6 shell.

Connects to Hyprland's event socket (.socket2.sock) and command
socket (.socket.sock) to receive workspace changes, monitor focus,
fullscreen events, and to send commands.

Emits signals on ShellState.
"""

import json
import os
import socket
from typing import Optional

from PySide6.QtCore import QObject, QSocketNotifier


def _get_socket_path(name: str) -> str:
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    uid = os.getuid()
    return f"/run/user/{uid}/hypr/{sig}/{name}"


def hyprctl(command: str) -> str:
    """Send a command to Hyprland and return the response."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(_get_socket_path(".socket.sock"))
        sock.sendall(command.encode())
        chunks = []
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks).decode()
    finally:
        sock.close()


def hyprctl_json(command: str) -> object:
    """Send a command with -j flag and parse JSON response."""
    raw = hyprctl(f"-j/{command}")
    return json.loads(raw)


class HyprlandListener(QObject):
    """Listens to Hyprland's event socket and dispatches to ShellState."""

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self._state = state
        self._buffer = b""
        self._sock: Optional[socket.socket] = None
        self._notifier: Optional[QSocketNotifier] = None

        self._connect()

    def _connect(self):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self._sock.connect(_get_socket_path(".socket2.sock"))

        self._notifier = QSocketNotifier(
            self._sock.fileno(),
            QSocketNotifier.Type.Read,
            self,
        )
        self._notifier.activated.connect(self._on_data)

    def _on_data(self):
        try:
            data = self._sock.recv(8192)
        except BlockingIOError:
            return
        except OSError:
            return

        if not data:
            return

        self._buffer += data
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            self._dispatch(line.decode(errors="replace"))

    def _dispatch(self, line: str):
        if ">>" not in line:
            return

        event, _, payload = line.partition(">>")
        event = event.strip()
        payload = payload.strip()

        if event == "workspace" or event == "workspacev2":
            try:
                ws_id = int(payload.split(",")[0])
                self._state.workspace_changed.emit(ws_id)
            except (ValueError, IndexError):
                pass

        elif event == "focusedmon":
            parts = payload.split(",")
            if parts:
                self._state.monitor_focused.emit(parts[0])
                if len(parts) > 1:
                    try:
                        ws_id = int(parts[1])
                        self._state.workspace_changed.emit(ws_id)
                    except ValueError:
                        pass

        elif event == "fullscreen":
            self._state.fullscreen_changed.emit(payload == "1")

        elif event == "activewindowv2":
            pass  # available for future use

        elif event == "monitoraddedv2" or event == "monitorremoved":
            pass  # available for monitor hotplug

    def close(self):
        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier = None
        if self._sock:
            self._sock.close()
            self._sock = None
