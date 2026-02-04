"""
PySide6 dashboard view — port of modules/dashboard.py + modules/widgets.py.

The dashboard is the main expanded view of the notch containing:
- Widgets view: buttons, controls, calendar, player, metrics, notifications
- Sub-views: pins, kanban, wallpapers, mixer (via tab switcher)

Responsive layout adapts to horizontal vs vertical bar positions.
"""

from datetime import datetime as dt
import calendar as cal
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QSlider, QStackedWidget,
    QTabWidget, QSizePolicy, QProgressBar,
)


def _icon_font(size: int = 16) -> QFont:
    f = QFont("tabler-icons")
    f.setPixelSize(size)
    return f


def _icon_button(icon: str, tooltip: str = "", size: int = 40) -> QPushButton:
    btn = QPushButton(icon)
    btn.setFont(_icon_font(16))
    btn.setToolTip(tooltip)
    btn.setFixedSize(size, size)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


# ============================================================================
# Quick Action Buttons
# ============================================================================

class QuickButton(QPushButton):
    """Toggle button for quick actions (wifi, bluetooth, night mode, caffeine)."""

    def __init__(self, icon_on: str, icon_off: str, label: str, parent=None):
        super().__init__(parent)
        self._icon_on = icon_on
        self._icon_off = icon_off
        self._label = label
        self._active = False

        self.setObjectName("quick-button")
        self.setCheckable(True)
        self.setFont(_icon_font(20))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(70, 70)

        self._update_display()
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        self._active = checked
        self._update_display()

    def _update_display(self):
        self.setText(self._icon_on if self._active else self._icon_off)
        self.setProperty("active", self._active)
        self.style().unpolish(self)
        self.style().polish(self)


