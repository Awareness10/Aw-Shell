"""
Aw-Shell Settings Dialog

Desktop shell configuration panel with:
- Key Bindings (20 keybindings)
- Appearance (wallpapers, layout, components)
- System (monitors, terminal, metrics)
- About (links, credits)
"""

import os
import sys
import webbrowser
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFormLayout, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget
)
from PySide6.QtGui import QColor, QPixmap

from pyqt_theme.theme import get_dialog_stylesheet, get_table_container_style, get_current_theme
from pyqt_theme.widgets import ThemedComboBox, FramelessMainWindow

from config.settings_bridge import get_bridge

from config.settings_utils import APP_NAME, APP_NAME_CAP
from config.settings_constants import DEFAULTS

# get_bridge,
# Constants matching the original GTK implementation
POSITIONS = ["Top", "Bottom", "Left", "Right"]
THEMES = ["Pills", "Dense", "Edge"]
PANEL_THEMES = ["Notch", "Panel"]
PANEL_POSITIONS = ["Start", "Center", "End"]
NOTIFICATION_POSITIONS = ["Top", "Bottom"]
METRIC_NAMES = {"cpu": "CPU", "ram": "RAM", "disk": "Disk", "gpu": "GPU"}

COMPONENT_DISPLAY_NAMES = {
    "button_apps": "App Launcher Button",
    "systray": "System Tray",
    "control": "Control Panel",
    "network": "Network Applet",
    "button_tools": "Toolbox Button",
    "sysprofiles": "Powerprofiles Switcher",
    "button_overview": "Overview Button",
    "ws_container": "Workspaces",
    "weather": "Weather Widget",
    "battery": "Battery Indicator",
    "metrics": "System Metrics",
    "language": "Language Indicator",
    "date_time": "Date & Time",
    "button_power": "Power Button",
}

KEYBIND_DEFINITIONS: List[Tuple[str, str, str]] = [
    (f"Reload {APP_NAME_CAP}", "prefix_restart", "suffix_restart"),
    ("Message", "prefix_axmsg", "suffix_axmsg"),
    ("Dashboard", "prefix_dash", "suffix_dash"),
    ("Bluetooth", "prefix_bluetooth", "suffix_bluetooth"),
    ("Pins", "prefix_pins", "suffix_pins"),
    ("Kanban", "prefix_kanban", "suffix_kanban"),
    ("App Launcher", "prefix_launcher", "suffix_launcher"),
    ("Tmux", "prefix_tmux", "suffix_tmux"),
    ("Clipboard History", "prefix_cliphist", "suffix_cliphist"),
    ("Toolbox", "prefix_toolbox", "suffix_toolbox"),
    ("Overview", "prefix_overview", "suffix_overview"),
    ("Wallpapers", "prefix_wallpapers", "suffix_wallpapers"),
    ("Random Wallpaper", "prefix_randwall", "suffix_randwall"),
    ("Audio Mixer", "prefix_mixer", "suffix_mixer"),
    ("Emoji Picker", "prefix_emoji", "suffix_emoji"),
    ("Power Menu", "prefix_power", "suffix_power"),
    ("Toggle Caffeine", "prefix_caffeine", "suffix_caffeine"),
    ("Toggle Bar", "prefix_toggle", "suffix_toggle"),
    ("Reload CSS", "prefix_css", "suffix_css"),
    ("Restart with inspector", "prefix_restart_inspector", "suffix_restart_inspector"),
]


