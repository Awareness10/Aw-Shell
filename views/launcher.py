"""
PySide6 launcher view — port of modules/launcher.py.

The launcher provides:
- Application search with fuzzy matching
- Calculator mode (= prefix)
- Conversion mode (; prefix)
- Special commands (:w, :d, :p, etc.)
- Keyboard navigation (up/down/enter/escape)
"""

import json
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Callable

from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QFont, QKeyEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
    QPushButton, QScrollArea, QFrame, QSizePolicy,
)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from config.data import APP_NAME, CACHE_DIR, HOME_DIR


def _icon_font(size: int = 16) -> QFont:
    f = QFont("tabler-icons")
    f.setPixelSize(size)
    return f


# Desktop application discovery
class DesktopApp:
    """Represents a .desktop application entry."""

    def __init__(self, path: str):
        self.path = path
        self.name = ""
        self.display_name = ""
        self.generic_name = ""
        self.description = ""
        self.executable = ""
        self.command_line = ""
        self.icon_name = ""
        self.window_class = ""
        self.categories = []
        self.no_display = False
        self._parse()

    def _parse(self):
        try:
            with open(self.path, 'r', encoding='utf-8', errors='replace') as f:
                in_desktop_entry = False
                for line in f:
                    line = line.strip()
                    if line == "[Desktop Entry]":
                        in_desktop_entry = True
                        continue
                    if line.startswith("[") and in_desktop_entry:
                        break  # New section
                    if not in_desktop_entry or "=" not in line:
                        continue

                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()

                    if key == "Name":
                        self.display_name = value
                        if not self.name:
                            self.name = value
                    elif key == "GenericName":
                        self.generic_name = value
                    elif key == "Comment":
                        self.description = value
                    elif key == "Exec":
                        self.command_line = value
                        # Extract executable
                        parts = value.split()
                        if parts:
                            self.executable = parts[0].split("/")[-1]
                    elif key == "Icon":
                        self.icon_name = value
                    elif key == "StartupWMClass":
                        self.window_class = value
                    elif key == "Categories":
                        self.categories = value.split(";")
                    elif key == "NoDisplay":
                        self.no_display = value.lower() == "true"
        except Exception:
            pass

    def launch(self):
        """Launch the application."""
        if self.command_line:
            # Remove field codes like %f %u %F %U
            cmd = re.sub(r'%[fFuUdDnNickvm]', '', self.command_line).strip()
            try:
                subprocess.Popen(
                    cmd,
                    shell=True,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                print(f"Failed to launch {self.display_name}: {e}")

    def get_icon(self, size: int = 24) -> Optional[QIcon]:
        """Get application icon."""
        if not self.icon_name:
            return None

        # Check if it's a path
        if "/" in self.icon_name:
            if os.path.exists(self.icon_name):
                return QIcon(self.icon_name)

        # Try theme icons
        icon = QIcon.fromTheme(self.icon_name)
        if not icon.isNull():
            return icon

        # Search common icon paths
        icon_dirs = [
            "/usr/share/icons/hicolor",
            "/usr/share/pixmaps",
            os.path.expanduser("~/.local/share/icons"),
        ]
        for base in icon_dirs:
            for ext in [".png", ".svg", ".xpm"]:
                for subdir in ["48x48/apps", "scalable/apps", "256x256/apps", ""]:
                    path = os.path.join(base, subdir, f"{self.icon_name}{ext}")
                    if os.path.exists(path):
                        return QIcon(path)

        return None


def get_desktop_applications() -> List[DesktopApp]:
    """Discover all desktop applications."""
    apps = []
    seen = set()

    app_dirs = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        os.path.expanduser("~/.local/share/applications"),
        "/var/lib/flatpak/exports/share/applications",
        os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    ]

    for app_dir in app_dirs:
        if not os.path.isdir(app_dir):
            continue
        for filename in os.listdir(app_dir):
            if not filename.endswith(".desktop"):
                continue
            if filename in seen:
                continue
            seen.add(filename)

            path = os.path.join(app_dir, filename)
            app = DesktopApp(path)
            if app.display_name and not app.no_display:
                apps.append(app)

    return sorted(apps, key=lambda a: (a.display_name or "").lower())


