"""
PySide6 emoji picker — port of modules/emoji.py.

Grid-based emoji picker with search and keyboard navigation.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit,
    QPushButton, QLabel, QScrollArea, QFrame,
)


def _icon_font(size: int = 16) -> QFont:
    f = QFont("tabler-icons")
    f.setPixelSize(size)
    return f


class EmojiButton(QPushButton):
    """Single emoji button."""

    def __init__(self, emoji: str, name: str, parent=None):
        super().__init__(emoji, parent)
        self.emoji = emoji
        self.emoji_name = name
        self.setObjectName("emoji-button")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 40)
        self.setToolTip(name)
        self.setFont(QFont("Noto Color Emoji", 18))


class EmojiPicker(QWidget):
    """Emoji picker with search and grid display."""

    closed = Signal()
    COLUMNS = 9
    ROWS = 5

    def __init__(self, state, on_close: Callable = None, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("emoji-picker")
        self._state = state
        self._on_close = on_close
        self._vertical = vertical

        self._all_emojis: Dict[str, dict] = {}
        self._filtered_emojis: List[Tuple[str, dict]] = []
        self._buttons: List[EmojiButton] = []
        self._selected_index = -1

        if vertical:
            self.COLUMNS = 5
            self.ROWS = 9

        self._load_emoji_data()
        self._build_ui()

    def _load_emoji_data(self):
        """Load emoji data from JSON file."""
        emoji_path = Path(__file__).parent.parent / "assets" / "emoji.json"
        if emoji_path.exists():
            try:
                with open(emoji_path, 'r', encoding='utf-8') as f:
                    self._all_emojis = json.load(f)
            except Exception as e:
                print(f"Failed to load emoji data: {e}")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with search
        header = QHBoxLayout()
        header.setSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("emoji-search")
        self.search.setPlaceholderText("Search emojis...")
        self.search.textChanged.connect(self._on_search)
        self.search.returnPressed.connect(self._on_activate)
        header.addWidget(self.search, 1)

        close_btn = QPushButton("\ueb55")  # x icon
        close_btn.setFont(_icon_font(16))
        close_btn.setObjectName("emoji-close")
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self._close)
        header.addWidget(close_btn)

        layout.addLayout(header)

        # Scroll area for emoji grid
        self.scroll = QScrollArea()
        self.scroll.setObjectName("emoji-scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.grid_widget = QWidget()
        self.grid_widget.setObjectName("emoji-grid")
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)

        self.scroll.setWidget(self.grid_widget)
        layout.addWidget(self.scroll, 1)

        # Page info
        self.page_label = QLabel()
        self.page_label.setObjectName("emoji-page")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.page_label)

    def open(self):
        """Called when emoji picker is opened."""
        self.search.clear()
        self.search.setFocus()
        self._arrange_grid()

    def _close(self):
        self._selected_index = -1
        if self._on_close:
            self._on_close()
        self.closed.emit()

    def _on_search(self, text: str):
        self._arrange_grid(text)

    def _on_activate(self):
        if self._selected_index >= 0 and self._selected_index < len(self._buttons):
            btn = self._buttons[self._selected_index]
            self._copy_emoji(btn.emoji)
            self._close()
        elif self._buttons:
            self._copy_emoji(self._buttons[0].emoji)
            self._close()

    def _arrange_grid(self, query: str = ""):
        """Arrange emoji grid based on search query."""
        # Clear existing buttons
        self._buttons.clear()
        self._selected_index = -1
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Filter emojis
        query_lower = query.lower()
        self._filtered_emojis = []
        for emoji_char, emoji_info in self._all_emojis.items():
            if not query or query_lower in (
                emoji_info.get("name", "") + " " + emoji_info.get("group", "")
            ).lower():
                self._filtered_emojis.append((emoji_char, emoji_info))

        # Limit to reasonable amount for display
        display_emojis = self._filtered_emojis[:self.COLUMNS * self.ROWS * 3]

        # Create buttons
        for i, (emoji_char, emoji_info) in enumerate(display_emojis):
            btn = EmojiButton(emoji_char, emoji_info.get("name", ""))
            btn.clicked.connect(lambda checked, e=emoji_char: self._on_emoji_clicked(e))
            self._buttons.append(btn)

            row = i // self.COLUMNS
            col = i % self.COLUMNS
            self.grid.addWidget(btn, row, col)

        # Update page label
        total = len(self._filtered_emojis)
        shown = len(display_emojis)
        if total > shown:
            self.page_label.setText(f"Showing {shown} of {total} emojis")
        else:
            self.page_label.setText(f"{total} emojis")

        # Select first if searching
        if query.strip() and self._buttons:
            self._update_selection(0)

    def _on_emoji_clicked(self, emoji: str):
        self._copy_emoji(emoji)
        self._close()

    def _copy_emoji(self, emoji: str):
        """Copy emoji to clipboard."""
        try:
            subprocess.run(["wl-copy"], input=emoji.encode('utf-8'), check=True)
        except Exception as e:
            print(f"Clipboard copy failed: {e}")

    def _update_selection(self, new_index: int):
        # Remove old selection
        if self._selected_index >= 0 and self._selected_index < len(self._buttons):
            self._buttons[self._selected_index].setProperty("selected", False)
            self._buttons[self._selected_index].style().unpolish(self._buttons[self._selected_index])
            self._buttons[self._selected_index].style().polish(self._buttons[self._selected_index])

        # Add new selection
        if new_index >= 0 and new_index < len(self._buttons):
            self._buttons[new_index].setProperty("selected", True)
            self._buttons[new_index].style().unpolish(self._buttons[new_index])
            self._buttons[new_index].style().polish(self._buttons[new_index])
            self._selected_index = new_index
            self.scroll.ensureWidgetVisible(self._buttons[new_index])
        else:
            self._selected_index = -1

    def _move_selection(self, direction: str):
        if not self._buttons:
            return

        total = len(self._buttons)
        cols = self.COLUMNS

        if self._selected_index == -1:
            if direction in ("down", "right"):
                new_index = 0
            else:
                new_index = total - 1
        else:
            row = self._selected_index // cols
            col = self._selected_index % cols

            if direction == "right":
                new_index = self._selected_index + 1
                if new_index >= total:
                    new_index = total - 1
            elif direction == "left":
                new_index = self._selected_index - 1
                if new_index < 0:
                    new_index = 0
            elif direction == "down":
                new_index = self._selected_index + cols
                if new_index >= total:
                    new_index = total - 1
            elif direction == "up":
                new_index = self._selected_index - cols
                if new_index < 0:
                    new_index = 0
            else:
                return

        self._update_selection(new_index)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self._close()
        elif key == Qt.Key.Key_Up:
            self._move_selection("up")
        elif key == Qt.Key.Key_Down:
            self._move_selection("down")
        elif key == Qt.Key.Key_Left:
            self._move_selection("left")
        elif key == Qt.Key.Key_Right:
            self._move_selection("right")
        else:
            super().keyPressEvent(event)


def get_emoji_stylesheet(theme) -> str:
    """Generate emoji picker stylesheet."""
    t = theme
    return f"""
        #emoji-picker {{
            background: transparent;
        }}
        #emoji-search {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 14px;
        }}
        #emoji-search:focus {{
            border: 1px solid {t.accent};
        }}
        #emoji-close {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 8px;
        }}
        #emoji-close:hover {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #emoji-scroll {{
            background: transparent;
            border: none;
        }}
        #emoji-grid {{
            background: transparent;
        }}
        #emoji-button {{
            background: transparent;
            border: none;
            border-radius: 8px;
        }}
        #emoji-button:hover {{
            background: {t.surface_variant};
        }}
        #emoji-button[selected="true"] {{
            background: {t.accent};
        }}
        #emoji-page {{
            color: {t.text_secondary};
            font-size: 11px;
        }}
    """
