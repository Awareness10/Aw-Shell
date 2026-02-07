"""
IPC socket server for the PySide6 shell.

Replaces fabric-cli exec — listens on a Unix socket for commands
like 'open_notch dashboard', 'toggle_bar', etc.

Client usage:
    aw-shell-msg open_notch dashboard
    aw-shell-msg toggle_bar
"""

import os
import socket
import threading

from PySide6.QtCore import QObject, Signal


SOCKET_PATH = f"/tmp/aw-shell-pyside6-{os.getuid()}.sock"


class ShellIPC(QObject):
    """Unix socket server that receives shell commands.

    Runs a listener thread that accepts connections and emits
    command_received on the main Qt thread via Signal.
    """

    command_received = Signal(str, str)  # (command, args)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._socket = None
        self._thread = None
        self._running = False

    def start(self):
        # Clean up stale socket
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass

        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.bind(SOCKET_PATH)
        self._socket.listen(5)
        self._socket.settimeout(1.0)
        self._running = True

        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._socket:
            self._socket.close()
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass

    def _listen(self):
        while self._running:
            try:
                conn, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                data = conn.recv(4096).decode("utf-8").strip()
                if data:
                    parts = data.split(None, 1)
                    cmd = parts[0]
                    args = parts[1] if len(parts) > 1 else ""
                    self.command_received.emit(cmd, args)
                conn.sendall(b"ok\n")
            except Exception:
                pass
            finally:
                conn.close()
