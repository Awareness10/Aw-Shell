from typing import Any, Dict, List, Optional, TypeVar, Generic
from dataclasses import dataclass, field

T = TypeVar('T')


@dataclass(slots=True)
class ThemeConfig:
    bar_theme: str = "Pills"
    dock_theme: str = "Pills"
    panel_theme: str = "Notch"


@dataclass(slots=True)
class LayoutConfig:
    bar_position: str = "Top"
    vertical: bool = False
    centered_bar: bool = False
    panel_position: str = "Center"
    notif_pos: str = "Top"


@dataclass(slots=True)
class DockConfig:
    enabled: bool = True
    icon_size: int = 28
    always_show: bool = False


@dataclass(slots=True)
class WorkspaceConfig:
    show_number: bool = False
    use_chinese_numerals: bool = False
    hide_special: bool = True


@dataclass(slots=True)
class MetricsConfig:
    visible: Dict[str, bool] = field(default_factory=lambda: {
        "cpu": True, "ram": True, "disk": True, "gpu": True
    })
    small_visible: Dict[str, bool] = field(default_factory=lambda: {
        "cpu": True, "ram": True, "disk": True, "gpu": True
    })
    disks: List[str] = field(default_factory=lambda: ["/"])


@dataclass(slots=True)
class BarComponentVisibility:
    button_apps: bool = True
    systray: bool = True
    control: bool = True
    network: bool = True
    button_tools: bool = True
    sysprofiles: bool = True
    button_overview: bool = True
    ws_container: bool = True
    weather: bool = True
    battery: bool = True
    metrics: bool = True
    language: bool = True
    date_time: bool = True
    button_power: bool = True


class ConfigService:
    _instance: Optional['ConfigService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._reload()

    def _reload(self) -> None:
        import config.data as data
        self._data = data

    @property
    def theme(self) -> ThemeConfig:
        return ThemeConfig(
            bar_theme=self._data.BAR_THEME,
            dock_theme=self._data.DOCK_THEME,
            panel_theme=self._data.PANEL_THEME,
        )

    @property
    def layout(self) -> LayoutConfig:
        return LayoutConfig(
            bar_position=self._data.BAR_POSITION,
            vertical=self._data.VERTICAL,
            centered_bar=self._data.CENTERED_BAR,
            panel_position=self._data.PANEL_POSITION,
            notif_pos=self._data.NOTIF_POS,
        )

    @property
    def dock(self) -> DockConfig:
        return DockConfig(
            enabled=self._data.DOCK_ENABLED,
            icon_size=self._data.DOCK_ICON_SIZE,
            always_show=self._data.DOCK_ALWAYS_SHOW,
        )

    @property
    def workspace(self) -> WorkspaceConfig:
        return WorkspaceConfig(
            show_number=self._data.BAR_WORKSPACE_SHOW_NUMBER,
            use_chinese_numerals=self._data.BAR_WORKSPACE_USE_CHINESE_NUMERALS,
            hide_special=self._data.BAR_HIDE_SPECIAL_WORKSPACE,
        )

    @property
    def metrics(self) -> MetricsConfig:
        return MetricsConfig(
            visible=self._data.METRICS_VISIBLE,
            small_visible=self._data.METRICS_SMALL_VISIBLE,
            disks=self._data.BAR_METRICS_DISKS,
        )

    @property
    def bar_visibility(self) -> BarComponentVisibility:
        return BarComponentVisibility(
            button_apps=self._data.BAR_BUTTON_APPS_VISIBLE,
            systray=self._data.BAR_SYSTRAY_VISIBLE,
            control=self._data.BAR_CONTROL_VISIBLE,
            network=self._data.BAR_NETWORK_VISIBLE,
            button_tools=self._data.BAR_BUTTON_TOOLS_VISIBLE,
            sysprofiles=self._data.BAR_SYSPROFILES_VISIBLE,
            button_overview=self._data.BAR_BUTTON_OVERVIEW_VISIBLE,
            ws_container=self._data.BAR_WS_CONTAINER_VISIBLE,
            weather=self._data.BAR_WEATHER_VISIBLE,
            battery=self._data.BAR_BATTERY_VISIBLE,
            metrics=self._data.BAR_METRICS_VISIBLE,
            language=self._data.BAR_LANGUAGE_VISIBLE,
            date_time=self._data.BAR_DATE_TIME_VISIBLE,
            button_power=self._data.BAR_BUTTON_POWER_VISIBLE,
        )

    @property
    def terminal_command(self) -> str:
        return self._data.TERMINAL_COMMAND

    @property
    def wallpapers_dir(self) -> str:
        return self._data.WALLPAPERS_DIR

    @property
    def corners_visible(self) -> bool:
        return self._data.CORNERS_VISIBLE

    @property
    def datetime_12h_format(self) -> bool:
        return self._data.DATETIME_12H_FORMAT

    @property
    def selected_monitors(self) -> List[str]:
        return self._data.SELECTED_MONITORS

    @property
    def limited_apps_history(self) -> List[str]:
        return self._data.LIMITED_APPS_HISTORY

    @property
    def history_ignored_apps(self) -> List[str]:
        return self._data.HISTORY_IGNORED_APPS

    def is_vertical_bar(self) -> bool:
        return self.layout.bar_position in ("Left", "Right")

    def is_panel_vertical(self) -> bool:
        return self.theme.panel_theme == "Panel" and self.is_vertical_bar()


_config_service: Optional[ConfigService] = None


def get_config() -> ConfigService:
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service
