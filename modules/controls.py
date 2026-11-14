import json
import shutil
import threading
from abc import abstractmethod
from typing import Callable, Optional

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.eventbox import EventBox
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from fabric.widgets.scale import Scale
from gi.repository import Gdk, Gio, GLib

import config.data as data
import modules.hidpp as hidpp
import modules.icons as icons
from modules.level_sources import BrightnessSource, MicrophoneSource, SpeakerSource
from modules.upower.upower import UPowerManager
from services.brightness import Brightness

SCROLL_STEP = 5


def set_style_class(widget, name: str, on: bool) -> None:
    (widget.add_style_class if on else widget.remove_style_class)(name)


def scroll_direction(event, discrete: bool = True) -> int:
    """1 for up, -1 for down, 0 otherwise. Smooth scrolling goes by the sign
    of delta_y; discrete up/down events count only when discrete is set."""
    if event.direction == Gdk.ScrollDirection.SMOOTH:
        return (event.delta_y < 0) - (event.delta_y > 0)
    if discrete and event.direction == Gdk.ScrollDirection.UP:
        return 1
    if discrete and event.direction == Gdk.ScrollDirection.DOWN:
        return -1
    return 0


class DebouncedValueMixin:
    _pending_value: Optional[float] = None
    _update_source_id: Optional[int] = None
    _debounce_timeout: int = 100
    _updating_from_source: bool = False

    def _schedule_update(self, value: float, callback: Callable[[], bool]) -> None:
        self._pending_value = value
        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)
        self._update_source_id = GLib.timeout_add(self._debounce_timeout, callback)

    def _cleanup_update_source(self) -> None:
        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)
            self._update_source_id = None


class LevelControlMixin(DebouncedValueMixin):
    """Shared by the controls of a level source (self.source, see
    modules/level_sources.py)."""

    def _watch(self, callback) -> None:
        self.source.watch(callback)
        self.connect("destroy", lambda *_: self.source.unwatch())

    def _uses_source(self) -> bool:
        """False, after destroying the widget, when there's nothing to control."""
        if self.source.appears_later or self.source.available:
            return True
        self.destroy()
        return False

    def _apply_pending(self) -> bool:
        pending, self._pending_value = self._pending_value, None
        self._update_source_id = None
        if pending is not None and self.source.available and pending != self.source.value:
            self.source.set_value(pending)
        return False

    def _scroll_step(self, event, discrete: bool = True) -> None:
        direction = scroll_direction(event, discrete)
        if not direction or not self.source.available:
            return
        current = self.source.value
        if direction > 0:
            new_value = min(current + SCROLL_STEP, self.source.maximum)
        else:
            new_value = max(current - SCROLL_STEP, 0)
        self._schedule_update(new_value, self._apply_pending)

    def _toggle_mute(self, *_) -> None:
        if self.source.available:
            self.source.toggle_mute()
            self._update()


class LevelSlider(Scale, LevelControlMixin):
    """A slider for a level source; one slider unit is `unit` source units."""

    def __init__(self, source, style_class: str, increments, unit: float = 1,
                 tooltip_on_change: bool = False, **kwargs):
        super().__init__(
            name="control-slider",
            orientation="h",
            h_expand=True,
            h_align="fill",
            has_origin=True,
            increments=increments,
            **kwargs,
        )
        self.source = source
        self.unit = unit
        self.tooltip_on_change = tooltip_on_change
        if not self._uses_source():
            return
        self.set_range(0, source.maximum / unit)
        self.add_style_class(style_class)
        self.connect("change-value", self._on_change_value)
        self._watch(self._on_source_changed)
        self._show_value()

    def _show_value(self) -> None:
        if not self.source.available:
            return
        self._updating_from_source = True
        self.set_value(self.source.value / self.unit)
        self._updating_from_source = False
        if self.source.has_mute:
            set_style_class(self, "muted", self.source.muted)

    def _on_source_changed(self) -> None:
        self._show_value()
        if self.tooltip_on_change:
            self.set_tooltip_text(self.source.tooltip())

    def _on_change_value(self, widget, scroll, value) -> bool:
        if not self._updating_from_source:
            self._schedule_update(value * self.unit, self._apply_pending)
        return False

    def destroy(self) -> None:
        self._cleanup_update_source()
        super().destroy()


class VolumeSlider(LevelSlider):
    def __init__(self, **kwargs):
        super().__init__(SpeakerSource(), "vol", increments=(0.01, 0.1), unit=100, **kwargs)


