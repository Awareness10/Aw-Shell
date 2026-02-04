"""
PySide6 toolbox view — port of modules/tools.py.

Utility tools: Screenshot, Screen Record, OCR, Color Picker, Game Mode, Pomodoro, Emoji.
"""

import os
import subprocess
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFrame,
)

from config.data import APP_NAME


def _icon_font(size: int = 20) -> QFont:
    f = QFont("tabler-icons")
    f.setPixelSize(size)
    return f


def _get_script_path(name: str) -> str:
    """Get path to a shell script."""
    return str(Path(__file__).parent.parent / "scripts" / name)


class ToolButton(QPushButton):
    """Single tool button with icon."""

    def __init__(self, icon: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setObjectName("tool-button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setMinimumSize(48, 48)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel(icon)
        icon_label.setFont(_icon_font(22))
        icon_label.setObjectName("tool-icon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)


class ToolSeparator(QFrame):
    """Vertical separator between tool groups."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tool-separator")
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFixedWidth(2)


class Toolbox(QWidget):
    """Toolbox with screenshot, recording, and utility tools."""

    closed = Signal()

    def __init__(self, state, on_close: Callable = None, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("toolbox")
        self._state = state
        self._on_close = on_close
        self._vertical = vertical

        # State tracking
        self._recording = False
        self._gamemode = False
        self._pomodoro = False

        self._build_ui()
        self._start_status_timers()

    def _build_ui(self):
        if self._vertical:
            layout = QVBoxLayout(self)
        else:
            layout = QHBoxLayout(self)

        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Screenshot tools
        self.ss_region = ToolButton("\uea97", "Region Screenshot\nShift+Click for mockup")
        self.ss_region.clicked.connect(self._screenshot_region)

        self.ss_window = ToolButton("\uf212", "Window Screenshot\nShift+Click for mockup")
        self.ss_window.clicked.connect(self._screenshot_window)

        self.ss_full = ToolButton("\uea97", "Fullscreen Screenshot\nShift+Click for mockup")
        self.ss_full.clicked.connect(self._screenshot_full)

        self.ss_folder = ToolButton("\uea53", "Screenshots Folder")
        self.ss_folder.clicked.connect(self._open_screenshots)

        # Recording tools
        self.record = ToolButton("\uea53", "Screen Record")
        self.record.clicked.connect(self._toggle_recording)

        self.rec_folder = ToolButton("\uf3a6", "Recordings Folder")
        self.rec_folder.clicked.connect(self._open_recordings)

        # Utility tools
        self.ocr = ToolButton("\uf12b", "OCR - Extract text from screen")
        self.ocr.clicked.connect(self._ocr)

        self.colorpicker = ToolButton("\uea65", "Color Picker")
        self.colorpicker.clicked.connect(self._colorpicker)

        # Toggle tools
        self.gamemode = ToolButton("\ueb4e", "Game Mode\nDisable effects for performance")
        self.gamemode.clicked.connect(self._toggle_gamemode)

        self.pomodoro = ToolButton("\uec13", "Pomodoro Timer")
        self.pomodoro.clicked.connect(self._toggle_pomodoro)

        self.emoji = ToolButton("\ueb8d", "Emoji Picker")
        self.emoji.clicked.connect(self._open_emoji)

        # Add to layout with separators
        for btn in [self.ss_region, self.ss_window, self.ss_full, self.ss_folder]:
            layout.addWidget(btn)

        layout.addWidget(ToolSeparator())

        for btn in [self.record, self.rec_folder]:
            layout.addWidget(btn)

        layout.addWidget(ToolSeparator())

        for btn in [self.ocr, self.colorpicker]:
            layout.addWidget(btn)

        layout.addWidget(ToolSeparator())

        for btn in [self.gamemode, self.pomodoro, self.emoji]:
            layout.addWidget(btn)

    def _start_status_timers(self):
        """Start timers to check tool status."""
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._check_status)
        self._status_timer.start()

    def _check_status(self):
        """Check status of recording, gamemode, pomodoro."""
        # Check recording
        try:
            result = subprocess.run(
                ["pgrep", "-f", "gpu-screen-recorder"],
                capture_output=True
            )
            self._recording = result.returncode == 0
            self.record.setProperty("active", self._recording)
            self.record.style().unpolish(self.record)
            self.record.style().polish(self.record)
        except:
            pass

        # Check pomodoro
        try:
            result = subprocess.run(
                ["pgrep", "-f", "pomodoro.sh"],
                capture_output=True
            )
            self._pomodoro = result.returncode == 0
            self.pomodoro.setProperty("active", self._pomodoro)
            self.pomodoro.style().unpolish(self.pomodoro)
            self.pomodoro.style().polish(self.pomodoro)
        except:
            pass

    def _close_menu(self):
        if self._on_close:
            self._on_close()
        self.closed.emit()

    def _exec(self, cmd: str):
        """Execute shell command asynchronously."""
        try:
            subprocess.Popen(
                cmd,
                shell=True,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"Command failed: {e}")

    def _screenshot_region(self):
        script = _get_script_path("screenshot.sh")
        self._exec(f"bash {script} s")
        self._close_menu()

    def _screenshot_window(self):
        script = _get_script_path("screenshot.sh")
        self._exec(f"bash {script} w")
        self._close_menu()

    def _screenshot_full(self):
        script = _get_script_path("screenshot.sh")
        self._exec(f"bash {script} p")
        self._close_menu()

    def _open_screenshots(self):
        screenshots_dir = os.path.join(
            os.environ.get('XDG_PICTURES_DIR', os.path.expanduser('~/Pictures')),
            'Screenshots'
        )
        os.makedirs(screenshots_dir, exist_ok=True)
        self._exec(f"xdg-open {screenshots_dir}")
        self._close_menu()

    def _toggle_recording(self):
        script = _get_script_path("screenrecord.sh")
        self._exec(f"bash -c 'nohup bash {script} > /dev/null 2>&1 & disown'")
        self._close_menu()

    def _open_recordings(self):
        recordings_dir = os.path.join(
            os.environ.get('XDG_VIDEOS_DIR', os.path.expanduser('~/Videos')),
            'Recordings'
        )
        os.makedirs(recordings_dir, exist_ok=True)
        self._exec(f"xdg-open {recordings_dir}")
        self._close_menu()

    def _ocr(self):
        script = _get_script_path("ocr.sh")
        self._exec(f"bash {script} s")
        self._close_menu()

    def _colorpicker(self):
        script = _get_script_path("hyprpicker.sh")
        self._exec(f"bash {script} -hex")
        self._close_menu()

    def _toggle_gamemode(self):
        script = _get_script_path("gamemode.sh")
        self._exec(f"bash {script}")
        self._close_menu()

    def _toggle_pomodoro(self):
        script = _get_script_path("pomodoro.sh")
        self._exec(f"bash -c 'nohup bash {script} > /dev/null 2>&1 & disown'")
        self._close_menu()

    def _open_emoji(self):
        self._state.notch_opened.emit("emoji")


def get_tools_stylesheet(theme) -> str:
    """Generate toolbox stylesheet."""
    t = theme
    return f"""
        #toolbox {{
            background: transparent;
        }}
        #tool-button {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 12px;
            min-width: 48px;
            min-height: 48px;
        }}
        #tool-button:hover {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #tool-button[active="true"] {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #tool-icon {{
            color: {t.text_primary};
        }}
        #tool-button:hover #tool-icon {{
            color: {t.on_accent};
        }}
        #tool-separator {{
            background: {t.surface_variant};
        }}
    """
