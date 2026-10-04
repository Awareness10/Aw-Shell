"""Size Qt windows relative to the screen they open on.

Windows ask for a size derived from the focused monitor instead of fixed
pixels. The size is locked (min == max) until the window is mapped so tiling
compositors like Hyprland float it at that size rather than tiling it, then
the lock is released so the user can resize freely.
"""

import json
import subprocess

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QApplication, QWidget

QWIDGETSIZE_MAX = (1 << 24) - 1
# Long enough for the compositor to map the window while it is still locked
RELEASE_DELAY_MS = 500


def get_focused_monitor_name():
    """Name of the monitor Hyprland has focused, or None if unavailable."""
    try:
        result = subprocess.run(
            ["hyprctl", "monitors", "-j"], capture_output=True, text=True
        )
        if result.returncode == 0:
            for m in json.loads(result.stdout):
                if m.get("focused"):
                    return m.get("name")
    except Exception as e:
        print(f"Error getting focused monitor: {e}")
    return None


def target_screen() -> QScreen:
    """The screen the compositor will open a new window on: the focused monitor."""
    name = get_focused_monitor_name()
    for screen in QApplication.screens():
        if screen.name() == name:
            return screen
    return QApplication.primaryScreen()


def fit_size(screen: QScreen, height_fraction: float, width_per_height: float,
             min_size: tuple[int, int]) -> tuple[int, int]:
    """Window size for *screen*: a fraction of its height, width from the aspect."""
    avail = screen.availableGeometry()
    min_w, min_h = min_size
    height = max(min_h, min(round(avail.height() * height_fraction), avail.height()))
    width = max(min_w, min(round(height * width_per_height), avail.width()))
    return width, height


class ScreenFit(QObject):
    """Give *window* a screen-relative initial size and make it float."""

    def __init__(self, window: QWidget, height_fraction: float, width_per_height: float,
                 min_size: tuple[int, int]):
        super().__init__(window)
        self._window = window
        self._min_size = min_size
        self._locked = True
        width, height = fit_size(target_screen(), height_fraction, width_per_height, min_size)
        window.setFixedSize(width, height)
        window.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Show and self._locked:
            self._locked = False
            QTimer.singleShot(RELEASE_DELAY_MS, self.release)
        return False

    def release(self) -> None:
        self._window.setMinimumSize(*self._min_size)
        self._window.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