class ButtonsGrid(QWidget):
    """Grid of quick action buttons: Network, Bluetooth, Night Mode, Caffeine."""

    def __init__(self, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("buttons-grid")

        # Icons from modules/icons.py (tabler-icons)
        self.network_btn = QuickButton("\ueae3", "\uf060", "Wi-Fi")      # wifi / wifi-off
        self.bluetooth_btn = QuickButton("\uea37", "\ueaf2", "Bluetooth")  # bluetooth / bluetooth-off
        self.night_btn = QuickButton("\uea7c", "\uf1a8", "Night Mode")   # moon / moon-off
        self.caffeine_btn = QuickButton("\uef0e", "\uefea", "Caffeine")  # coffee / coffee-off

        if vertical:
            layout = QGridLayout(self)
            layout.setSpacing(8)
            layout.addWidget(self.network_btn, 0, 0)
            layout.addWidget(self.bluetooth_btn, 0, 1)
            layout.addWidget(self.night_btn, 1, 0)
            layout.addWidget(self.caffeine_btn, 1, 1)
        else:
            layout = QHBoxLayout(self)
            layout.setSpacing(8)
            layout.addWidget(self.network_btn)
            layout.addWidget(self.bluetooth_btn)
            layout.addWidget(self.night_btn)
            layout.addWidget(self.caffeine_btn)
            layout.addStretch()


# ============================================================================
# Control Sliders
# ============================================================================

class ControlSlider(QWidget):
    """Single control slider with icon (volume, brightness, mic)."""

    value_changed = Signal(int)

    def __init__(self, icon: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.setObjectName("control-slider")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.icon_btn = QPushButton(icon)
        self.icon_btn.setFont(_icon_font(18))
        self.icon_btn.setObjectName("control-icon")
        self.icon_btn.setFixedSize(36, 36)
        self.icon_btn.setToolTip(tooltip)
        layout.addWidget(self.icon_btn)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setObjectName("control-slider-bar")
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(self.value_changed.emit)
        layout.addWidget(self.slider, 1)

        self.label = QLabel("50%")
        self.label.setObjectName("control-label")
        self.label.setFixedWidth(40)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.slider.valueChanged.connect(lambda v: self.label.setText(f"{v}%"))
        layout.addWidget(self.label)


class ControlSliders(QWidget):
    """Container for volume, brightness, and mic sliders."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("control-sliders")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.brightness = ControlSlider("\uea30", "Brightness")  # brightness
        self.volume = ControlSlider("\uea7a", "Volume")          # volume
        self.mic = ControlSlider("\uea86", "Microphone")         # microphone

        layout.addWidget(self.brightness)
        layout.addWidget(self.volume)
        layout.addWidget(self.mic)


# ============================================================================
# Calendar Widget (Placeholder)
# ============================================================================

class CalendarWidget(QWidget):
    """Simple calendar display — month or week view."""

    def __init__(self, week_view: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("calendar-widget")
        self._week_view = week_view
        self._current_date = dt.now()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header: < Month Year >
        header = QHBoxLayout()
        self.prev_btn = _icon_button("\uea60", "Previous")  # chevron-left
        self.prev_btn.setFixedSize(28, 28)
        self.prev_btn.clicked.connect(self._prev_month)
        header.addWidget(self.prev_btn)

        self.month_label = QLabel()
        self.month_label.setObjectName("calendar-month")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.month_label, 1)

        self.next_btn = _icon_button("\uea61", "Next")  # chevron-right
        self.next_btn.setFixedSize(28, 28)
        self.next_btn.clicked.connect(self._next_month)
        header.addWidget(self.next_btn)

        layout.addLayout(header)

        # Weekday headers
        weekdays = QHBoxLayout()
        weekdays.setSpacing(2)
        for day in ["M", "T", "W", "T", "F", "S", "S"]:
            lbl = QLabel(day)
            lbl.setObjectName("calendar-weekday")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(32)
            weekdays.addWidget(lbl)
        layout.addLayout(weekdays)

        # Days grid
        self.days_grid = QGridLayout()
        self.days_grid.setSpacing(2)
        layout.addLayout(self.days_grid)

        self._build_calendar()

    def _build_calendar(self):
        # Clear existing
        while self.days_grid.count():
            item = self.days_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        year = self._current_date.year
        month = self._current_date.month
        today = dt.now()

        self.month_label.setText(f"{cal.month_name[month]} {year}")

        if self._week_view:
            # Show current week only
            start = today - __import__('datetime').timedelta(days=today.weekday())
            for col in range(7):
                day = start + __import__('datetime').timedelta(days=col)
                lbl = QLabel(str(day.day))
                lbl.setObjectName("calendar-day")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setFixedSize(32, 32)
                if day.date() == today.date():
                    lbl.setProperty("today", True)
                self.days_grid.addWidget(lbl, 0, col)
        else:
            # Full month view
            month_cal = cal.monthcalendar(year, month)
            for row, week in enumerate(month_cal):
                for col, day in enumerate(week):
                    if day == 0:
                        lbl = QLabel("")
                    else:
                        lbl = QLabel(str(day))
                        if day == today.day and month == today.month and year == today.year:
                            lbl.setProperty("today", True)
                    lbl.setObjectName("calendar-day")
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    lbl.setFixedSize(32, 32)
                    self.days_grid.addWidget(lbl, row, col)

    def _prev_month(self):
        if self._current_date.month == 1:
            self._current_date = self._current_date.replace(year=self._current_date.year - 1, month=12)
        else:
            self._current_date = self._current_date.replace(month=self._current_date.month - 1)
        self._build_calendar()

    def _next_month(self):
        if self._current_date.month == 12:
            self._current_date = self._current_date.replace(year=self._current_date.year + 1, month=1)
        else:
            self._current_date = self._current_date.replace(month=self._current_date.month + 1)
        self._build_calendar()


# ============================================================================
# Player Widget (Placeholder)
# ============================================================================

class PlayerWidget(QWidget):
    """Media player controls placeholder."""

    def __init__(self, compact: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("player-widget")
        self._compact = compact

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Album art placeholder
        self.cover = QLabel()
        self.cover.setObjectName("player-cover")
        self.cover.setFixedSize(120 if not compact else 80, 120 if not compact else 80)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setText("\uf00d")  # music icon
        self.cover.setFont(_icon_font(40 if not compact else 28))
        layout.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignCenter)

        # Title/Artist
        self.title = QLabel("No Media Playing")
        self.title.setObjectName("player-title")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        self.artist = QLabel("")
        self.artist.setObjectName("player-artist")
        self.artist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.artist)

        # Controls
        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.prev_btn = _icon_button("\ueab5", "Previous", 32)   # player-skip-back
        self.play_btn = _icon_button("\ueaba", "Play/Pause", 36)  # player-play
        self.next_btn = _icon_button("\ueab6", "Next", 32)       # player-skip-forward

        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.next_btn)

        layout.addLayout(controls)


# ============================================================================
# Metrics Widget (Placeholder)
# ============================================================================

class MetricGauge(QWidget):
    """Single circular metric gauge (CPU, RAM, Disk, GPU)."""

    def __init__(self, label: str, icon: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metric-gauge")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Progress ring (using QProgressBar as placeholder)
        self.progress = QProgressBar()
        self.progress.setObjectName("metric-progress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(50, 50)
        layout.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignCenter)

        # Label
        self.label = QLabel(label)
        self.label.setObjectName("metric-label")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

    def set_value(self, value: int):
        self.progress.setValue(value)


class MetricsWidget(QWidget):
    """System metrics display: CPU, RAM, Disk, GPU."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("metrics-widget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.cpu = MetricGauge("CPU", "\uef8e")
        self.ram = MetricGauge("RAM", "\ufa97")
        self.disk = MetricGauge("Disk", "\uea88")
        self.gpu = MetricGauge("GPU", "\uf233")

        layout.addWidget(self.cpu)
        layout.addWidget(self.ram)
        layout.addWidget(self.disk)
        layout.addWidget(self.gpu)

        # Demo values
        self.cpu.set_value(35)
        self.ram.set_value(62)
        self.disk.set_value(45)
        self.gpu.set_value(20)


# ============================================================================
# Applet Stack (Notifications, Bluetooth, Network)
# ============================================================================

class NotificationHistoryPlaceholder(QWidget):
    """Placeholder for notification history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("notification-history")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("\ueaa1")  # bell icon
        icon.setFont(_icon_font(32))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        label = QLabel("No Notifications")
        label.setObjectName("placeholder-text")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)


class AppletStack(QStackedWidget):
    """Stack of applets: notifications, bluetooth, network."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("applet-stack")

        self.notifications = NotificationHistoryPlaceholder()
        self.bluetooth = QLabel("Bluetooth Devices")
        self.bluetooth.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.network = QLabel("Wi-Fi Networks")
        self.network.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.addWidget(self.notifications)  # 0
        self.addWidget(self.bluetooth)      # 1
        self.addWidget(self.network)        # 2

    def show_notifications(self):
        self.setCurrentIndex(0)

    def show_bluetooth(self):
        self.setCurrentIndex(1)

    def show_network(self):
        self.setCurrentIndex(2)


# ============================================================================
# Main Widgets View
# ============================================================================

class DashWidgets(QWidget):
    """Main dashboard widgets view — the default view when dashboard opens."""

    def __init__(self, state, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("dash-widgets")
        self._state = state
        self._vertical = vertical

        # Create widgets
        self.buttons = ButtonsGrid(vertical=vertical)
        self.controls = ControlSliders()
        self.calendar = CalendarWidget(week_view=vertical)
        self.player = PlayerWidget(compact=vertical)
        self.metrics = MetricsWidget()
        self.applet_stack = AppletStack()

        # Build layout based on orientation
        if vertical:
            self._build_vertical_layout()
        else:
            self._build_horizontal_layout()

    def _build_horizontal_layout(self):
        """Standard horizontal layout for top/bottom bar."""
        main = QHBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(12)

        # Left column: Calendar + Applet Stack
        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self.calendar)
        left.addWidget(self.applet_stack, 1)

        # Center column: Buttons + Controls + Metrics
        center = QVBoxLayout()
        center.setSpacing(8)
        center.addWidget(self.buttons)
        center.addWidget(self.controls)
        center.addWidget(self.metrics)
        center.addStretch()

        # Right column: Player
        right = QVBoxLayout()
        right.addWidget(self.player)
        right.addStretch()

        main.addLayout(left, 2)
        main.addLayout(center, 2)
        main.addLayout(right, 1)

    def _build_vertical_layout(self):
        """Vertical layout for left/right bar."""
        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(8)

        # Stack vertically: Applet → Calendar → Player → Buttons → Controls
        main.addWidget(self.applet_stack, 1)
        main.addWidget(self.calendar)
        main.addWidget(self.player)
        main.addWidget(self.buttons)
        main.addWidget(self.controls)


# ============================================================================
# Placeholder Sub-Views
# ============================================================================

class PinsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("Pins View\n(Phase 5)")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)


class KanbanView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("Kanban Board\n(Phase 5)")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)


