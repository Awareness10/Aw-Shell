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
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFormLayout, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QSlider,  QTabWidget, QVBoxLayout, QWidget
)
from PySide6.QtGui import QColor, QPixmap

from glaze.theme import get_dialog_stylesheet, get_table_container_style, get_current_theme
from glaze.widgets import ThemedComboBox, FramelessMainWindow, DonateButton

from config.settings_utils import (
    get_bind_var, set_all_bind_vars, reset_to_defaults,
    apply_and_restart, get_available_monitors, load_bind_vars,
    APP_NAME, APP_NAME_CAP, HOME_DIR
)

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

KEYBIND_SECTIONS: List[Tuple[str, List[Tuple[str, str, str]]]] = [
    ("Shell Controls", [
        (f"Reload {APP_NAME_CAP}", "prefix_restart", "suffix_restart"),
        ("Reload CSS", "prefix_css", "suffix_css"),
        ("Restart with Inspector", "prefix_restart_inspector", "suffix_restart_inspector"),
        ("Toggle Bar", "prefix_toggle", "suffix_toggle"),
        ("Toggle Caffeine", "prefix_caffeine", "suffix_caffeine"),
    ]),
    ("Panels & Widgets", [
        ("Message", "prefix_axmsg", "suffix_axmsg"),
        ("Dashboard", "prefix_dash", "suffix_dash"),
        ("Bluetooth", "prefix_bluetooth", "suffix_bluetooth"),
        ("Pins", "prefix_pins", "suffix_pins"),
        ("Kanban", "prefix_kanban", "suffix_kanban"),
        ("App Launcher", "prefix_launcher", "suffix_launcher"),
        ("Toolbox", "prefix_toolbox", "suffix_toolbox"),
        ("Overview", "prefix_overview", "suffix_overview"),
        ("Clipboard History", "prefix_cliphist", "suffix_cliphist"),
    ]),
    ("Utilities", [
        ("Tmux", "prefix_tmux", "suffix_tmux"),
        ("Wallpapers", "prefix_wallpapers", "suffix_wallpapers"),
        ("Random Wallpaper", "prefix_randwall", "suffix_randwall"),
        ("Audio Mixer", "prefix_mixer", "suffix_mixer"),
        ("Emoji Picker", "prefix_emoji", "suffix_emoji"),
        ("Power Menu", "prefix_power", "suffix_power"),
    ]),
]


