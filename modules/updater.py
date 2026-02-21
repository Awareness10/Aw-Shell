"""Aw-Shell Updater — PySide6 version.

Checks for updates, displays a changelog window, and runs
the update process via QProcess. No GTK dependencies.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QThread, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout,
)
from PySide6.QtGui import QColor

from glaze.theme import get_dialog_stylesheet, get_table_container_style, get_current_theme
from glaze.widgets import FramelessMainWindow

from config.settings_constants import APP_NAME, APP_NAME_CAP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _MODULE_DIR.parent

VERSION_FILE = str(_PROJECT_DIR / "version.json")
REMOTE_VERSION_FILE = "/tmp/remote_version.json"
REMOTE_URL = (
    "https://raw.githubusercontent.com/awareness10/Aw-Shell/"
    "refs/heads/main/version.json"
)
REPO_DIR = str(_PROJECT_DIR)

CACHE_DIR = os.path.expanduser(f"~/.cache/{APP_NAME}")

SNOOZE_FILE_NAME = "updater_snooze.txt"
UPDATER_DISABLE_FILE_NAME = "updater_disabled.flag"
SNOOZE_DURATION_SECONDS = 8 * 60 * 60  # 8 hours

# ---------------------------------------------------------------------------
# Backend helpers
# ---------------------------------------------------------------------------


def get_cache_dir() -> str:
    """Return the cache directory path, creating it if necessary."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception as e:
        print(f"Error creating cache directory {CACHE_DIR}: {e}")
    return CACHE_DIR


def get_snooze_file_path() -> str:
    """Return the path to the snooze timestamp file."""
    return os.path.join(get_cache_dir(), SNOOZE_FILE_NAME)


def get_disable_file_path() -> str:
    """Return the path to the updater-disabled flag file."""
    return os.path.join(get_cache_dir(), UPDATER_DISABLE_FILE_NAME)


def fetch_remote_version() -> None:
    """Download the remote version.json with curl."""
    try:
        subprocess.run(
            ["curl", "-sL", "--connect-timeout", "10",
             REMOTE_URL, "-o", REMOTE_VERSION_FILE],
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        print("Error: curl timed out while fetching the remote version.")
    except FileNotFoundError:
        print("Error: curl not found. Please install curl.")
    except Exception as e:
        print(f"Error fetching remote version: {e}")


def get_local_version():
    """Read the local version file and return *(version, changelog)*."""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, "r") as f:
                data = json.load(f)
                return data.get("version", "0.0.0"), data.get("changelog", [])
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in local file: {VERSION_FILE}")
            return "0.0.0", []
        except Exception as e:
            print(f"Error reading local version file {VERSION_FILE}: {e}")
            return "0.0.0", []
    return "0.0.0", []


def get_remote_version():
    """Read the remote version file and return *(version, changelog, download_url, pkg_update)*."""
    if os.path.exists(REMOTE_VERSION_FILE):
        try:
            with open(REMOTE_VERSION_FILE, "r") as f:
                data = json.load(f)
                return (
                    data.get("version", "0.0.0"),
                    data.get("changelog", []),
                    data.get("download_url", "#"),
                    data.get("pkg_update", True),
                )
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in remote file: {REMOTE_VERSION_FILE}")
            return "0.0.0", [], "#", True
        except Exception as e:
            print(f"Error reading remote version file {REMOTE_VERSION_FILE}: {e}")
            return "0.0.0", [], "#", True
    return "0.0.0", [], "#", True


def update_local_version_file() -> None:
    """Replace the local version.json with the downloaded remote one."""
    if os.path.exists(REMOTE_VERSION_FILE):
        try:
            shutil.move(REMOTE_VERSION_FILE, VERSION_FILE)
        except Exception as e:
            print(f"Error updating local version file: {e}")
            raise


def is_connected() -> bool:
    """Return *True* if we can reach www.google.com:80."""
    try:
        socket.create_connection(("www.google.com", 80), timeout=5)
        return True
    except OSError:
        return False


