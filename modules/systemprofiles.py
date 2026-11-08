import subprocess
import threading

from fabric.utils.helpers import exec_shell_command_async
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from gi.repository import GLib

import config.data as data
import modules.icons as icons


class Systemprofiles(Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="systemprofiles",
            orientation="h" if not data.VERTICAL else "v",
            spacing=3,
        )

        if data.BAR_THEME == "Dense" or data.BAR_THEME == "Edge":
            self.add_style_class("invert")

        self.bat_save = None
        self.bat_balanced = None
        self.bat_perf = None
        self.current_mode = "balanced"

        # powerprofilesctl is a Python script (~50 ms a run): asked in the
        # background, and hidden until it answers with profiles. Without any
        # (a VM, or no working powerprofilesctl) there's nothing to show, not
        # even the empty background
        self.has_profiles = False
        self.loading = True
        self._wanted_visible = True
        self.set_no_show_all(True)
        super().set_visible(False)
        self._destroyed = False
        self.connect("destroy", lambda *_: setattr(self, "_destroyed", True))
        threading.Thread(target=self._load_profiles, name="powerprofiles", daemon=True).start()

    @staticmethod
    def _powerprofilesctl(*args) -> str:
        try:
            return subprocess.run(
                ["powerprofilesctl", *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    def _load_profiles(self):
        """In a thread: the available profiles, and the current one."""
        available = self._powerprofilesctl("list")
        current = self._powerprofilesctl("get").strip() if available else ""
        GLib.idle_add(self._build_buttons, available, current)

    def _build_buttons(self, available_profiles: str, current: str) -> bool:
        self.loading = False
        if self._destroyed:
            return False
        children = []

        if "power-saver" in available_profiles:
            self.bat_save = Button(
                name="battery-save",
                child=Label(name="battery-save-label", markup=icons.power_saving),
                on_clicked=lambda *_: self.set_power_mode("power-saver"),
                tooltip_text="Power saving mode",
            )
            children.append(self.bat_save)

        if "balanced" in available_profiles:
            self.bat_balanced = Button(
                name="battery-balanced",
                child=Label(name="battery-balanced-label", markup=icons.power_balanced),
                on_clicked=lambda *_: self.set_power_mode("balanced"),
                tooltip_text="Balanced mode",
            )
            children.append(self.bat_balanced)

        if "performance" in available_profiles:
            self.bat_perf = Button(
                name="battery-performance",
                child=Label(
                    name="battery-performance-label", markup=icons.power_performance
                ),
                on_clicked=lambda *_: self.set_power_mode("performance"),
                tooltip_text="Performance mode",
            )
            children.append(self.bat_perf)

        if not children:
            return False

        # Group the mode buttons into a container.
        self.add(
            Box(
                name="power-mode-switcher",
                orientation="h" if not data.VERTICAL else "v",
                spacing=4,
                children=children,
            )
        )
        self.has_profiles = True
        self.current_mode = current if current in ("power-saver", "balanced", "performance") \
            else "balanced"
        self.update_button_styles()
        self.set_no_show_all(False)
        self.set_visible(self._wanted_visible)
        if self._wanted_visible:
            self.show_all()
        return False

    def set_visible(self, visible: bool) -> None:
        """Stays hidden without profiles, even when enabled in the settings
        (the bar sets each component's visibility from them); shown as
        asked once they've loaded."""
        self._wanted_visible = visible
        super().set_visible(visible and getattr(self, "has_profiles", True))

    def set_power_mode(self, mode):
        """
        Switches power mode by running the corresponding auto-cpufreq command.
        mode: one of 'powersave', 'balanced', or 'performance'
        """
        commands = {
            "power-saver": "powerprofilesctl set power-saver",
            "balanced": "powerprofilesctl set balanced",
            "performance": "powerprofilesctl set performance",
        }
        if mode in commands:
            try:
                exec_shell_command_async(commands[mode])
                self.current_mode = mode
                self.update_button_styles()
            except Exception as err:
                # Optionally, handle errors or display a notification.
                print(f"Error setting power mode: {err}")

    def update_button_styles(self):
        """
        Optionally updates button styles to reflect the current mode.
        Adjust the styling method based on your toolkit's capabilities.
        """
        if self.bat_save:
            self.bat_save.remove_style_class("active")
        if self.bat_balanced:
            self.bat_balanced.remove_style_class("active")
        if self.bat_perf:
            self.bat_perf.remove_style_class("active")

        if self.current_mode == "power-saver" and self.bat_save:
            self.bat_save.add_style_class("active")
        elif self.current_mode == "balanced" and self.bat_balanced:
            self.bat_balanced.add_style_class("active")
        elif self.current_mode == "performance" and self.bat_perf:
            self.bat_perf.add_style_class("active")