class SettingsSection(QGroupBox):
    """Styled section group box."""
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class AwShellSettings(FramelessMainWindow):
    """Main Aw-Shell Settings Window."""

    def __init__(self, parent=None):
        load_bind_vars()

        # Check for hyprlock/hypridle source files
        self.show_lock_checkbox = (HOME_DIR / ".config" / "hypr" / "hyprlock.conf").exists()
        self.show_idle_checkbox = (HOME_DIR / ".config" / "hypr" / "hypridle.conf").exists()

        # Widget references
        self.keybind_entries: List[Tuple[str, str, QLineEdit, QLineEdit]] = []
        self.component_switches: Dict[str, QCheckBox] = {}
        self.metrics_switches: Dict[str, QCheckBox] = {}
        self.metrics_small_switches: Dict[str, QCheckBox] = {}
        self.monitor_checkboxes: Dict[str, QCheckBox] = {}
        self.disk_entries: List[QWidget] = []
        self.selected_face_icon: Optional[str] = None

        super().__init__(width=560, height=1080, title=f"{APP_NAME_CAP} Settings")
        self.setMinimumSize(400, 380)

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
                padding: 12px 8px 8px 8px;
                margin-top: 4px;
            }}
            SettingsSection > QWidget {{
                margin-left: 4px;
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
        layout.setContentsMargins(16, 16, 16, 16)

        for section_name, bindings in KEYBIND_SECTIONS:
            section = SettingsSection(section_name)
            section_layout = QVBoxLayout(section)
            section_layout.setSpacing(8)

            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(8)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 0)

            for row, (label_text, prefix_key, suffix_key) in enumerate(bindings):
                action_lbl = QLabel(label_text)
                action_lbl.setFixedWidth(140)
                grid.addWidget(action_lbl, row, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

                prefix_entry = QLineEdit()
                prefix_entry.setText(str(get_bind_var(prefix_key, "")))
                prefix_entry.setPlaceholderText("SUPER ...")
                prefix_entry.setMinimumHeight(32)
                prefix_entry.setMaximumWidth(140)
                grid.addWidget(prefix_entry, row, 1)

                plus_lbl = QLabel("+")
                plus_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                plus_lbl.setFixedWidth(12)
                grid.addWidget(plus_lbl, row, 2)

                suffix_entry = QLineEdit()
                suffix_entry.setText(str(get_bind_var(suffix_key, "")))
                suffix_entry.setPlaceholderText("Key")
                suffix_entry.setMinimumHeight(32)
                suffix_entry.setMaximumWidth(80)
                grid.addWidget(suffix_entry, row, 3)

                self.keybind_entries.append((prefix_key, suffix_key, prefix_entry, suffix_entry))

            section_layout.addLayout(grid)
            layout.addWidget(section)

        layout.addStretch()
        return w

    # =========================================================================
    # APPEARANCE TAB
    # =========================================================================

    def _build_appearance_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Wallpapers Section
        self._build_wallpapers_section(layout)

        # Date & Time Section
        self._build_datetime_section(layout)

        # Layout Options Section
        self._build_layout_section(layout)

        # Components/Modules Section
        self._build_components_section(layout)

        layout.addStretch()
        return w

    def _build_wallpapers_section(self, layout: QVBoxLayout) -> None:
        section = SettingsSection("Wallpapers")
        form = QFormLayout(section)
        form.setSpacing(12)
        form.setHorizontalSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Wallpaper directory
        dir_row = QHBoxLayout()
        self.wall_dir_entry = QLineEdit()
        self.wall_dir_entry.setText(str(get_bind_var("wallpapers_dir", "")))
        self.wall_dir_entry.setMinimumHeight(36)
        dir_row.addWidget(self.wall_dir_entry)

        browse_btn = QPushButton("Browse...")
        browse_btn.setObjectName("secondary")
        browse_btn.setFixedWidth(90)
        browse_btn.setMinimumHeight(36)
        browse_btn.clicked.connect(self._on_browse_wallpapers)
        dir_row.addWidget(browse_btn)

        form.addRow("Directory:", dir_row)

        # Profile icon
        icon_row = QHBoxLayout()
        self.face_image = QLabel()
        self.face_image.setFixedSize(64, 64)
        self.face_image.setStyleSheet("border: 1px solid rgba(255,255,255,0.2); border-radius: 4px;")
        self._load_face_icon()
        icon_row.addWidget(self.face_image)
        icon_row.addSpacing(12)

        icon_btn = QPushButton("Change...")
        icon_btn.setObjectName("secondary")
        icon_btn.setContentsMargins(4, 0, 0, 0)
        icon_btn.setMinimumHeight(36)
        icon_btn.clicked.connect(self._on_select_face_icon)
        icon_row.addWidget(icon_btn)

        self.face_status_label = QLabel("")
        icon_row.addWidget(self.face_status_label)
        icon_row.addStretch()

        form.addRow("Profile Icon:", icon_row)

        layout.addWidget(section)

    def _load_face_icon(self) -> None:
        face_path = Path("~/.face.icon").expanduser()
        if face_path.exists():
            pixmap = QPixmap(str(face_path)).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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
        section = SettingsSection("Date && Time")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(8)

        self.datetime_12h_cb = QCheckBox("Use 12-Hour Clock")
        self.datetime_12h_cb.setChecked(get_bind_var("datetime_12h_format", False))
        section_layout.addWidget(self.datetime_12h_cb)

        layout.addWidget(section)

    def _build_layout_section(self, layout: QVBoxLayout) -> None:
        section = SettingsSection("Layout")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(12)

        # Bar Position row
        pos_row = QHBoxLayout()
        pos_row.setSpacing(10)
        pos_label = QLabel("Bar Position:")
        pos_label.setFixedWidth(120)
        pos_row.addWidget(pos_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.position_combo = ThemedComboBox()
        self.position_combo.addItems(POSITIONS)
        self.position_combo.setCurrentText(str(get_bind_var("bar_position", "Top")))
        self.position_combo.setMinimumWidth(120)
        self.position_combo.currentTextChanged.connect(self._on_position_changed)
        pos_row.addWidget(self.position_combo)
        pos_row.addStretch()
        section_layout.addLayout(pos_row)

        # Checkboxes in compact rows
        self.centered_cb = QCheckBox("Centered Bar (Left/Right only)")
        self.centered_cb.setChecked(get_bind_var("centered_bar", False))
        self.centered_cb.setEnabled(get_bind_var("bar_position") in ["Left", "Right"])
        section_layout.addWidget(self.centered_cb)

        # Dock settings
        dock_row = QHBoxLayout()
        dock_row.setSpacing(20)
        self.dock_cb = QCheckBox("Show Dock")
        self.dock_cb.setChecked(get_bind_var("dock_enabled", True))
        self.dock_cb.stateChanged.connect(self._on_dock_changed)
        dock_row.addWidget(self.dock_cb)
        self.dock_always_cb = QCheckBox("Always Show Dock")
        self.dock_always_cb.setChecked(get_bind_var("dock_always_show", False))
        self.dock_always_cb.setEnabled(self.dock_cb.isChecked())
        dock_row.addWidget(self.dock_always_cb)
        dock_row.addStretch()
        section_layout.addLayout(dock_row)

        # Dock icon size
        size_row = QHBoxLayout()
        size_row.setSpacing(12)
        size_label = QLabel("Dock Icon Size:")
        size_label.setFixedWidth(120)
        size_row.addWidget(size_label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.dock_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.dock_size_slider.setRange(16, 48)
        self.dock_size_slider.setValue(int(get_bind_var("dock_icon_size", 28)))
        self.dock_size_slider.setMinimumWidth(200)
        size_row.addWidget(self.dock_size_slider, 1)
        self.dock_size_label = QLabel(str(self.dock_size_slider.value()))
        self.dock_size_label.setMinimumWidth(30)
        self.dock_size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.dock_size_slider.valueChanged.connect(lambda v: self.dock_size_label.setText(str(v)))
        size_row.addWidget(self.dock_size_label)
        section_layout.addLayout(size_row)

        # Workspace options
        ws_row = QHBoxLayout()
        ws_row.setSpacing(20)
        self.ws_num_cb = QCheckBox("Show Workspace Numbers")
        self.ws_num_cb.setChecked(get_bind_var("bar_workspace_show_number", False))
        self.ws_num_cb.stateChanged.connect(self._on_ws_num_changed)
        ws_row.addWidget(self.ws_num_cb)
        self.ws_runes_cb = QCheckBox("Runes in place of numbers ᚠ ᚢ ᚦ ᚯ ᚱ …")
        self.ws_runes_cb.setChecked(get_bind_var("bar_workspace_use_runes", False))
        self.ws_runes_cb.setEnabled(self.ws_num_cb.isChecked())
        ws_row.addWidget(self.ws_runes_cb)
        ws_row.addStretch()
        section_layout.addLayout(ws_row)

        self.special_ws_cb = QCheckBox("Hide Special Workspace")
        self.special_ws_cb.setChecked(get_bind_var("bar_hide_special_workspace", True))
        section_layout.addWidget(self.special_ws_cb)

        # Theme combos using form-style rows
        theme_form = QFormLayout()
        theme_form.setSpacing(12)
        theme_form.setHorizontalSpacing(16)
        theme_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.bar_theme_combo = ThemedComboBox()
        self.bar_theme_combo.addItems(THEMES)
        self.bar_theme_combo.setCurrentText(str(get_bind_var("bar_theme", "Pills")))
        self.bar_theme_combo.setMinimumWidth(150)
        theme_form.addRow("Bar Theme:", self.bar_theme_combo)

        self.dock_theme_combo = ThemedComboBox()
        self.dock_theme_combo.addItems(THEMES)
        self.dock_theme_combo.setCurrentText(str(get_bind_var("dock_theme", "Pills")))
        self.dock_theme_combo.setMinimumWidth(150)
        theme_form.addRow("Dock Theme:", self.dock_theme_combo)

        # Panel theme + position on same row
        panel_row = QHBoxLayout()
        panel_row.setSpacing(10)
        self.panel_theme_combo = ThemedComboBox()
        self.panel_theme_combo.addItems(PANEL_THEMES)
        self.panel_theme_combo.setCurrentText(str(get_bind_var("panel_theme", "Notch")))
        self.panel_theme_combo.setMinimumWidth(150)
        self.panel_theme_combo.currentTextChanged.connect(self._on_panel_theme_changed)
        panel_row.addWidget(self.panel_theme_combo)

        panel_pos_label = QLabel("Position:")
        panel_row.addWidget(panel_pos_label)
        self.panel_position_combo = ThemedComboBox()
        self.panel_position_combo.addItems(PANEL_POSITIONS)
        self.panel_position_combo.setCurrentText(str(get_bind_var("panel_position", "Center")))
        self.panel_position_combo.setEnabled(self.panel_theme_combo.currentText() == "Panel")
        self.panel_position_combo.setMinimumWidth(100)
        panel_row.addWidget(self.panel_position_combo)
        panel_row.addStretch()
        theme_form.addRow("Panel Theme:", panel_row)

        self.notif_pos_combo = ThemedComboBox()
        self.notif_pos_combo.addItems(NOTIFICATION_POSITIONS)
        self.notif_pos_combo.setCurrentText(str(get_bind_var("notif_pos", "Top")))
        self.notif_pos_combo.setMinimumWidth(150)
        theme_form.addRow("Notifications:", self.notif_pos_combo)

        section_layout.addLayout(theme_form)

        layout.addWidget(section)

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
        self.ws_runes_cb.setEnabled(is_active)
        if not is_active:
            self.ws_runes_cb.setChecked(False)

    def _on_panel_theme_changed(self, text: str) -> None:
        self.panel_position_combo.setEnabled(text == "Panel")

    def _build_components_section(self, layout: QVBoxLayout) -> None:
        section = SettingsSection("Modules")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(8)

        self.corners_cb = QCheckBox("Rounded Corners")
        self.corners_cb.setChecked(get_bind_var("corners_visible", True))
        section_layout.addWidget(self.corners_cb)

        # Component toggles in 2-column grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        items = list(COMPONENT_DISPLAY_NAMES.items())
        rows_per_col = (len(items) + 1) // 2

        for idx, (name, display) in enumerate(items):
            if idx < rows_per_col:
                row = idx
                col = 0
            else:
                row = idx - rows_per_col
                col = 1

            cb = QCheckBox(display)
            cb.setChecked(get_bind_var(f"bar_{name}_visible", True))
            grid.addWidget(cb, row, col)
            self.component_switches[name] = cb

        section_layout.addLayout(grid)
        layout.addWidget(section)

    # =========================================================================
    # SYSTEM TAB
    # =========================================================================

    def _build_system_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

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
        section = SettingsSection("General")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(8)

        self.auto_append_cb = QCheckBox("Auto-append to hyprland.conf")
        self.auto_append_cb.setChecked(get_bind_var("auto_append_hyprland", True))
        self.auto_append_cb.setToolTip("Automatically append Aw-Shell source string to hyprland.conf")
        section_layout.addWidget(self.auto_append_cb)

        layout.addWidget(section)

    def _build_monitor_section(self, layout: QVBoxLayout) -> None:
        section = SettingsSection("Monitor Selection")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(8)

        monitors = get_available_monitors()
        current_selection = get_bind_var("selected_monitors", [])

        for mon in monitors:
            name = mon.get("name", f'monitor-{mon.get("id", 0)}')
            cb = QCheckBox(name)
            is_selected = len(current_selection) == 0 or name in current_selection
            cb.setChecked(is_selected)
            section_layout.addWidget(cb)
            self.monitor_checkboxes[name] = cb

        hint = QLabel("<small>Leave all unchecked to show on all monitors</small>")
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setObjectName("subtitle")
        section_layout.addWidget(hint)

        layout.addWidget(section)

    def _build_terminal_section(self, layout: QVBoxLayout) -> None:
        section = SettingsSection("Terminal")
        form = QFormLayout(section)
        form.setSpacing(12)
        form.setHorizontalSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.terminal_entry = QLineEdit()
        self.terminal_entry.setText(str(get_bind_var("terminal_command", "kitty -e")))
        self.terminal_entry.setToolTip("Command used to launch terminal apps (e.g., 'kitty -e')")
        self.terminal_entry.setMinimumHeight(32)
        form.addRow("Command:", self.terminal_entry)

        hint = QLabel("<small>Examples: 'kitty -e', 'alacritty -e', 'foot -e'</small>")
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setObjectName("subtitle")
        form.addRow("", hint)

        layout.addWidget(section)

    def _build_hypr_section(self, layout: QVBoxLayout) -> None:
        if not self.show_lock_checkbox and not self.show_idle_checkbox:
            return

        section = SettingsSection("Hyprland Integration")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(8)

        if self.show_lock_checkbox:
            self.lock_cb = QCheckBox("Replace Hyprlock config")
            self.lock_cb.setToolTip("Replace Hyprlock configuration with Aw-Shell's custom config")
            section_layout.addWidget(self.lock_cb)

        if self.show_idle_checkbox:
            self.idle_cb = QCheckBox("Replace Hypridle config")
            self.idle_cb.setToolTip("Replace Hypridle configuration with Aw-Shell's custom config")
            section_layout.addWidget(self.idle_cb)

        hint = QLabel("<small>Existing configs will be backed up</small>")
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setObjectName("subtitle")
        section_layout.addWidget(hint)

        layout.addWidget(section)

    def _build_notification_apps_section(self, layout: QVBoxLayout) -> None:
        section = SettingsSection("Notifications")
        form = QFormLayout(section)
        form.setSpacing(12)
        form.setHorizontalSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.limited_apps_entry = QLineEdit()
        limited_list = get_bind_var("limited_apps_history", [])
        self.limited_apps_entry.setText(", ".join(f'"{app}"' for app in limited_list))
        self.limited_apps_entry.setToolTip('Enter app names separated by commas, e.g: "Spotify", "Discord"')
        self.limited_apps_entry.setMinimumHeight(32)
        form.addRow("Limited Apps:", self.limited_apps_entry)

        self.ignored_apps_entry = QLineEdit()
        ignored_list = get_bind_var("history_ignored_apps", [])
        self.ignored_apps_entry.setText(", ".join(f'"{app}"' for app in ignored_list))
        self.ignored_apps_entry.setToolTip('Enter app names separated by commas, e.g: "Hyprshot", "Screenshot"')
        self.ignored_apps_entry.setMinimumHeight(32)
        form.addRow("Ignored Apps:", self.ignored_apps_entry)

        hint = QLabel('<small>Comma-separated app names, e.g: "Spotify", "Discord"</small>')
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setObjectName("subtitle")
        form.addRow("", hint)

        layout.addWidget(section)

    def _build_metrics_section(self, layout: QVBoxLayout) -> None:
        section = SettingsSection("System Metrics")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        # Column headers
        metrics_header = QLabel("Metrics")
        metrics_header.setStyleSheet("font-weight: 600;")
        grid.addWidget(metrics_header, 0, 0)
        small_header = QLabel("Small Metrics")
        small_header.setStyleSheet("font-weight: 600;")
        grid.addWidget(small_header, 0, 1)

        metrics_vis = get_bind_var("metrics_visible", {})
        metrics_small_vis = get_bind_var("metrics_small_visible", {})

        for i, (key, label) in enumerate(METRIC_NAMES.items()):
            cb = QCheckBox(label)
            cb.setChecked(metrics_vis.get(key, True))
            grid.addWidget(cb, i + 1, 0)
            self.metrics_switches[key] = cb

            cb_small = QCheckBox(label)
            cb_small.setChecked(metrics_small_vis.get(key, True))
            grid.addWidget(cb_small, i + 1, 1)
            self.metrics_small_switches[key] = cb_small

        section_layout.addLayout(grid)
        layout.addWidget(section)

    def _build_disk_section(self, layout: QVBoxLayout) -> None:
        section = SettingsSection("Disk Directories")
        section_layout = QVBoxLayout(section)
        section_layout.setSpacing(8)

        self.disk_container = QVBoxLayout()
        section_layout.addLayout(self.disk_container)

        for path in get_bind_var("bar_metrics_disks", ["/"]):
            self._add_disk_entry(path)

        add_btn = QPushButton("Add Directory")
        add_btn.setObjectName("secondary")
        add_btn.setMaximumWidth(130)
        add_btn.setMinimumHeight(32)
        add_btn.clicked.connect(lambda: self._add_disk_entry("/"))
        section_layout.addWidget(add_btn)

        layout.addWidget(section)

    def _add_disk_entry(self, path: str) -> None:
        row = QHBoxLayout()
        entry = QLineEdit(path)
        entry.setMinimumHeight(32)
        row.addWidget(entry)

        remove_btn = QPushButton("X")
        remove_btn.setObjectName("danger")
        remove_btn.setFixedSize(32, 32)

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
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Aw-Shell section ---
        aw_section = SettingsSection(APP_NAME_CAP)
        aw_layout = QVBoxLayout(aw_section)
        aw_layout.setSpacing(12)

        desc = QLabel("A hackable shell for Hyprland, powered by Fabric.")
        aw_layout.addWidget(desc)

        repo_row = QHBoxLayout()
        repo_row.addWidget(QLabel("GitHub:"))
        repo_link = QLabel('<a href="https://github.com/awareness10/Aw-Shell">Awareness10/Aw-Shell</a>')
        repo_link.setOpenExternalLinks(True)
        repo_row.addWidget(repo_link)
        repo_row.addStretch()
        aw_layout.addLayout(repo_row)

        donate_btn = DonateButton(url="https://ko-fi.com/awareness10", preset="gold")
        donate_btn.setText("Donate to Aw-Shell")
        donate_btn.setMinimumWidth(200)
        aw_layout.addWidget(donate_btn)

        layout.addWidget(aw_section)

        # --- Original Project section ---
        orig_section = SettingsSection("Original Project (Deprecated)")
        orig_layout = QVBoxLayout(orig_section)
        orig_layout.setSpacing(12)

        orig_row = QHBoxLayout()
        orig_row.addWidget(QLabel("Original:"))
        orig_link = QLabel('<a href="https://github.com/Axenide/Ax-Shell">Axenide/Ax-Shell</a>')
        orig_link.setOpenExternalLinks(True)
        orig_row.addWidget(orig_link)
        orig_row.addStretch()
        orig_layout.addLayout(orig_row)

        kofi_btn = DonateButton(url="https://ko-fi.com/Axenide", preset="silver")
        kofi_btn.setText("Support Original Author on Ko-Fi")
        kofi_btn.setMinimumWidth(200)
        orig_layout.addWidget(kofi_btn)

        layout.addWidget(orig_section)

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
        settings["bar_workspace_use_runes"] = self.ws_runes_cb.isChecked()
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
        set_all_bind_vars(settings)

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
        apply_and_restart(replace_lock, replace_idle)

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
            reset_to_defaults()
            self._reload_widgets()

    def _reload_widgets(self) -> None:
        """Reload all widget values from bind_vars."""
        # Keybindings
        for prefix_key, suffix_key, prefix_entry, suffix_entry in self.keybind_entries:
            prefix_entry.setText(str(get_bind_var(prefix_key, "")))
            suffix_entry.setText(str(get_bind_var(suffix_key, "")))

        # Appearance
        self.wall_dir_entry.setText(str(get_bind_var("wallpapers_dir", "")))
        self.datetime_12h_cb.setChecked(get_bind_var("datetime_12h_format", False))
        self.position_combo.setCurrentText(str(get_bind_var("bar_position", "Top")))
        self.centered_cb.setChecked(get_bind_var("centered_bar", False))
        self.dock_cb.setChecked(get_bind_var("dock_enabled", True))
        self.dock_always_cb.setChecked(get_bind_var("dock_always_show", False))
        self.dock_size_slider.setValue(int(get_bind_var("dock_icon_size", 28)))
        self.ws_num_cb.setChecked(get_bind_var("bar_workspace_show_number", False))
        self.ws_runes_cb.setChecked(get_bind_var("bar_workspace_use_runes", False))
        self.special_ws_cb.setChecked(get_bind_var("bar_hide_special_workspace", True))
        self.bar_theme_combo.setCurrentText(str(get_bind_var("bar_theme", "Pills")))
        self.dock_theme_combo.setCurrentText(str(get_bind_var("dock_theme", "Pills")))
        self.panel_theme_combo.setCurrentText(str(get_bind_var("panel_theme", "Notch")))
        self.panel_position_combo.setCurrentText(str(get_bind_var("panel_position", "Center")))
        self.notif_pos_combo.setCurrentText(str(get_bind_var("notif_pos", "Top")))
        self.corners_cb.setChecked(get_bind_var("corners_visible", True))

        # Component switches
        for name, cb in self.component_switches.items():
            cb.setChecked(get_bind_var(f"bar_{name}_visible", True))

        # System
        self.auto_append_cb.setChecked(get_bind_var("auto_append_hyprland", True))
        self.terminal_entry.setText(str(get_bind_var("terminal_command", "kitty -e")))

        # Monitors
        current_selection = get_bind_var("selected_monitors", [])
        for name, cb in self.monitor_checkboxes.items():
            is_selected = len(current_selection) == 0 or name in current_selection
            cb.setChecked(is_selected)

        # Metrics
        metrics_vis = get_bind_var("metrics_visible", {})
        for k, cb in self.metrics_switches.items():
            cb.setChecked(metrics_vis.get(k, True))

        metrics_small_vis = get_bind_var("metrics_small_visible", {})
        for k, cb in self.metrics_small_switches.items():
            cb.setChecked(metrics_small_vis.get(k, True))

        # Disk entries
        for container in self.disk_entries[:]:
            self._remove_disk_entry(container)
        for path in get_bind_var("bar_metrics_disks", ["/"]):
            self._add_disk_entry(path)

        # Notification apps
        limited_list = get_bind_var("limited_apps_history", [])
        self.limited_apps_entry.setText(", ".join(f'"{app}"' for app in limited_list))
        ignored_list = get_bind_var("history_ignored_apps", [])
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