def is_snoozed() -> bool:
    """Return *True* if the snooze window (8 h) has not yet elapsed."""
    snooze_path = get_snooze_file_path()
    if not os.path.exists(snooze_path):
        return False
    try:
        with open(snooze_path, "r") as f:
            ts = float(f.read().strip())
        if time.time() - ts < SNOOZE_DURATION_SECONDS:
            return True
        # Expired — clean up
        os.remove(snooze_path)
    except (ValueError, OSError) as e:
        print(f"Error processing snooze file: {e}")
        try:
            os.remove(snooze_path)
        except OSError:
            pass
    return False


def is_updater_disabled() -> bool:
    """Return *True* if the updater-disabled flag file exists."""
    return os.path.exists(get_disable_file_path())


def write_snooze() -> None:
    """Write the current timestamp to the snooze file."""
    snooze_path = get_snooze_file_path()
    try:
        with open(snooze_path, "w") as f:
            f.write(str(time.time()))
        print(f"Update snoozed. Snooze file at: {snooze_path}")
    except Exception as e:
        print(f"Error creating snooze file {snooze_path}: {e}")


def toggle_updater_disabled() -> bool:
    """Toggle the updater-disabled flag file.  Return the new *disabled* state."""
    disable_path = get_disable_file_path()
    try:
        if os.path.exists(disable_path):
            os.remove(disable_path)
            print("Updater enabled.")
            return False
        else:
            with open(disable_path, "w") as f:
                pass
            print("Updater disabled.")
            return True
    except Exception as e:
        print(f"Error toggling updater state: {e}")
        return os.path.exists(disable_path)


def _version_is_newer(latest: str, current: str) -> bool:
    """Semantic version comparison using tuple of ints."""
    try:
        return tuple(int(x) for x in latest.split(".")) > tuple(int(x) for x in current.split("."))
    except ValueError:
        return latest > current


# ---------------------------------------------------------------------------
# UpdateCheckWorker
# ---------------------------------------------------------------------------


class UpdateCheckWorker(QObject):
    """Runs the update-check logic on a background QThread."""

    update_available = Signal(str, list, bool)  # version, changelog, pkg_update
    no_update = Signal()
    finished = Signal()

    def __init__(self, force: bool = False):
        super().__init__()
        self._force = force

    @Slot()
    def run(self) -> None:
        try:
            if is_updater_disabled() and not self._force:
                print(f"Updater is disabled via {UPDATER_DISABLE_FILE_NAME}. Skipping.")
                self.no_update.emit()
                return

            if not is_connected():
                print("No internet connection. Skipping update check.")
                self.no_update.emit()
                return

            fetch_remote_version()
            latest_version, changelog, _, pkg_update = get_remote_version()

            if self._force:
                print(f"Force mode — opening updater for version {latest_version}.")
                self.update_available.emit(latest_version, changelog, pkg_update)
                return

            if is_snoozed():
                print("Update check snoozed.")
                self.no_update.emit()
                return

            current_version, _ = get_local_version()
            if _version_is_newer(latest_version, current_version) and latest_version != "0.0.0":
                self.update_available.emit(latest_version, changelog, pkg_update)
            else:
                print(f"{APP_NAME_CAP} is up to date.")
                self.no_update.emit()
        finally:
            self.finished.emit()


# ---------------------------------------------------------------------------
# UpdaterWindow
# ---------------------------------------------------------------------------