class WallpapersView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("Wallpaper Selector\n(Phase 5)")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)


class MixerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("Audio Mixer\n(Phase 5)")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)


# ============================================================================
# Dashboard Container
# ============================================================================

class Dashboard(QWidget):
    """Dashboard container with tab switcher for sub-views.

    Contains: Widgets, Pins, Kanban, Wallpapers, Mixer
    """

    def __init__(self, state, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("dashboard")
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget for sub-views
        self.tabs = QTabWidget()
        self.tabs.setObjectName("dashboard-tabs")
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)

        # Create sub-views
        self.widgets = DashWidgets(state, vertical=vertical)
        self.pins = PinsView()
        self.kanban = KanbanView()
        self.wallpapers = WallpapersView()
        self.mixer = MixerView()

        # Add tabs with icons
        self.tabs.addTab(self.widgets, "\uea87")     # dashboard icon
        self.tabs.addTab(self.pins, "\ueadb")        # pin icon
        self.tabs.addTab(self.kanban, "\ueb9c")      # layout-kanban icon
        self.tabs.addTab(self.wallpapers, "\ueb01") # photo icon
        self.tabs.addTab(self.mixer, "\ued38")       # volume icon

        # Style tab bar with icon font
        self.tabs.tabBar().setFont(_icon_font(16))

        layout.addWidget(self.tabs)

    def go_to_section(self, name: str):
        """Navigate to a specific section by name."""
        sections = {"widgets": 0, "pins": 1, "kanban": 2, "wallpapers": 3, "mixer": 4}
        if name in sections:
            self.tabs.setCurrentIndex(sections[name])

    def go_to_next(self):
        """Navigate to next tab."""
        current = self.tabs.currentIndex()
        self.tabs.setCurrentIndex((current + 1) % self.tabs.count())

    def go_to_previous(self):
        """Navigate to previous tab."""
        current = self.tabs.currentIndex()
        self.tabs.setCurrentIndex((current - 1) % self.tabs.count())