class AppSlot(QPushButton):
    """Single application entry in the launcher."""

    def __init__(self, app: DesktopApp, parent=None):
        super().__init__(parent)
        self.app = app
        self.setObjectName("app-slot")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Icon
        icon = app.get_icon(24)
        if icon:
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(QSize(24, 24)))
            icon_label.setFixedSize(24, 24)
            layout.addWidget(icon_label)
        else:
            # Fallback icon
            icon_label = QLabel("\uf1fd")  # apps icon
            icon_label.setFont(_icon_font(18))
            icon_label.setFixedSize(24, 24)
            layout.addWidget(icon_label)

        # Name
        name_label = QLabel(app.display_name or "Unknown")
        name_label.setObjectName("app-name")
        layout.addWidget(name_label)

        # Description (if available)
        if app.description:
            desc_label = QLabel(app.description)
            desc_label.setObjectName("app-desc")
            desc_label.setStyleSheet("color: #888;")
            layout.addWidget(desc_label, 1)
        else:
            layout.addStretch()

        self.setToolTip(app.description or app.display_name)
        self.clicked.connect(self._launch)

    def _launch(self):
        self.app.launch()


class HistorySlot(QPushButton):
    """Single history entry for calculator/conversion."""

    def __init__(self, text: str, on_copy: Callable, parent=None):
        super().__init__(parent)
        self._text = text
        self._on_copy = on_copy
        self.setObjectName("history-slot")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        label = QLabel(text)
        label.setObjectName("history-text")
        layout.addWidget(label)

        self.clicked.connect(self._copy)

    def _copy(self):
        # Extract result part
        if "=>" in self._text:
            result = self._text.split("=>", 1)[1].strip()
        else:
            result = self._text
        self._on_copy(result)


