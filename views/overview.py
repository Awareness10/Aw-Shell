"""
PySide6 overview view — simplified port of modules/overview.py.

Workspace overview showing open windows. Full implementation requires
Hyprland IPC integration for window positions and drag-drop.

This is a placeholder that shows workspace buttons - the full version
with window thumbnails will be implemented later.
"""

import json
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QScrollArea,
)

from core.hyprland import hyprctl_json


def _icon_font(size: int = 16) -> QFont:
    f = QFont("tabler-icons")
    f.setPixelSize(size)
    return f


class WorkspaceButton(QPushButton):
    """Single workspace button showing workspace number and window count."""

    workspace_clicked = Signal(int)

    def __init__(self, ws_id: int, window_count: int = 0, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.ws_id = ws_id
        self.setObjectName("overview-workspace")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(120, 80)
        self.setCheckable(True)
        self.setChecked(is_active)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Workspace number
        num_label = QLabel(str(ws_id))
        num_label.setObjectName("workspace-number")
        num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(num_label)

        # Window count
        if window_count > 0:
            count_label = QLabel(f"{window_count} window{'s' if window_count != 1 else ''}")
            count_label.setObjectName("workspace-count")
            count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(count_label)

        self.clicked.connect(lambda: self.workspace_clicked.emit(ws_id))


class Overview(QWidget):
    """Workspace overview showing all workspaces with window counts."""

    closed = Signal()

    def __init__(self, state, on_close: Callable = None, parent=None):
        super().__init__(parent)
        self.setObjectName("overview")
        self._state = state
        self._on_close = on_close
        self._workspace_buttons = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Workspace Overview")
        title.setObjectName("overview-title")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("\ueb13")  # refresh
        refresh_btn.setFont(_icon_font(16))
        refresh_btn.setObjectName("overview-btn")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Workspace grid
        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setSpacing(8)

        layout.addWidget(self.grid_widget, 1)

        # Hint
        hint = QLabel("Click workspace to switch. Full drag-drop support coming soon.")
        hint.setObjectName("overview-hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def open(self):
        """Called when overview is opened."""
        self.refresh()

    def refresh(self):
        """Refresh workspace data from Hyprland."""
        # Clear existing
        self._workspace_buttons.clear()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get data from Hyprland
        try:
            workspaces = hyprctl_json("workspaces")
            clients = hyprctl_json("clients")
            active_ws = hyprctl_json("activeworkspace")
            active_id = active_ws.get("id", 1)
        except Exception as e:
            print(f"Failed to get Hyprland data: {e}")
            workspaces = []
            clients = []
            active_id = 1

        # Count windows per workspace
        window_counts = {}
        for client in clients:
            ws_id = client.get("workspace", {}).get("id", -1)
            if ws_id > 0:
                window_counts[ws_id] = window_counts.get(ws_id, 0) + 1

        # Create workspace buttons (1-10)
        for i in range(10):
            ws_id = i + 1
            count = window_counts.get(ws_id, 0)
            is_active = ws_id == active_id

            btn = WorkspaceButton(ws_id, count, is_active)
            btn.workspace_clicked.connect(self._switch_workspace)
            self._workspace_buttons.append(btn)

            row = i // 5
            col = i % 5
            self.grid.addWidget(btn, row, col)

    def _switch_workspace(self, ws_id: int):
        """Switch to a workspace."""
        try:
            from core.hyprland import hyprctl
            hyprctl(f"dispatch workspace {ws_id}")
        except Exception as e:
            print(f"Failed to switch workspace: {e}")

        if self._on_close:
            self._on_close()
        self.closed.emit()


def get_overview_stylesheet(theme) -> str:
    """Generate overview stylesheet."""
    t = theme
    return f"""
        #overview {{
            background: transparent;
        }}
        #overview-title {{
            color: {t.text_primary};
            font-size: 16px;
            font-weight: bold;
        }}
        #overview-btn {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 8px;
        }}
        #overview-btn:hover {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #overview-workspace {{
            background: {t.surface_variant};
            border: none;
            border-radius: 12px;
        }}
        #overview-workspace:hover {{
            background: {t.surface};
            border: 1px solid {t.accent};
        }}
        #overview-workspace:checked {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #workspace-number {{
            color: {t.text_primary};
            font-size: 20px;
            font-weight: bold;
        }}
        #overview-workspace:checked #workspace-number {{
            color: {t.on_accent};
        }}
        #workspace-count {{
            color: {t.text_secondary};
            font-size: 11px;
        }}
        #overview-workspace:checked #workspace-count {{
            color: {t.on_accent};
        }}
        #overview-hint {{
            color: {t.text_secondary};
            font-size: 11px;
        }}
    """