class MicSlider(LevelSlider):
    def __init__(self, **kwargs):
        super().__init__(MicrophoneSource(), "mic", increments=(0.01, 0.1), unit=100, **kwargs)


class BrightnessSlider(LevelSlider):
    def __init__(self, **kwargs):
        super().__init__(BrightnessSource(), "brightness", increments=(5, 10),
                         tooltip_on_change=True, **kwargs)


def when_brightness_ready(owner, add) -> None:
    """Calls add() to put brightness controls in owner: now when there's a
    backend, or once a DDC/CI monitor turns up in the background (ddcutil
    takes about a second; see Brightness.detecting)."""
    brightness = Brightness.get_initial()
    if brightness.screen_brightness != -1:
        add()
        return
    if not brightness.detecting:
        return

    def on_ready(*_):
        brightness.disconnect(handler)
        if brightness.screen_brightness != -1:
            add()

    handler = brightness.connect("ready", on_ready)

    def on_destroy(*_):
        if brightness.handler_is_connected(handler):
            brightness.disconnect(handler)

    owner.connect("destroy", on_destroy)


class BaseSmallControl(Box, DebouncedValueMixin):
    # Open dial arc: reads as a knob you can scroll
    START_ANGLE = 150
    END_ANGLE = 390

    def __init__(self, name: str, progress_name: str, label_markup: str, **kwargs):
        super().__init__(name=name, **kwargs)
        self.progress_bar = CircularProgressBar(
            name=progress_name,
            size=28,
            line_width=2,
            start_angle=self.START_ANGLE,
            end_angle=self.END_ANGLE,
        )
        self.control_label = Label(name=f"{name}-label", markup=label_markup)
        self.control_button = Button(child=self.control_label)
        self.event_box = EventBox(
            events=["scroll", "smooth-scroll"],
            child=Overlay(child=self.progress_bar, overlays=self.control_button),
        )
        self.event_box.connect("scroll-event", self._on_scroll)
        self.add(self.event_box)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)

    @abstractmethod
    def _on_scroll(self, widget, event):
        pass

    def destroy(self) -> None:
        self._cleanup_update_source()
        super().destroy()


class LevelSmall(BaseSmallControl, LevelControlMixin):
    """A bar knob for a level source: scroll to adjust, click to mute.
    With follow_delta, smooth scrolling moves the level by the scroll delta
    right away; otherwise each scroll is a debounced step."""

    def __init__(self, source, name: str, progress_name: str, icon: str,
                 follow_delta: bool = False, **kwargs):
        self.source = source
        self.follow_delta = follow_delta
        super().__init__(name, progress_name, icon, **kwargs)
        if not self._uses_source():
            return
        if source.has_mute:
            self.control_button.connect("clicked", self._toggle_mute)
        self._watch(self._update)
        self._update()

    def _on_scroll(self, widget, event) -> None:
        if not self.follow_delta:
            self._scroll_step(event, discrete=False)
        elif self.source.available and event.direction == Gdk.ScrollDirection.SMOOTH:
            if abs(event.delta_y) > 0:
                self.source.set_value(self.source.value - event.delta_y)
            if abs(event.delta_x) > 0:
                self.source.set_value(self.source.value + event.delta_x)

    def _update(self) -> None:
        if not self.source.available:
            return
        muted = self.source.muted
        if self.source.progress_while_muted or not muted:
            self.progress_bar.value = self.source.fraction
        self.control_label.set_markup(self.source.knob_icon())
        if self.source.has_mute:
            for widget in (self.progress_bar, self.control_label):
                set_style_class(widget, "muted", muted)
        self.set_tooltip_text(self.source.tooltip())


class BrightnessSmall(LevelSmall):
    def __init__(self, **kwargs):
        super().__init__(BrightnessSource(), "button-bar-brightness", "button-brightness",
                         icons.brightness_high, **kwargs)


class VolumeSmall(LevelSmall):
    def __init__(self, **kwargs):
        super().__init__(SpeakerSource(), "button-bar-vol", "button-volume", icons.vol_high,
                         follow_delta=True, **kwargs)


class MicSmall(LevelSmall):
    def __init__(self, **kwargs):
        super().__init__(MicrophoneSource(), "button-bar-mic", "button-mic", icons.mic,
                         follow_delta=True, **kwargs)