class SettingsSection(QGroupBox):
    """Styled section group box."""
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class AwShellSettings(FramelessMainWindow):
    """Main Aw-Shell Settings Window."""

    def __init__(self, parent=None):
        self.bridge = get_bridge()

        # Check for hyprlock/hypridle source files
        self.show_lock_checkbox = os.path.exists(
            os.path.expanduser(f"~/.config/{APP_NAME}/config/hypr/hyprlock.conf")
        )
        self.show_idle_checkbox = os.path.exists(
            os.path.expanduser(f"~/.config/{APP_NAME}/config/hypr/hypridle.conf")
        )

        # Widget references
        self.keybind_entries: List[Tuple[str, str, QLineEdit, QLineEdit]] = []
        self.component_switches: Dict[str, QCheckBox] = {}
        self.metrics_switches: Dict[str, QCheckBox] = {}
        self.metrics_small_switches: Dict[str, QCheckBox] = {}
        self.monitor_checkboxes: Dict[str, QCheckBox] = {}
        self.disk_entries: List[QWidget] = []
        self.selected_face_icon: Optional[str] = None

        super().__init__(width=700, height=720, title=f"{APP_NAME_CAP} Settings")
        self.setMinimumSize(600, 500)

    def _create_scrollable_tab(self, content: QWidget) -> QScrollArea:
        """Wrap tab content in a scroll area."""
        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    def setup_content(self):
        self.content_layout.setContentsMargins(16, 12, 16, 16)
        self.content_layout.setSpacing(12)

        # Tab container with shadow
        tab_container = QFrame()
        tab_container.setObjectName("tableContainer")
        tab_container.setStyleSheet(get_table_container_style())
        tab_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 80))
        tab_container.setGraphicsEffect(shadow)

        container_layout = QVBoxLayout(tab_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Build tabs matching original structure
        self.tabs.addTab(self._create_scrollable_tab(self._build_keybindings_tab()), "Key Bindings")
        self.tabs.addTab(self._create_scrollable_tab(self._build_appearance_tab()), "Appearance")
        self.tabs.addTab(self._create_scrollable_tab(self._build_system_tab()), "System")
        self.tabs.addTab(self._build_about_tab(), "About")

        container_layout.addWidget(self.tabs)
        self.content_layout.addWidget(tab_container, 1)

        # Button row
        row = QHBoxLayout()
        row.addStretch()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._on_reset)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)

        self.apply_btn = QPushButton("Apply && Reload")
        self.apply_btn.clicked.connect(self._on_apply)

        for btn in [self.reset_btn, self.close_btn, self.apply_btn]:
            btn.setMinimumHeight(36)
            btn.setMinimumWidth(110)

        row.addWidget(self.reset_btn)
        row.addWidget(self.close_btn)
        row.addWidget(self.apply_btn)

        self.content_layout.addLayout(row)

    def get_extra_stylesheet(self) -> str:
        """Return dialog-specific styles."""
        t = get_current_theme()
        return get_dialog_stylesheet() + f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            SettingsSection {{
                font-weight: 600;
                padding-top: 4px;
                margin-top: 4px;
            }}
            SettingsSection::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 6px;
                color: {t.text_primary};
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {t.surface_variant};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {t.accent};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{
                background: {t.accent};
                border-radius: 2px;
            }}
            QLineEdit {{
                padding: 4px 8px;
                min-height: 24px;
            }}
            QCheckBox {{
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QLabel {{
                padding: 0px;
            }}
        """

    # =========================================================================
    # KEY BINDINGS TAB
    # =========================================================================

    def _build_keybindings_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(15, 15, 15, 15)

        # Grid for keybindings
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        # Headers
        headers = ["Action", "Modifier", "+", "Key"]
        for col, text in enumerate(headers):
            lbl = QLabel(f"<b>{text}</b>")
            lbl.setTextFormat(Qt.TextFormat.RichText)
            grid.addWidget(lbl, 0, col)

        # Keybinding rows
        for row, (label_text, prefix_key, suffix_key) in enumerate(KEYBIND_DEFINITIONS, start=1):
            # Action label
            action_lbl = QLabel(label_text)
            grid.addWidget(action_lbl, row, 0)

            # Modifier entry
            prefix_entry = QLineEdit()
            prefix_entry.setText(str(self.bridge.get(prefix_key, "")))
            prefix_entry.setPlaceholderText("SUPER ...")
            prefix_entry.setMaximumWidth(180)
            grid.addWidget(prefix_entry, row, 1)

            # Plus sign
            plus_lbl = QLabel("+")
            plus_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(plus_lbl, row, 2)

            # Key entry
            suffix_entry = QLineEdit()
            suffix_entry.setText(str(self.bridge.get(suffix_key, "")))
            suffix_entry.setPlaceholderText("Key")
            suffix_entry.setMaximumWidth(100)
            grid.addWidget(suffix_entry, row, 3)

            self.keybind_entries.append((prefix_key, suffix_key, prefix_entry, suffix_entry))

        layout.addLayout(grid)
        layout.addStretch()
        return w

    # =========================================================================
    # APPEARANCE TAB
    # =========================================================================

    def _build_appearance_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(15, 15, 15, 15)

        # Wallpapers Section
        self._build_wallpapers_section(layout)
        self._add_separator(layout)

        # Date & Time Section
        self._build_datetime_section(layout)

        # Layout Options Section
        self._build_layout_section(layout)
        self._add_separator(layout)

        # Components/Modules Section
        self._build_components_section(layout)

        layout.addStretch()
        return w

    def _add_separator(self, layout: QVBoxLayout) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.1); max-height: 1px;")
        layout.addWidget(sep)

    def _build_wallpapers_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>Wallpapers</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)

        # Wallpaper directory
        grid.addWidget(QLabel("Directory:"), 0, 0)

        dir_row = QHBoxLayout()
        self.wall_dir_entry = QLineEdit()
        self.wall_dir_entry.setText(str(self.bridge.get("wallpapers_dir", "")))
        self.wall_dir_entry.setMinimumWidth(250)
        dir_row.addWidget(self.wall_dir_entry)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse_wallpapers)
        dir_row.addWidget(browse_btn)

        grid.addLayout(dir_row, 0, 1)

        # Profile icon
        grid.addWidget(QLabel("Profile Icon:"), 1, 0)

        icon_row = QHBoxLayout()
        self.face_image = QLabel()
        self.face_image.setFixedSize(64, 64)
        self.face_image.setStyleSheet("border: 1px solid rgba(255,255,255,0.2); border-radius: 4px;")
        self._load_face_icon()
        icon_row.addWidget(self.face_image)

        icon_btn = QPushButton("Change...")
        icon_btn.clicked.connect(self._on_select_face_icon)
        icon_row.addWidget(icon_btn)

        self.face_status_label = QLabel("")
        icon_row.addWidget(self.face_status_label)
        icon_row.addStretch()

        grid.addLayout(icon_row, 1, 1)

        layout.addLayout(grid)

    def _load_face_icon(self) -> None:
        face_path = os.path.expanduser("~/.face.icon")
        if os.path.exists(face_path):
            pixmap = QPixmap(face_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.face_image.setPixmap(pixmap)
        else:
            self.face_image.setText("No Icon")
            self.face_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _on_browse_wallpapers(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Wallpapers Directory", self.wall_dir_entry.text())
        if path:
            self.wall_dir_entry.setText(path)

    def _on_select_face_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Face Icon", "",
            "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self.selected_face_icon = path
            self.face_status_label.setText(f"Selected: {os.path.basename(path)}")
            pixmap = QPixmap(path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.face_image.setPixmap(pixmap)

    def _build_datetime_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>Date & Time Format</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        row = QHBoxLayout()
        row.addWidget(QLabel("Use 12-Hour Clock"))
        self.datetime_12h_cb = QCheckBox()
        self.datetime_12h_cb.setChecked(self.bridge.get("datetime_12h_format", False))
        row.addWidget(self.datetime_12h_cb)
        row.addStretch()
        layout.addLayout(row)

    def _build_layout_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>Layout Options</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)

        row = 0

        # Bar Position
        grid.addWidget(QLabel("Bar Position"), row, 0)
        self.position_combo = ThemedComboBox()
        self.position_combo.addItems(POSITIONS)
        self.position_combo.setCurrentText(str(self.bridge.get("bar_position", "Top")))
        self.position_combo.currentTextChanged.connect(self._on_position_changed)
        grid.addWidget(self.position_combo, row, 1)

        grid.addWidget(QLabel("Centered Bar (Left/Right)"), row, 2)
        self.centered_cb = QCheckBox()
        self.centered_cb.setChecked(self.bridge.get("centered_bar", False))
        self.centered_cb.setEnabled(self.bridge.get("bar_position") in ["Left", "Right"])
        grid.addWidget(self.centered_cb, row, 3)

        row += 1

        # Dock settings
        grid.addWidget(QLabel("Show Dock"), row, 0)
        self.dock_cb = QCheckBox()
        self.dock_cb.setChecked(self.bridge.get("dock_enabled", True))
        self.dock_cb.stateChanged.connect(self._on_dock_changed)
        grid.addWidget(self.dock_cb, row, 1)

        grid.addWidget(QLabel("Always Show Dock"), row, 2)
        self.dock_always_cb = QCheckBox()
        self.dock_always_cb.setChecked(self.bridge.get("dock_always_show", False))
        self.dock_always_cb.setEnabled(self.dock_cb.isChecked())
        grid.addWidget(self.dock_always_cb, row, 3)

        row += 1

        # Dock icon size
        grid.addWidget(QLabel("Dock Icon Size"), row, 0)
        self.dock_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.dock_size_slider.setRange(16, 48)
        self.dock_size_slider.setValue(int(self.bridge.get("dock_icon_size", 28)))
        self.dock_size_label = QLabel(str(self.dock_size_slider.value()))
        self.dock_size_slider.valueChanged.connect(lambda v: self.dock_size_label.setText(str(v)))

        size_row = QHBoxLayout()
        size_row.addWidget(self.dock_size_slider)
        size_row.addWidget(self.dock_size_label)
        grid.addLayout(size_row, row, 1, 1, 3)

        row += 1

        # Workspace options
        grid.addWidget(QLabel("Show Workspace Numbers"), row, 0)
        self.ws_num_cb = QCheckBox()
        self.ws_num_cb.setChecked(self.bridge.get("bar_workspace_show_number", False))
        self.ws_num_cb.stateChanged.connect(self._on_ws_num_changed)
        grid.addWidget(self.ws_num_cb, row, 1)

        grid.addWidget(QLabel("Use Chinese Numerals"), row, 2)
        self.ws_chinese_cb = QCheckBox()
        self.ws_chinese_cb.setChecked(self.bridge.get("bar_workspace_use_chinese_numerals", False))
        self.ws_chinese_cb.setEnabled(self.ws_num_cb.isChecked())
        grid.addWidget(self.ws_chinese_cb, row, 3)

        row += 1

        grid.addWidget(QLabel("Hide Special Workspace"), row, 0)
        self.special_ws_cb = QCheckBox()
        self.special_ws_cb.setChecked(self.bridge.get("bar_hide_special_workspace", True))
        grid.addWidget(self.special_ws_cb, row, 1)

        row += 1

        # Theme options
        grid.addWidget(QLabel("Bar Theme"), row, 0)
        self.bar_theme_combo = ThemedComboBox()
        self.bar_theme_combo.addItems(THEMES)
        self.bar_theme_combo.setCurrentText(str(self.bridge.get("bar_theme", "Pills")))
        grid.addWidget(self.bar_theme_combo, row, 1)

        row += 1

        grid.addWidget(QLabel("Dock Theme"), row, 0)
        self.dock_theme_combo = ThemedComboBox()
        self.dock_theme_combo.addItems(THEMES)
        self.dock_theme_combo.setCurrentText(str(self.bridge.get("dock_theme", "Pills")))
        grid.addWidget(self.dock_theme_combo, row, 1)

        row += 1

        grid.addWidget(QLabel("Panel Theme"), row, 0)
        self.panel_theme_combo = ThemedComboBox()
        self.panel_theme_combo.addItems(PANEL_THEMES)
        self.panel_theme_combo.setCurrentText(str(self.bridge.get("panel_theme", "Notch")))
        self.panel_theme_combo.currentTextChanged.connect(self._on_panel_theme_changed)
        grid.addWidget(self.panel_theme_combo, row, 1)

        grid.addWidget(QLabel("Panel Position"), row, 2)
        self.panel_position_combo = ThemedComboBox()
        self.panel_position_combo.addItems(PANEL_POSITIONS)
        self.panel_position_combo.setCurrentText(str(self.bridge.get("panel_position", "Center")))
        self.panel_position_combo.setEnabled(self.panel_theme_combo.currentText() == "Panel")
        grid.addWidget(self.panel_position_combo, row, 3)

        row += 1

        # Notification position
        grid.addWidget(QLabel("Notification Position"), row, 0)
        self.notif_pos_combo = ThemedComboBox()
        self.notif_pos_combo.addItems(NOTIFICATION_POSITIONS)
        self.notif_pos_combo.setCurrentText(str(self.bridge.get("notif_pos", "Top")))
        grid.addWidget(self.notif_pos_combo, row, 1)

        layout.addLayout(grid)

    def _on_position_changed(self, text: str) -> None:
        is_vertical = text in ["Left", "Right"]
        self.centered_cb.setEnabled(is_vertical)
        if not is_vertical:
            self.centered_cb.setChecked(False)

    def _on_dock_changed(self, state: int) -> None:
        is_active = state == Qt.CheckState.Checked.value
        self.dock_always_cb.setEnabled(is_active)
        if not is_active:
            self.dock_always_cb.setChecked(False)

    def _on_ws_num_changed(self, state: int) -> None:
        is_active = state == Qt.CheckState.Checked.value
        self.ws_chinese_cb.setEnabled(is_active)
        if not is_active:
            self.ws_chinese_cb.setChecked(False)

    def _on_panel_theme_changed(self, text: str) -> None:
        self.panel_position_combo.setEnabled(text == "Panel")

    def _build_components_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>Modules</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        # Corners visibility first
        grid.addWidget(QLabel("Rounded Corners"), 0, 0)
        self.corners_cb = QCheckBox()
        self.corners_cb.setChecked(self.bridge.get("corners_visible", True))
        grid.addWidget(self.corners_cb, 0, 1)

        # Component toggles in 2 columns
        items = list(COMPONENT_DISPLAY_NAMES.items())
        rows_per_col = (len(items) + 1) // 2

        for idx, (name, display) in enumerate(items):
            if idx < rows_per_col:
                row = idx + 1
                col = 0
            else:
                row = idx - rows_per_col
                col = 2

            grid.addWidget(QLabel(display), row, col)
            cb = QCheckBox()
            cb.setChecked(self.bridge.get(f"bar_{name}_visible", True))
            grid.addWidget(cb, row, col + 1)
            self.component_switches[name] = cb

        layout.addLayout(grid)

    # =========================================================================
    # SYSTEM TAB
    # =========================================================================

    def _build_system_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(15, 15, 15, 15)

        # General section
        self._build_general_section(layout)

        # Monitor section
        self._build_monitor_section(layout)

        # Terminal section
        self._build_terminal_section(layout)

        # Hyprland integration
        self._build_hypr_section(layout)

        # Notification apps
        self._build_notification_apps_section(layout)

        # Metrics
        self._build_metrics_section(layout)

        # Disk directories
        self._build_disk_section(layout)

        layout.addStretch()
        return w

    def _build_general_section(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel("Auto-append to hyprland.conf"))
        self.auto_append_cb = QCheckBox()
        self.auto_append_cb.setChecked(self.bridge.get("auto_append_hyprland", True))
        self.auto_append_cb.setToolTip("Automatically append Aw-Shell source string to hyprland.conf")
        row.addWidget(self.auto_append_cb)
        row.addStretch()
        layout.addLayout(row)

    def _build_monitor_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>Monitor Selection</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        layout.addWidget(QLabel("Show Aw-Shell on monitors:"))

        monitors = self.bridge.get_available_monitors()
        current_selection = self.bridge.get("selected_monitors", [])

        monitor_box = QVBoxLayout()
        for mon in monitors:
            name = mon.get("name", f'monitor-{mon.get("id", 0)}')
            cb = QCheckBox(name)
            is_selected = len(current_selection) == 0 or name in current_selection
            cb.setChecked(is_selected)
            monitor_box.addWidget(cb)
            self.monitor_checkboxes[name] = cb

        hint = QLabel("<small>Leave all unchecked to show on all monitors</small>")
        hint.setTextFormat(Qt.TextFormat.RichText)
        monitor_box.addWidget(hint)

        layout.addLayout(monitor_box)

    def _build_terminal_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>Terminal Settings</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        row = QHBoxLayout()
        row.addWidget(QLabel("Command:"))
        self.terminal_entry = QLineEdit()
        self.terminal_entry.setText(str(self.bridge.get("terminal_command", "kitty -e")))
        self.terminal_entry.setToolTip("Command used to launch terminal apps (e.g., 'kitty -e')")
        row.addWidget(self.terminal_entry)
        layout.addLayout(row)

        hint = QLabel("<small>Examples: 'kitty -e', 'alacritty -e', 'foot -e'</small>")
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

    def _build_hypr_section(self, layout: QVBoxLayout) -> None:
        if not self.show_lock_checkbox and not self.show_idle_checkbox:
            return

        header = QLabel("<b>Hyprland Integration</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        if self.show_lock_checkbox:
            row = QHBoxLayout()
            row.addWidget(QLabel("Replace Hyprlock config"))
            self.lock_cb = QCheckBox()
            self.lock_cb.setToolTip("Replace Hyprlock configuration with Aw-Shell's custom config")
            row.addWidget(self.lock_cb)
            row.addStretch()
            layout.addLayout(row)

        if self.show_idle_checkbox:
            row = QHBoxLayout()
            row.addWidget(QLabel("Replace Hypridle config"))
            self.idle_cb = QCheckBox()
            self.idle_cb.setToolTip("Replace Hypridle configuration with Aw-Shell's custom config")
            row.addWidget(self.idle_cb)
            row.addStretch()
            layout.addLayout(row)

        hint = QLabel("<small>Existing configs will be backed up</small>")
        hint.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint)

    def _build_notification_apps_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>Notification Settings</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        # Limited apps
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Limited Apps History:"))
        self.limited_apps_entry = QLineEdit()
        limited_list = self.bridge.get("limited_apps_history", [])
        self.limited_apps_entry.setText(", ".join(f'"{app}"' for app in limited_list))
        self.limited_apps_entry.setToolTip('Enter app names separated by commas, e.g: "Spotify", "Discord"')
        row1.addWidget(self.limited_apps_entry)
        layout.addLayout(row1)

        hint1 = QLabel('<small>Apps with limited notification history (format: "App1", "App2")</small>')
        hint1.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint1)

        # Ignored apps
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("History Ignored Apps:"))
        self.ignored_apps_entry = QLineEdit()
        ignored_list = self.bridge.get("history_ignored_apps", [])
        self.ignored_apps_entry.setText(", ".join(f'"{app}"' for app in ignored_list))
        self.ignored_apps_entry.setToolTip('Enter app names separated by commas, e.g: "Hyprshot", "Screenshot"')
        row2.addWidget(self.ignored_apps_entry)
        layout.addLayout(row2)

        hint2 = QLabel('<small>Apps whose notifications are ignored in history (format: "App1", "App2")</small>')
        hint2.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(hint2)

    def _build_metrics_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>System Metrics Options</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(8)

        grid.addWidget(QLabel("Show in Metrics"), 0, 0)
        grid.addWidget(QLabel("Show in Small Metrics"), 0, 2)

        metrics_vis = self.bridge.get("metrics_visible", {})
        metrics_small_vis = self.bridge.get("metrics_small_visible", {})

        for i, (key, label) in enumerate(METRIC_NAMES.items()):
            # Full metrics
            grid.addWidget(QLabel(label), i + 1, 0)
            cb = QCheckBox()
            cb.setChecked(metrics_vis.get(key, True))
            grid.addWidget(cb, i + 1, 1)
            self.metrics_switches[key] = cb

            # Small metrics
            grid.addWidget(QLabel(label), i + 1, 2)
            cb_small = QCheckBox()
            cb_small.setChecked(metrics_small_vis.get(key, True))
            grid.addWidget(cb_small, i + 1, 3)
            self.metrics_small_switches[key] = cb_small

        layout.addLayout(grid)

    def _build_disk_section(self, layout: QVBoxLayout) -> None:
        header = QLabel("<b>Disk directories for Metrics</b>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        self.disk_container = QVBoxLayout()
        layout.addLayout(self.disk_container)

        for path in self.bridge.get("bar_metrics_disks", ["/"]):
            self._add_disk_entry(path)

        add_btn = QPushButton("Add new disk")
        add_btn.clicked.connect(lambda: self._add_disk_entry("/"))
        layout.addWidget(add_btn)

    def _add_disk_entry(self, path: str) -> None:
        row = QHBoxLayout()
        entry = QLineEdit(path)
        row.addWidget(entry)

        remove_btn = QPushButton("X")
        remove_btn.setMaximumWidth(30)

        container = QWidget()
        container.setLayout(row)

        remove_btn.clicked.connect(lambda: self._remove_disk_entry(container))
        row.addWidget(remove_btn)

        self.disk_container.addWidget(container)
        self.disk_entries.append(container)

    def _remove_disk_entry(self, widget: QWidget) -> None:
        if widget in self.disk_entries:
            self.disk_entries.remove(widget)
            widget.deleteLater()

    # =========================================================================
    # ABOUT TAB
    # =========================================================================

    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(18)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel(f"<b>{APP_NAME_CAP}</b>")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setStyleSheet("font-size: 18pt;")
        layout.addWidget(title)

        desc = QLabel("A hackable shell for Hyprland, powered by Fabric.")
        layout.addWidget(desc)

        # GitHub link
        repo_row = QHBoxLayout()
        repo_row.addWidget(QLabel("GitHub:"))
        repo_link = QLabel('<a href="https://github.com/awareness10/Aw-Shell">https://github.com/awareness10/Aw-Shell</a>')
        repo_link.setOpenExternalLinks(True)
        repo_row.addWidget(repo_link)
        repo_row.addStretch()
        layout.addLayout(repo_row)

        # Original link
        orig_row = QHBoxLayout()
        orig_row.addWidget(QLabel("Original:"))
        orig_link = QLabel('<a href="https://github.com/Axenide/Ax-Shell">Axenide/Ax-Shell</a>')
        orig_link.setOpenExternalLinks(True)
        orig_row.addWidget(orig_link)
        orig_row.addStretch()
        layout.addLayout(orig_row)

        # Ko-Fi button
        kofi_btn = QPushButton("Support Original Author on Ko-Fi")
        kofi_btn.clicked.connect(lambda: webbrowser.open("https://ko-fi.com/Axenide"))
        kofi_btn.setMinimumWidth(200)
        layout.addWidget(kofi_btn)

        layout.addStretch()
        return w

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def _collect_settings(self) -> dict:
        """Collect all settings from widgets."""
        settings = {}

        # Keybindings
        for prefix_key, suffix_key, prefix_entry, suffix_entry in self.keybind_entries:
            settings[prefix_key] = prefix_entry.text()
            settings[suffix_key] = suffix_entry.text()

        # Appearance
        settings["wallpapers_dir"] = self.wall_dir_entry.text()
        settings["datetime_12h_format"] = self.datetime_12h_cb.isChecked()
        settings["bar_position"] = self.position_combo.currentText()
        settings["vertical"] = settings["bar_position"] in ["Left", "Right"]
        settings["centered_bar"] = self.centered_cb.isChecked()
        settings["dock_enabled"] = self.dock_cb.isChecked()
        settings["dock_always_show"] = self.dock_always_cb.isChecked()
        settings["dock_icon_size"] = self.dock_size_slider.value()
        settings["bar_workspace_show_number"] = self.ws_num_cb.isChecked()
        settings["bar_workspace_use_chinese_numerals"] = self.ws_chinese_cb.isChecked()
        settings["bar_hide_special_workspace"] = self.special_ws_cb.isChecked()
        settings["bar_theme"] = self.bar_theme_combo.currentText()
        settings["dock_theme"] = self.dock_theme_combo.currentText()
        settings["panel_theme"] = self.panel_theme_combo.currentText()
        settings["panel_position"] = self.panel_position_combo.currentText()
        settings["notif_pos"] = self.notif_pos_combo.currentText()
        settings["corners_visible"] = self.corners_cb.isChecked()

        # Component visibility
        for name, cb in self.component_switches.items():
            settings[f"bar_{name}_visible"] = cb.isChecked()

        # System
        settings["auto_append_hyprland"] = self.auto_append_cb.isChecked()
        settings["terminal_command"] = self.terminal_entry.text()

        # Monitors
        selected_monitors = [name for name, cb in self.monitor_checkboxes.items() if cb.isChecked()]
        settings["selected_monitors"] = selected_monitors if any(cb.isChecked() for cb in self.monitor_checkboxes.values()) else []

        # Metrics
        settings["metrics_visible"] = {k: cb.isChecked() for k, cb in self.metrics_switches.items()}
        settings["metrics_small_visible"] = {k: cb.isChecked() for k, cb in self.metrics_small_switches.items()}

        # Disk paths
        disk_paths = []
        for container in self.disk_entries:
            layout = container.layout()
            if layout and layout.count() > 0:
                entry = layout.itemAt(0).widget() # pyright: ignore[reportOptionalMemberAccess]
                if isinstance(entry, QLineEdit) and entry.text().strip():
                    disk_paths.append(entry.text().strip())
        settings["bar_metrics_disks"] = disk_paths if disk_paths else ["/"]

        # Notification apps
        settings["limited_apps_history"] = self._parse_app_list(self.limited_apps_entry.text())
        settings["history_ignored_apps"] = self._parse_app_list(self.ignored_apps_entry.text())

        return settings

    def _parse_app_list(self, text: str) -> list:
        """Parse comma-separated app list."""
        if not text.strip():
            return []
        apps = []
        for app in text.split(","):
            app = app.strip().strip('"').strip("'")
            if app:
                apps.append(app)
        return apps

    def _on_apply(self) -> None:
        """Apply settings and restart Aw-Shell."""
        settings = self._collect_settings()
        self.bridge.set_all(settings)

        # Handle face icon
        if self.selected_face_icon:
            try:
                from PIL import Image
                img = Image.open(self.selected_face_icon)
                side = min(img.size)
                left = (img.width - side) // 2
                top = (img.height - side) // 2
                cropped = img.crop((left, top, left + side, top + side))
                face_dest = os.path.expanduser("~/.face.icon")
                cropped.save(face_dest, format="PNG")
                self.selected_face_icon = None
                self.face_status_label.setText("")
            except Exception as e:
                print(f"Error processing face icon: {e}")

        # Get lock/idle checkbox states
        replace_lock = hasattr(self, 'lock_cb') and self.lock_cb.isChecked()
        replace_idle = hasattr(self, 'idle_cb') and self.idle_cb.isChecked()

        # Apply and restart
        self.bridge.apply_and_restart(replace_lock, replace_idle)

        QMessageBox.information(self, APP_NAME_CAP, "Settings applied. Aw-Shell is restarting...")

    def _on_reset(self) -> None:
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Reset all settings to defaults?\n\nThis will reset all keybindings and appearance settings to their default values.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.bridge.reset_to_defaults()
            self._reload_widgets_from_bridge()

    def _reload_widgets_from_bridge(self) -> None:
        """Reload all widget values from the bridge."""
        # Keybindings
        for prefix_key, suffix_key, prefix_entry, suffix_entry in self.keybind_entries:
            prefix_entry.setText(str(self.bridge.get(prefix_key, "")))
            suffix_entry.setText(str(self.bridge.get(suffix_key, "")))

        # Appearance
        self.wall_dir_entry.setText(str(self.bridge.get("wallpapers_dir", "")))
        self.datetime_12h_cb.setChecked(self.bridge.get("datetime_12h_format", False))
        self.position_combo.setCurrentText(str(self.bridge.get("bar_position", "Top")))
        self.centered_cb.setChecked(self.bridge.get("centered_bar", False))
        self.dock_cb.setChecked(self.bridge.get("dock_enabled", True))
        self.dock_always_cb.setChecked(self.bridge.get("dock_always_show", False))
        self.dock_size_slider.setValue(int(self.bridge.get("dock_icon_size", 28)))
        self.ws_num_cb.setChecked(self.bridge.get("bar_workspace_show_number", False))
        self.ws_chinese_cb.setChecked(self.bridge.get("bar_workspace_use_chinese_numerals", False))
        self.special_ws_cb.setChecked(self.bridge.get("bar_hide_special_workspace", True))
        self.bar_theme_combo.setCurrentText(str(self.bridge.get("bar_theme", "Pills")))
        self.dock_theme_combo.setCurrentText(str(self.bridge.get("dock_theme", "Pills")))
        self.panel_theme_combo.setCurrentText(str(self.bridge.get("panel_theme", "Notch")))
        self.panel_position_combo.setCurrentText(str(self.bridge.get("panel_position", "Center")))
        self.notif_pos_combo.setCurrentText(str(self.bridge.get("notif_pos", "Top")))
        self.corners_cb.setChecked(self.bridge.get("corners_visible", True))

        # Component switches
        for name, cb in self.component_switches.items():
            cb.setChecked(self.bridge.get(f"bar_{name}_visible", True))

        # System
        self.auto_append_cb.setChecked(self.bridge.get("auto_append_hyprland", True))
        self.terminal_entry.setText(str(self.bridge.get("terminal_command", "kitty -e")))

        # Monitors
        current_selection = self.bridge.get("selected_monitors", [])
        for name, cb in self.monitor_checkboxes.items():
            is_selected = len(current_selection) == 0 or name in current_selection
            cb.setChecked(is_selected)

        # Metrics
        metrics_vis = self.bridge.get("metrics_visible", {})
        for k, cb in self.metrics_switches.items():
            cb.setChecked(metrics_vis.get(k, True))

        metrics_small_vis = self.bridge.get("metrics_small_visible", {})
        for k, cb in self.metrics_small_switches.items():
            cb.setChecked(metrics_small_vis.get(k, True))

        # Disk entries
        for container in self.disk_entries[:]:
            self._remove_disk_entry(container)
        for path in self.bridge.get("bar_metrics_disks", ["/"]):
            self._add_disk_entry(path)

        # Notification apps
        limited_list = self.bridge.get("limited_apps_history", [])
        self.limited_apps_entry.setText(", ".join(f'"{app}"' for app in limited_list))
        ignored_list = self.bridge.get("history_ignored_apps", [])
        self.ignored_apps_entry.setText(", ".join(f'"{app}"' for app in ignored_list))

        # Reset lock/idle checkboxes
        if hasattr(self, 'lock_cb'):
            self.lock_cb.setChecked(False)
        if hasattr(self, 'idle_cb'):
            self.idle_cb.setChecked(False)

        # Face icon
        self._load_face_icon()
        self.face_status_label.setText("")
        self.selected_face_icon = None

        # Update dependent states
        self._on_position_changed(self.position_combo.currentText())
        self._on_dock_changed(Qt.CheckState.Checked.value if self.dock_cb.isChecked() else Qt.CheckState.Unchecked.value)
        self._on_ws_num_changed(Qt.CheckState.Checked.value if self.ws_num_cb.isChecked() else Qt.CheckState.Unchecked.value)
        self._on_panel_theme_changed(self.panel_theme_combo.currentText())


def main():
    app = QApplication(sys.argv)
    win = AwShellSettings()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