def get_dashboard_stylesheet(theme) -> str:
    """Generate dashboard-specific stylesheet."""
    t = theme
    return f"""
        #dashboard {{
            background: transparent;
        }}
        #dashboard-tabs {{
            background: transparent;
        }}
        #dashboard-tabs::pane {{
            border: none;
            background: transparent;
        }}
        #dashboard-tabs::tab-bar {{
            alignment: center;
        }}
        #dashboard-tabs QTabBar::tab {{
            background: {t.surface_variant};
            color: {t.text_secondary};
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            margin: 2px;
        }}
        #dashboard-tabs QTabBar::tab:selected {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #quick-button {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 12px;
        }}
        #quick-button:checked, #quick-button[active="true"] {{
            background: {t.accent};
            color: {t.on_accent};
        }}
        #control-icon {{
            background: {t.surface_variant};
            color: {t.text_primary};
            border: none;
            border-radius: 8px;
        }}
        #control-slider-bar {{
            background: {t.surface_variant};
        }}
        #control-slider-bar::groove:horizontal {{
            background: {t.surface_variant};
            height: 6px;
            border-radius: 3px;
        }}
        #control-slider-bar::handle:horizontal {{
            background: {t.accent};
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }}
        #control-slider-bar::sub-page:horizontal {{
            background: {t.accent};
            border-radius: 3px;
        }}
        #calendar-month {{
            color: {t.text_primary};
            font-weight: bold;
            font-size: 14px;
        }}
        #calendar-weekday {{
            color: {t.text_secondary};
            font-size: 11px;
        }}
        #calendar-day {{
            color: {t.text_primary};
            background: transparent;
            border-radius: 4px;
        }}
        #calendar-day[today="true"] {{
            background: {t.accent};
            color: {t.on_accent};
            font-weight: bold;
        }}
        #player-widget {{
            background: {t.surface_variant};
            border-radius: 12px;
        }}
        #player-cover {{
            background: {t.surface};
            border-radius: 60px;
            color: {t.text_secondary};
        }}
        #player-title {{
            color: {t.text_primary};
            font-weight: bold;
        }}
        #player-artist {{
            color: {t.text_secondary};
        }}
        #metric-progress {{
            background: {t.surface_variant};
            border-radius: 25px;
        }}
        #metric-progress::chunk {{
            background: {t.accent};
            border-radius: 25px;
        }}
        #metric-label {{
            color: {t.text_secondary};
            font-size: 11px;
        }}
        #applet-stack {{
            background: {t.surface_variant};
            border-radius: 12px;
            padding: 8px;
        }}
    """