class DeviceBattery(BaseSmallControl):
    """Battery ring for a peripheral. Subclasses fetch a reading and pass
    (percentage, charging, model) or None to _show_reading."""
    LOW_THRESHOLD = 15
    POLL_INTERVAL_SECONDS = 30
    # Closed ring from the top: reads as a gauge, not a knob
    START_ANGLE = -90
    END_ANGLE = 270

    def __init__(self, name: str, progress_name: str, icon: str, **kwargs):
        super().__init__(name, progress_name, icon, **kwargs)
        self._icon = icon
        self._poll_source_id = None

    def _start_polling(self) -> None:
        self._poll_source_id = GLib.timeout_add_seconds(self.POLL_INTERVAL_SECONDS, self._update)
        # One-shot: _update returns True to keep the timeout alive, which
        # would make a bare idle_add re-run it on every main-loop iteration
        GLib.idle_add(lambda: self._update() and False)

    def _update(self) -> bool:
        raise NotImplementedError

    def _on_scroll(self, widget, event) -> None:
        return None

    def _show_reading(self, reading) -> None:
        if reading is None:
            self.set_visible(False)
            return

        percentage, is_charging, model = reading
        self.set_visible(True)
        self.progress_bar.value = percentage / 100

        is_low = percentage <= self.LOW_THRESHOLD and not is_charging

        if is_charging:
            self.control_label.set_markup(icons.bolt)
        elif is_low:
            self.control_label.set_markup(icons.alert)
        else:
            self.control_label.set_markup(self._icon)

        set_style_class(self.progress_bar, "alert", is_low)
        set_style_class(self.control_label, "alert", is_low)

        self.set_tooltip_text(f"{model}: {round(percentage)}%")

    def destroy(self) -> None:
        if self._poll_source_id:
            GLib.source_remove(self._poll_source_id)
            self._poll_source_id = None
        super().destroy()


class MouseBattery(DeviceBattery):
    """Any mouse UPower knows about (Bluetooth, Logitech, ...), checked every
    poll so one switched on or plugged in after startup still shows up.
    Logitech mice are read over HID++ since the kernel misreports some."""
    DEVICE_TYPE_MOUSE = 5
    STATE_CHARGING = 1

    def __init__(self, **kwargs):
        super().__init__("button-bar-mouse-battery", "button-mouse-battery", icons.mouse, **kwargs)
        self._in_flight = False
        # UPower path -> whether HID++ says it's a mouse; only definite answers
        self._hidpp_kinds: dict[str, bool] = {}
        self.set_no_show_all(True)
        self.set_visible(False)
        try:
            self.upower = UPowerManager()
        except Exception:
            return
        self._start_polling()

    @staticmethod
    def _hidraw_for(info) -> Optional[str]:
        native_path = str(info.get("NativePath", ""))
        if not native_path.startswith("hidpp_battery"):
            return None
        return hidpp.hidraw_for_power_supply(native_path)

    def _present_devices(self) -> list:
        try:
            devices = [(path, self.upower.get_full_device_information(path))
                       for path in self.upower.detect_devices()]
        except Exception:
            return []
        return [(path, info) for path, info in devices if info.get("IsPresent", False)]

    def _update(self) -> bool:
        if not self._in_flight:
            # HID++ queries can wait on a sleeping device, so keep them off the main loop
            self._in_flight = True
            devices = self._present_devices()
            threading.Thread(target=self._read_in_background, args=(devices,), daemon=True).start()
        return True

    def _read_in_background(self, devices) -> None:
        reading = None
        try:
            reading = self._find_reading(devices)
        finally:
            GLib.idle_add(self._finish_update, reading)

    def _is_mouse(self, path: str, info, hidraw: Optional[str]) -> bool:
        if info.get("Type") == self.DEVICE_TYPE_MOUSE:
            return True
        if hidraw is None:
            return False
        # Logitech mice plugged in by cable show up as keyboards in UPower
        if path not in self._hidpp_kinds:
            kind = hidpp.is_pointer(hidraw)
            if kind is None:
                return False
            self._hidpp_kinds[path] = kind
        return self._hidpp_kinds[path]

    def _find_reading(self, devices):
        for path, info in devices:
            hidraw = self._hidraw_for(info)
            if not self._is_mouse(path, info, hidraw):
                continue
            model = (info.get("Model") or "").strip() or "Mouse"
            battery = hidpp.read_battery(hidraw) if hidraw else None
            if battery is not None:
                return (battery.percentage, battery.charging, model)
            return (
                float(info.get("Percentage", 0)),
                int(info.get("State", 0)) == self.STATE_CHARGING,
                model,
            )
        return None

    def _finish_update(self, reading) -> bool:
        self._in_flight = False
        # destroy() clears the poll source; don't touch a destroyed widget
        if self._poll_source_id is not None:
            self._show_reading(reading)
        return False