class Launcher(QWidget):
    """Application launcher with search, calculator, and conversion modes."""

    closed = Signal()

    def __init__(self, state, on_close: Callable = None, parent=None):
        super().__init__(parent)
        self.setObjectName("launcher")
        self._state = state
        self._on_close = on_close
        self._all_apps: List[DesktopApp] = []
        self._filtered_apps: List[DesktopApp] = []
        self._selected_index = -1
        self._slots: List[QPushButton] = []

        # History
        self._calc_history: List[str] = []
        self._conv_history: List[str] = []
        self._load_history()

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with search
        header = QHBoxLayout()
        header.setSpacing(8)

        # Settings button
        self.settings_btn = QPushButton("\uea8c")  # settings icon
        self.settings_btn.setFont(_icon_font(16))
        self.settings_btn.setObjectName("launcher-btn")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self._open_settings)
        header.addWidget(self.settings_btn)

        # Search entry
        self.search = QLineEdit()
        self.search.setObjectName("launcher-search")
        self.search.setPlaceholderText("Search applications...")
        self.search.textChanged.connect(self._on_text_changed)
        self.search.returnPressed.connect(self._on_activate)
        header.addWidget(self.search, 1)

        # Close button
        self.close_btn = QPushButton("\ueb55")  # x icon
        self.close_btn.setFont(_icon_font(16))
        self.close_btn.setObjectName("launcher-btn")
        self.close_btn.setFixedSize(36, 36)
        self.close_btn.setToolTip("Close")
        self.close_btn.clicked.connect(self._close)
        header.addWidget(self.close_btn)

        layout.addLayout(header)

        # Scroll area for results
        self.scroll = QScrollArea()
        self.scroll.setObjectName("launcher-scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.viewport = QWidget()
        self.viewport.setObjectName("launcher-viewport")
        self.viewport_layout = QVBoxLayout(self.viewport)
        self.viewport_layout.setContentsMargins(0, 0, 0, 0)
        self.viewport_layout.setSpacing(2)
        self.viewport_layout.addStretch()

        self.scroll.setWidget(self.viewport)
        layout.addWidget(self.scroll, 1)

        # Hint label
        self.hint = QLabel("Type to search • = calculator • ; conversion • : commands")
        self.hint.setObjectName("launcher-hint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint)

    def open(self):
        """Open the launcher and refresh apps."""
        self._all_apps = get_desktop_applications()
        self.search.clear()
        self.search.setFocus()
        self._arrange_viewport()

    def _close(self):
        self._clear_viewport()
        self._selected_index = -1
        if self._on_close:
            self._on_close()
        self.closed.emit()

    def _load_history(self):
        calc_path = os.path.join(CACHE_DIR, "calc.json")
        conv_path = os.path.join(CACHE_DIR, "conversion.json")

        if os.path.exists(calc_path):
            try:
                with open(calc_path, 'r') as f:
                    self._calc_history = json.load(f)
            except:
                pass

        if os.path.exists(conv_path):
            try:
                with open(conv_path, 'r') as f:
                    self._conv_history = json.load(f)
            except:
                pass

    def _save_calc_history(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, "calc.json"), 'w') as f:
            json.dump(self._calc_history, f)

    def _save_conv_history(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, "conversion.json"), 'w') as f:
            json.dump(self._conv_history, f)

    def _on_text_changed(self, text: str):
        if text.startswith("="):
            self._show_calc_history()
        elif text.startswith(";"):
            self._show_conv_history()
        else:
            self._arrange_viewport(text)

    def _on_activate(self):
        text = self.search.text()

        # Calculator mode
        if text.startswith("="):
            if self._selected_index == -1:
                self._evaluate_calc(text)
            else:
                self._copy_selected()
            return

        # Conversion mode
        if text.startswith(";"):
            if self._selected_index == -1:
                self._evaluate_conv(text)
            else:
                self._copy_selected()
            return

        # Commands
        if text.startswith(":"):
            self._handle_command(text)
            return

        # Launch selected app
        if self._slots and self._selected_index >= 0:
            slot = self._slots[self._selected_index]
            if isinstance(slot, AppSlot):
                slot.app.launch()
                self._close()
        elif self._slots:
            # Launch first app
            slot = self._slots[0]
            if isinstance(slot, AppSlot):
                slot.app.launch()
                self._close()

    def _handle_command(self, text: str):
        cmd = text.strip()
        if cmd == ":w":
            self._state.notch_opened.emit("wallpapers")
        elif cmd == ":d":
            self._state.notch_opened.emit("dashboard")
        elif cmd == ":p":
            self._state.notch_opened.emit("power")
        elif cmd in (":settings", ":config"):
            self._open_settings()
            self._close()

    def _open_settings(self):
        config_script = os.path.join(HOME_DIR, f".config/{APP_NAME}/config/config.py")
        subprocess.Popen(["python", config_script], start_new_session=True)

    def _clear_viewport(self):
        self._slots.clear()
        while self.viewport_layout.count() > 1:
            item = self.viewport_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _arrange_viewport(self, query: str = ""):
        self._clear_viewport()
        self._selected_index = -1

        # Score and filter apps
        scored = []
        for app in self._all_apps:
            score = self._score_app(app, query) if query else 1
            if score > 0:
                scored.append((score, app))

        # Sort by score descending
        scored.sort(key=lambda x: (-x[0], (x[1].display_name or "").lower()))

        # Add slots
        for _, app in scored[:50]:  # Limit to 50 results
            slot = AppSlot(app)
            slot.clicked.connect(self._close)
            self._slots.append(slot)
            self.viewport_layout.insertWidget(self.viewport_layout.count() - 1, slot)

        # Auto-select first if query
        if query.strip() and self._slots:
            self._update_selection(0)

    def _score_app(self, app: DesktopApp, query: str) -> int:
        """Calculate relevance score for an app."""
        q = query.lower()
        name = (app.display_name or "").lower()
        app_name = (app.name or "").lower()
        generic = (app.generic_name or "").lower()
        exe = (app.executable or "").lower()

        # Exact match
        if name == q:
            return 10000
        if app_name == q or exe == q:
            return 9000

        # Starts with
        if name.startswith(q):
            return 8000 - len(name)
        if app_name.startswith(q) or exe.startswith(q):
            return 7000 - len(name)

        # Word starts with
        for i, word in enumerate(name.split()):
            if word.startswith(q):
                return 6000 - (i * 100) - len(name)

        # Substring
        if q in name:
            return 4000 - name.find(q) - len(name)
        if q in f"{app_name} {generic} {exe}":
            return 3000 - len(name)

        # Fuzzy match
        if self._fuzzy_match(q, name):
            return 1000

        return 0

    def _fuzzy_match(self, query: str, text: str) -> bool:
        """Check if all chars in query appear in text in order."""
        it = iter(text)
        return all(c in it for c in query)

    def _show_calc_history(self):
        self._clear_viewport()
        self._selected_index = -1

        for item in self._calc_history:
            slot = HistorySlot(item, self._copy_to_clipboard)
            self._slots.append(slot)
            self.viewport_layout.insertWidget(self.viewport_layout.count() - 1, slot)

    def _show_conv_history(self):
        self._clear_viewport()
        self._selected_index = -1

        for item in self._conv_history:
            slot = HistorySlot(item, self._copy_to_clipboard)
            self._slots.append(slot)
            self.viewport_layout.insertWidget(self.viewport_layout.count() - 1, slot)

    def _evaluate_calc(self, text: str):
        """Evaluate calculator expression."""
        expr = text.lstrip("=").strip()
        if not expr:
            return

        if not HAS_NUMPY:
            result_str = "Error: numpy not installed"
        else:
            # Replace common math symbols
            replacements = {
                "^": "**", "×": "*", "÷": "/",
                "π": "np.pi", "pi": "np.pi", "e": "np.e",
                "sin(": "np.sin(", "cos(": "np.cos(", "tan(": "np.tan(",
                "log(": "np.log10(", "ln(": "np.log(",
                "sqrt(": "np.sqrt(", "abs(": "np.abs(", "exp(": "np.exp(",
            }
            for old, new in replacements.items():
                expr = expr.replace(old, new)

            # Factorial
            expr = re.sub(r'(\d+)!', r'np.math.factorial(\1)', expr)

            # Brackets
            for old, new in [("[", "("), ("]", ")"), ("{", "("), ("}", ")")]:
                expr = expr.replace(old, new)

            safe_dict = {'np': np, 'math': math}
            try:
                result = eval(expr, {"__builtins__": None}, safe_dict)
                if isinstance(result, (int, float)):
                    if isinstance(result, int) or (isinstance(result, float) and result.is_integer()):
                        result_str = str(int(result))
                    else:
                        result_str = f"{float(result):.10g}"
                else:
                    result_str = str(result)
            except Exception as e:
                result_str = f"Error: {e}"

        # Add to history
        entry = f"{text} => {result_str}"
        self._calc_history.insert(0, entry)
        self._save_calc_history()
        self._show_calc_history()

    def _evaluate_conv(self, text: str):
        """Evaluate conversion expression (placeholder)."""
        expr = text.lstrip(";").strip()
        if not expr:
            return

        # For now, just echo back - full conversion requires the Conversion class
        result_str = "Conversion not implemented yet"

        entry = f"{text} => {result_str}"
        self._conv_history.insert(0, entry)
        self._save_conv_history()
        self._show_conv_history()

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard using wl-copy."""
        try:
            subprocess.run(["wl-copy"], input=text.encode(), check=True)
        except Exception as e:
            print(f"Clipboard copy failed: {e}")

    def _copy_selected(self):
        """Copy selected history item."""
        if self._selected_index >= 0 and self._selected_index < len(self._slots):
            slot = self._slots[self._selected_index]
            if isinstance(slot, HistorySlot):
                slot._copy()

    def _update_selection(self, new_index: int):
        # Remove old selection
        if self._selected_index >= 0 and self._selected_index < len(self._slots):
            self._slots[self._selected_index].setProperty("selected", False)
            self._slots[self._selected_index].style().unpolish(self._slots[self._selected_index])
            self._slots[self._selected_index].style().polish(self._slots[self._selected_index])

        # Add new selection
        if new_index >= 0 and new_index < len(self._slots):
            self._slots[new_index].setProperty("selected", True)
            self._slots[new_index].style().unpolish(self._slots[new_index])
            self._slots[new_index].style().polish(self._slots[new_index])
            self._selected_index = new_index

            # Scroll to visible
            self.scroll.ensureWidgetVisible(self._slots[new_index])
        else:
            self._selected_index = -1

    def _move_selection(self, delta: int):
        if not self._slots:
            return

        if self._selected_index == -1 and delta == 1:
            new_index = 0
        else:
            new_index = self._selected_index + delta

        new_index = max(0, min(new_index, len(self._slots) - 1))
        self._update_selection(new_index)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        print(f"[Launcher] keyPressEvent: key={key}, Qt.Key_Escape={Qt.Key.Key_Escape}", flush=True)

        if key == Qt.Key.Key_Escape:
            self._close()
        elif key == Qt.Key.Key_Down:
            self._move_selection(1)
        elif key == Qt.Key.Key_Up:
            self._move_selection(-1)
        else:
            super().keyPressEvent(event)


def get_launcher_stylesheet(theme) -> str:
    """Generate launcher-specific stylesheet."""
    t = theme
    return f"""
        #launcher {{
            background: transparent;
        }}
        #launcher-search {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 14px;
        }}
        #launcher-search:focus {{
            background: {t.surface};
            border: 1px solid {t.accent};
        }}
        #launcher-btn {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 8px;
        }}
        #launcher-btn:hover {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #launcher-scroll {{
            background: transparent;
            border: none;
        }}
        #launcher-viewport {{
            background: transparent;
        }}
        #app-slot, #history-slot {{
            background: transparent;
            border: none;
            border-radius: 8px;
            text-align: left;
        }}
        #app-slot:hover, #history-slot:hover {{
            background: {t.surface_variant};
        }}
        #app-slot[selected="true"], #history-slot[selected="true"] {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #app-name {{
            color: {t.text_primary};
            font-weight: 500;
        }}
        #app-desc {{
            color: {t.text_secondary};
            font-size: 12px;
        }}
        #history-text {{
            color: {t.text_primary};
        }}
        #launcher-hint {{
            color: {t.text_secondary};
            font-size: 11px;
        }}
    """
