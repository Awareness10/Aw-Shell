"""
PySide6 power menu — port of modules/power.py.

Power actions: Lock, Suspend, Logout, Reboot, Shutdown.
"""

import subprocess
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
)


def _icon_font(size: int = 24) -> QFont:
    f = QFont("tabler-icons")
    f.setPixelSize(size)
    return f


class PowerButton(QPushButton):
    """Single power action button with icon and label."""

    def __init__(self, icon: str, label: str, tooltip: str, action: Callable, parent=None):
        super().__init__(parent)
        self.setObjectName("power-button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setMinimumSize(80, 80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(_icon_font(28))
        icon_label.setObjectName("power-icon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Label
        text_label = QLabel(label)
        text_label.setObjectName("power-label")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)

        self.clicked.connect(action)


class PowerMenu(QWidget):
    """Power menu with lock, suspend, logout, reboot, shutdown."""

    closed = Signal()

    def __init__(self, state, on_close: Callable = None, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("power-menu")
        self._state = state
        self._on_close = on_close
        self._vertical = vertical

        self._build_ui()

    def _build_ui(self):
        if self._vertical:
            layout = QVBoxLayout(self)
        else:
            layout = QHBoxLayout(self)

        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icons from tabler-icons
        self.lock_btn = PowerButton(
            "\uea88",  # lock
            "Lock",
            "Lock screen",
            self._lock,
        )
        self.suspend_btn = PowerButton(
            "\uf4b6",  # zzz / moon-zzz
            "Suspend",
            "Suspend system",
            self._suspend,
        )
        self.logout_btn = PowerButton(
            "\uea7c",  # logout
            "Logout",
            "Logout of session",
            self._logout,
        )
        self.reboot_btn = PowerButton(
            "\ueb13",  # refresh
            "Reboot",
            "Reboot system",
            self._reboot,
        )
        self.shutdown_btn = PowerButton(
            "\ueb0d",  # power
            "Shutdown",
            "Power off system",
            self._shutdown,
        )

        for btn in [self.lock_btn, self.suspend_btn, self.logout_btn,
                    self.reboot_btn, self.shutdown_btn]:
            layout.addWidget(btn)

    def _close_menu(self):
        if self._on_close:
            self._on_close()
        self.closed.emit()

    def _exec(self, cmd: str):
        """Execute a shell command asynchronously."""
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

    def _lock(self):
        print("Locking screen...")
        self._exec("loginctl lock-session")
        self._close_menu()

    def _suspend(self):
        print("Suspending system...")
        self._exec("systemctl suspend")
        self._close_menu()

    def _logout(self):
        print("Logging out...")
        self._exec("hyprctl dispatch exit")
        self._close_menu()

    def _reboot(self):
        print("Rebooting system...")
        self._exec("systemctl reboot")
        self._close_menu()

    def _shutdown(self):
        print("Powering off...")
        self._exec("systemctl poweroff")
        self._close_menu()


def get_power_stylesheet(theme) -> str:
    """Generate power menu stylesheet."""
    t = theme
    return f"""
        #power-menu {{
            background: transparent;
        }}
        #power-button {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 16px;
            min-width: 80px;
            min-height: 80px;
        }}
        #power-button:hover {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #power-button:hover #power-icon,
        #power-button:hover #power-label {{
            color: {t.on_accent};
        }}
        #power-icon {{
            color: {t.text_primary};
        }}
        #power-label {{
            color: {t.text_secondary};
            font-size: 12px;
        }}
    """