class HeadsetBatteryMonitor:
    """Single headsetcontrol poller shared by every bar's HeadsetBattery.
    Concurrent queries to the dongle collide and both read back 0%, so
    only one may run at a time."""
    POLL_INTERVAL_SECONDS = 30
    _instance = None

    @classmethod
    def get(cls) -> "HeadsetBatteryMonitor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._listeners = []
        self._reading = None
        self._in_flight = False
        self._poll_source_id = None

    def subscribe(self, callback) -> None:
        self._listeners.append(callback)
        callback(self._reading)
        if self._poll_source_id is None:
            self._poll_source_id = GLib.timeout_add_seconds(self.POLL_INTERVAL_SECONDS, self._poll)
            self._poll()

    def unsubscribe(self, callback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)
        if not self._listeners and self._poll_source_id is not None:
            GLib.source_remove(self._poll_source_id)
            self._poll_source_id = None

    def _poll(self) -> bool:
        # headsetcontrol talks to the dongle over HID and can take a while;
        # run it async so it never stalls the main loop
        if self._in_flight:
            return True
        self._in_flight = True
        try:
            proc = Gio.Subprocess.new(
                ["headsetcontrol", "-b", "-o", "json"],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE,
            )
            proc.communicate_utf8_async(None, None, self._on_output)
        except GLib.Error:
            self._in_flight = False
            self._publish(None)
        return True

    def _on_output(self, proc, result) -> None:
        self._in_flight = False
        try:
            _, stdout, _ = proc.communicate_utf8_finish(result)
            reading = self._parse(stdout)
        except (GLib.Error, ValueError):
            reading = None
        # A 0% reading means the query collided with another headsetcontrol
        # run (e.g. from a terminal); keep the last good value instead
        if reading is not None and reading[0] <= 0 and self._reading is not None:
            return
        self._publish(reading)

    def _publish(self, reading) -> None:
        self._reading = reading
        for callback in list(self._listeners):
            callback(reading)

    @staticmethod
    def _parse(stdout):
        # Headset powered off (dongle still plugged in) reports BATTERY_UNAVAILABLE
        for device in json.loads(stdout or "{}").get("devices", []):
            battery = device.get("battery") or {}
            status = battery.get("status")
            if status not in ("BATTERY_AVAILABLE", "BATTERY_CHARGING"):
                continue
            level = battery.get("level", -1)
            if level < 0:
                continue
            model = device.get("device") or device.get("product") or "Headset"
            return float(level), status == "BATTERY_CHARGING", model
        return None


class HeadsetBattery(DeviceBattery):
    """USB-dongle headsets UPower doesn't see, read via headsetcontrol."""

    def __init__(self, **kwargs):
        super().__init__("button-bar-headset-battery", "button-headset-battery", icons.headset, **kwargs)
        self._monitor = None
        self.set_no_show_all(True)
        self.set_visible(False)
        if shutil.which("headsetcontrol") is None:
            return
        self._monitor = HeadsetBatteryMonitor.get()
        self._monitor.subscribe(self._show_reading)

    def destroy(self) -> None:
        if self._monitor is not None:
            self._monitor.unsubscribe(self._show_reading)
            self._monitor = None
        super().destroy()


class BaseIconControl(Box, DebouncedValueMixin):
    def __init__(self, name: str, label_name: str, label_markup: str, **kwargs):
        super().__init__(name=name, **kwargs)
        self.control_label = Label(
            name=label_name,
            markup=label_markup,
            h_align="center", v_align="center",
            h_expand=True, v_expand=True,
        )
        self.control_button = Button(
            child=self.control_label,
            h_align="center", v_align="center",
            h_expand=True, v_expand=True,
        )
        self.event_box = EventBox(
            events=["scroll", "smooth-scroll"],
            child=self.control_button,
            h_align="center", v_align="center",
            h_expand=True, v_expand=True,
        )
        self.event_box.connect("scroll-event", self._on_scroll)
        self.add(self.event_box)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)

    @abstractmethod
    def _on_scroll(self, widget, event):
        pass

    def destroy(self) -> None:
        self._cleanup_update_source()
        super().destroy()