class UpdaterWindow(FramelessMainWindow):
    """PySide6 updater dialog following the FramelessMainWindow pattern."""

    def __init__(
        self,
        latest_version: str = "0.0.0",
        changelog: list | None = None,
        pkg_update: bool = True,
    ):
        self._latest_version = latest_version
        self._changelog = changelog or []
        self._pkg_update = pkg_update
        self._process: QProcess | None = None

        super().__init__(width=500, height=480, title=f"{APP_NAME_CAP} Updater")
        self.setMinimumSize(400, 380)

    # -- FramelessMainWindow overrides --

    def setup_content(self) -> None:
        self.content_layout.setContentsMargins(16, 12, 16, 16)
        self.content_layout.setSpacing(12)

        # Container with shadow (same pattern as settings dialog)
        container = QFrame()
        container.setObjectName("tableContainer")
        container.setStyleSheet(get_table_container_style())
        container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 80))
        container.setGraphicsEffect(shadow)

        inner = QVBoxLayout(container)
        inner.setContentsMargins(16, 16, 16, 16)
        inner.setSpacing(10)

        # Title
        title = QLabel("Update Available")
        title.setObjectName("updaterTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(title)

        # Info
        self.info_label = QLabel(
            f"A new version ({self._latest_version}) of {APP_NAME_CAP} is available."
        )
        self.info_label.setWordWrap(True)
        inner.addWidget(self.info_label)

        # Changelog header
        cl_header = QLabel("<b>Changelog:</b>")
        inner.addWidget(cl_header)

        # Scrollable changelog
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        if self._changelog:
            joined = "<br>".join(f"&bull; {c}" for c in self._changelog)
        else:
            joined = "No specific changes listed for this version."

        self.changelog_label = QLabel(joined)
        self.changelog_label.setTextFormat(Qt.TextFormat.RichText)
        self.changelog_label.setWordWrap(True)
        self.changelog_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        scroll.setWidget(self.changelog_label)
        inner.addWidget(scroll, 1)

        # Log area (hidden by default)
        self.log_area = QTextEdit()
        self.log_area.setObjectName("updaterLog")
        self.log_area.setReadOnly(True)
        self.log_area.setVisible(False)
        inner.addWidget(self.log_area)

        # Status label (hidden by default)
        self.status_label = QLabel()
        self.status_label.setObjectName("updaterStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setVisible(False)
        inner.addWidget(self.status_label)

        self.content_layout.addWidget(container, 1)

        # Button row
        btn_row = QHBoxLayout()

        self.toggle_btn = QPushButton(
            "Enable Updater" if is_updater_disabled() else "Disable Updater"
        )
        self.toggle_btn.setMinimumHeight(36)
        self.toggle_btn.clicked.connect(self._on_toggle_updater)
        btn_row.addWidget(self.toggle_btn)

        btn_row.addStretch()

        self.later_btn = QPushButton("Later")
        self.later_btn.setMinimumHeight(36)
        self.later_btn.clicked.connect(self._on_later)
        btn_row.addWidget(self.later_btn)

        self.update_btn = QPushButton("Update")
        self.update_btn.setObjectName("updateButton")
        self.update_btn.setMinimumHeight(36)
        self.update_btn.clicked.connect(self._on_update)
        btn_row.addWidget(self.update_btn)

        self.content_layout.addLayout(btn_row)

    def get_extra_stylesheet(self) -> str:
        t = get_current_theme()
        return get_dialog_stylesheet() + f"""
            #updaterTitle {{
                font-size: 20px;
                font-weight: bold;
                color: {t.text_primary};
            }}
            #updateButton {{
                background-color: {t.accent};
                color: {t.text_dark};
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
            }}
            #updateButton:hover {{
                background-color: {t.accent_hover};
            }}
            #updateButton:pressed {{
                background-color: {t.accent_pressed};
            }}
            #updateButton:disabled {{
                background-color: {t.surface_variant};
                color: {t.text_secondary};
            }}
            #updaterLog {{
                font-family: monospace;
                background-color: {t.bg_tertiary};
                border: 1px solid {t.border};
                border-radius: 4px;
                padding: 6px;
            }}
            #updaterStatus {{
                font-weight: bold;
                padding: 4px 0;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """

    # -- Button handlers --

    def _on_toggle_updater(self) -> None:
        now_disabled = toggle_updater_disabled()
        self.toggle_btn.setText(
            "Enable Updater" if now_disabled else "Disable Updater"
        )

    def _on_later(self) -> None:
        write_snooze()
        self.close()

    def _on_update(self) -> None:
        # Disable all buttons
        self.update_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.toggle_btn.setEnabled(False)

        # Show log area and resize
        self.log_area.setVisible(True)
        self.resize(500, 600)

        # Build command
        if self._pkg_update:
            cmd = (
                "curl -fsSL "
                "https://raw.githubusercontent.com/awareness10/Aw-Shell/main/install.sh "
                "| bash"
            )
        else:
            cmd = (
                f'git -C "{REPO_DIR}" pull && '
                f'echo "Reloading in 3..." && sleep 1 && '
                f'echo "2..." && sleep 1 && '
                f'echo "1..." && sleep 1 && '
                f'killall {APP_NAME} && '
                f'setsid python "{REPO_DIR}/main.py"'
            )

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_process_output)
        self._process.finished.connect(self._on_process_finished)
        self._process.start("/bin/bash", ["-lc", cmd])

    def _on_process_output(self) -> None:
        if self._process is None:
            return
        raw = self._process.readAllStandardOutput()
        text = raw.data().decode("utf-8", errors="replace")
        self.log_area.append(text)

    def _on_process_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        if exit_code == 0:
            self._handle_success()
        else:
            self._handle_failure(exit_code)

    def _handle_success(self) -> None:
        try:
            update_local_version_file()
            print("Local version.json updated successfully.")
        except Exception as e:
            print(f"Failed to update local version.json: {e}")

        self.status_label.setText("Update complete. Restarting...")
        self.status_label.setVisible(True)
        QTimer.singleShot(2000, self._restart_app)

    def _handle_failure(self, exit_code: int = 1) -> None:
        t = get_current_theme()
        self.status_label.setText(f"Update failed (exit code {exit_code}).")
        self.status_label.setStyleSheet(f"color: {t.danger}; font-weight: bold;")
        self.status_label.setVisible(True)

        # Re-enable buttons
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        self.toggle_btn.setEnabled(True)

    @staticmethod
    def _restart_app() -> None:
        try:
            print("Restarting application...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"Error during restart: {e}")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

_active_threads: list = []
_active_windows: list = []
_theme_initialized = False


def _ensure_theme() -> None:
    """Initialize the Glaze theme from the current wallpaper (once)."""
    global _theme_initialized
    if _theme_initialized:
        return
    _theme_initialized = True
    wallpaper = Path.home() / ".current.wall"
    if wallpaper.exists():
        try:
            import glaze
            from glaze import generate_theme
            new_theme, backend = generate_theme(image_path=str(wallpaper))
            glaze.theme = new_theme
            sys.modules["glaze.theme"].theme = new_theme  # type: ignore
            print(f"Loaded theme from wallpaper using {backend}")
        except Exception as e:
            print(f"Warning: Could not generate theme from wallpaper: {e}")


def _show_updater(version: str, changelog: list, pkg_update: bool) -> None:
    """Create and display the UpdaterWindow (must be called on the main thread)."""
    _ensure_theme()
    win = UpdaterWindow(
        latest_version=version,
        changelog=changelog,
        pkg_update=pkg_update,
    )
    _active_windows.append(win)
    win.destroyed.connect(lambda: _active_windows.remove(win) if win in _active_windows else None)
    win.show()


def check_for_updates(force: bool = False) -> None:
    """Kick off a background update check.

    Connects signals so that *_show_updater* is invoked on the main thread
    if an update is available.
    """
    thread = QThread()
    worker = UpdateCheckWorker(force=force)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.update_available.connect(_show_updater, Qt.ConnectionType.QueuedConnection)
    worker.finished.connect(thread.quit)
    # Clean up after thread fully stops (avoids cross-thread parenting warnings)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.finished.connect(lambda t=thread: _active_threads.remove(t) if t in _active_threads else None)

    _active_threads.append(thread)
    thread.start()


def run_updater(force: bool = False) -> None:
    """Convenience wrapper compatible with existing callers."""
    check_for_updates(force=force)


def _run_standalone(force: bool = False) -> None:
    """Run the updater as a standalone Qt application.

    Runs the update check synchronously (before the event loop) to avoid
    cross-thread Qt warnings that occur with the QThread approach.
    """
    # Check synchronously — network calls are fast enough for standalone
    if is_updater_disabled() and not force:
        print(f"Updater is disabled via {UPDATER_DISABLE_FILE_NAME}. Skipping.")
        return

    if not is_connected():
        print("No internet connection. Skipping update check.")
        return

    fetch_remote_version()
    latest, changelog, _, pkg_update = get_remote_version()

    if not force:
        if is_snoozed():
            print("Update check snoozed.")
            return
        current, _ = get_local_version()
        if not (_version_is_newer(latest, current) and latest != "0.0.0"):
            print(f"{APP_NAME_CAP} is up to date.")
            return

    # Update available (or forced) — show the window
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    _ensure_theme()
    win = UpdaterWindow(latest_version=latest, changelog=changelog, pkg_update=pkg_update)
    _active_windows.append(win)
    win.destroyed.connect(lambda: _active_windows.remove(win) if win in _active_windows else None)
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    _force = "--force" in sys.argv
    _run_standalone(force=_force)