class LevelIcon(BaseIconControl, LevelControlMixin):
    """The dashboard icon next to a slider: scroll to step, click to mute."""

    def __init__(self, source, name: str, label_name: str, icon: str,
                 sync_now: bool = True, **kwargs):
        self.source = source
        super().__init__(name, label_name, icon, **kwargs)
        if not self._uses_source():
            return
        if source.has_mute:
            self.control_button.connect("clicked", self._toggle_mute)
        self._watch(self._update)
        if sync_now:
            self._update()

    def _on_scroll(self, widget, event) -> None:
        self._scroll_step(event)

    def _update(self) -> None:
        if not self.source.available:
            return
        muted = self.source.muted
        self.control_label.set_markup(self.source.dash_icon())
        if self.source.has_mute:
            for widget in (self, self.control_label, self.control_button):
                set_style_class(widget, "muted", muted)
        self.set_tooltip_text(self.source.tooltip())


class BrightnessIcon(LevelIcon):
    def __init__(self, **kwargs):
        super().__init__(BrightnessSource(), "brightness-icon", "brightness-label-dash",
                         icons.brightness_high, **kwargs)


class VolumeIcon(LevelIcon):
    def __init__(self, **kwargs):
        self._periodic_update_source_id = None
        # Not synced on creation: the periodic refresh puts the device icon in
        super().__init__(SpeakerSource(), "vol-icon", "vol-label-dash", "", sync_now=False,
                         **kwargs)
        self._periodic_update_source_id = GLib.timeout_add_seconds(2, self._update_device_icon)

    def _update(self) -> None:
        if self.source.available:
            super()._update()
            return
        self.control_label.set_markup("")
        for widget in (self, self.control_label, self.control_button):
            widget.remove_style_class("muted")
        self.set_tooltip_text("No audio device")

    def _update_device_icon(self) -> bool:
        if not self.source.available:
            self.control_label.set_markup("")
        elif not self.source.muted:
            self.control_label.set_markup(self.source.dash_icon())
        return True

    def destroy(self) -> None:
        if self._periodic_update_source_id:
            GLib.source_remove(self._periodic_update_source_id)
            self._periodic_update_source_id = None
        super().destroy()


class MicIcon(LevelIcon):
    def __init__(self, **kwargs):
        super().__init__(MicrophoneSource(), "mic-icon", "mic-label-dash", icons.mic, **kwargs)


class ControlSliders(Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="control-sliders",
            orientation="h",
            spacing=8,
            **kwargs,
        )
        def add_brightness_row():
            brightness_row = Box(orientation="h", spacing=0, h_expand=True, h_align="fill")
            brightness_row.add(BrightnessIcon())
            brightness_row.add(BrightnessSlider())
            self.add(brightness_row)
            self.reorder_child(brightness_row, 0)
            brightness_row.show_all()

        when_brightness_ready(self, add_brightness_row)

        volume_row = Box(orientation="h", spacing=0, h_expand=True, h_align="fill")
        volume_row.add(VolumeIcon())
        volume_row.add(VolumeSlider())
        self.add(volume_row)

        mic_row = Box(orientation="h", spacing=0, h_expand=True, h_align="fill")
        mic_row.add(MicIcon())
        mic_row.add(MicSlider())
        self.add(mic_row)

        self.show_all()


class ControlSmall(Box):
    def __init__(self, **kwargs):
        batteries = [MouseBattery(), HeadsetBattery()]
        divider = Box(name="control-small-divider", v_align="center", h_align="center")
        children = [VolumeSmall(), MicSmall(), divider, *batteries]
        super().__init__(
            name="control-small",
            orientation="h" if not data.VERTICAL else "v",
            spacing=4,
            children=children,
            **kwargs,
        )

        def add_brightness():
            small = BrightnessSmall()
            self.add(small)
            self.reorder_child(small, 0)
            small.show_all()

        when_brightness_ready(self, add_brightness)
        self.show_all()

        # The divider separates the knobs from the battery rings, so it only
        # shows while at least one battery is visible
        def sync_divider(*_):
            divider.set_visible(any(b.get_visible() for b in batteries))

        for battery in batteries:
            battery.connect("notify::visible", sync_divider)
        sync_divider()
