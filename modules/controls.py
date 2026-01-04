from abc import abstractmethod
from typing import Optional, Callable

from fabric.audio.service import Audio
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.eventbox import EventBox
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from fabric.widgets.scale import Scale
from gi.repository import Gdk, GLib

import config.data as data
import modules.icons as icons
from services.brightness import Brightness


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


class BaseAudioSlider(Scale, DebouncedValueMixin):
    def __init__(self, style_class: str, **kwargs):
        super().__init__(
            name="control-slider",
            orientation="h",
            h_expand=True,
            h_align="fill",
            has_origin=True,
            increments=(0.01, 0.1),
            **kwargs,
        )
        self.audio = Audio()
        self.add_style_class(style_class)
        self._setup_audio_connection()
        self.connect("change-value", self._on_change_value)
        self._sync_from_audio()

    @abstractmethod
    def _get_stream(self):
        pass

    @abstractmethod
    def _get_stream_notify_signal(self) -> str:
        pass

    def _setup_audio_connection(self) -> None:
        self.audio.connect(self._get_stream_notify_signal(), self._on_stream_changed)
        stream = self._get_stream()
        if stream:
            stream.connect("changed", self._on_stream_value_changed)

    def _on_stream_changed(self, *args) -> None:
        stream = self._get_stream()
        if stream:
            stream.connect("changed", self._on_stream_value_changed)
            self._sync_from_audio()

    def _on_stream_value_changed(self, *_) -> None:
        self._sync_from_audio()

    def _sync_from_audio(self) -> None:
        stream = self._get_stream()
        if not stream:
            return
        self._updating_from_source = True
        self.value = stream.volume / 100
        self._updating_from_source = False
        if stream.muted:
            self.add_style_class("muted")
        else:
            self.remove_style_class("muted")

    def _on_change_value(self, widget, scroll, value) -> bool:
        if self._updating_from_source:
            return False
        stream = self._get_stream()
        if stream:
            self._schedule_update(value * 100, self._apply_volume)
        return False

    def _apply_volume(self) -> bool:
        if self._pending_value is not None:
            stream = self._get_stream()
            if stream:
                stream.volume = self._pending_value
            self._pending_value = None
        self._update_source_id = None
        return False


class VolumeSlider(BaseAudioSlider):
    def __init__(self, **kwargs):
        super().__init__(style_class="vol", **kwargs)

    def _get_stream(self):
        return self.audio.speaker

    def _get_stream_notify_signal(self) -> str:
        return "notify::speaker"


class MicSlider(BaseAudioSlider):
    def __init__(self, **kwargs):
        super().__init__(style_class="mic", **kwargs)

    def _get_stream(self):
        return self.audio.microphone

    def _get_stream_notify_signal(self) -> str:
        return "notify::microphone"


class BrightnessSlider(Scale, DebouncedValueMixin):
    def __init__(self, **kwargs):
        super().__init__(
            name="control-slider",
            orientation="h",
            h_expand=True,
            has_origin=True,
            increments=(5, 10),
            **kwargs,
        )
        self.client = Brightness.get_initial()
        if self.client.screen_brightness == -1:
            self.destroy()
            return

        self.set_range(0, self.client.max_screen)
        self.set_value(self.client.screen_brightness)
        self.add_style_class("brightness")
        self.connect("change-value", self._on_scale_move)
        self.client.connect("screen", self._on_brightness_changed)

    def _on_scale_move(self, widget, scroll, moved_pos) -> bool:
        if self._updating_from_source:
            return False
        self._schedule_update(moved_pos, self._apply_brightness)
        return False

    def _apply_brightness(self) -> bool:
        if self._pending_value is not None:
            if self._pending_value != self.client.screen_brightness:
                self.client.screen_brightness = self._pending_value
            self._pending_value = None
        self._update_source_id = None
        return False

    def _on_brightness_changed(self, client, _) -> None:
        self._updating_from_source = True
        self.set_value(self.client.screen_brightness)
        self._updating_from_source = False
        percentage = int((self.client.screen_brightness / self.client.max_screen) * 100)
        self.set_tooltip_text(f"{percentage}%")

    def destroy(self) -> None:
        self._cleanup_update_source()
        super().destroy()


class BaseSmallControl(Box, DebouncedValueMixin):
    def __init__(self, name: str, progress_name: str, label_markup: str, **kwargs):
        super().__init__(name=name, **kwargs)
        self.progress_bar = CircularProgressBar(
            name=progress_name,
            size=28,
            line_width=2,
            start_angle=150,
            end_angle=390,
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


class BrightnessSmall(BaseSmallControl):
    def __init__(self, **kwargs):
        self.brightness = Brightness.get_initial()
        if self.brightness.screen_brightness == -1:
            super().__init__("button-bar-brightness", "button-brightness", icons.brightness_high, **kwargs)
            self.destroy()
            return

        super().__init__("button-bar-brightness", "button-brightness", icons.brightness_high, **kwargs)
        self.brightness.connect("screen", self._on_brightness_changed)
        self._on_brightness_changed()

    def _on_scroll(self, widget, event) -> None:
        if self.brightness.max_screen == -1:
            return
        step = 5
        current = self.brightness.screen_brightness
        if event.delta_y < 0:
            new_val = min(current + step, self.brightness.max_screen)
        elif event.delta_y > 0:
            new_val = max(current - step, 0)
        else:
            return
        self._schedule_update(new_val, self._apply_brightness)

    def _apply_brightness(self) -> bool:
        if self._pending_value is not None and self._pending_value != self.brightness.screen_brightness:
            self.brightness.screen_brightness = self._pending_value
            self._pending_value = None
        self._update_source_id = None
        return False

    def _on_brightness_changed(self, *args) -> None:
        if self.brightness.max_screen == -1:
            return
        normalized = self.brightness.screen_brightness / self.brightness.max_screen if self.brightness.max_screen > 0 else 0
        self._updating_from_source = True
        self.progress_bar.value = normalized
        self._updating_from_source = False

        pct = int(normalized * 100)
        if pct >= 75:
            self.control_label.set_markup(icons.brightness_high)
        elif pct >= 24:
            self.control_label.set_markup(icons.brightness_medium)
        else:
            self.control_label.set_markup(icons.brightness_low)
        self.set_tooltip_text(f"{pct}%")


class VolumeSmall(BaseSmallControl):
    def __init__(self, **kwargs):
        super().__init__("button-bar-vol", "button-volume", icons.vol_high, **kwargs)
        self.audio = Audio()
        self.control_button.connect("clicked", self._toggle_mute)
        self.audio.connect("notify::speaker", self._on_new_speaker)
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self._on_speaker_changed)
        self._on_speaker_changed()

    def _on_new_speaker(self, *args) -> None:
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self._on_speaker_changed)
            self._on_speaker_changed()

    def _toggle_mute(self, event) -> None:
        if self.audio.speaker:
            self.audio.speaker.muted = not self.audio.speaker.muted
            self._on_speaker_changed()
            style_op = self.progress_bar.add_style_class if self.audio.speaker.muted else self.progress_bar.remove_style_class
            style_op("muted")
            style_op = self.control_label.add_style_class if self.audio.speaker.muted else self.control_label.remove_style_class
            style_op("muted")

    def _on_scroll(self, _, event) -> None:
        if not self.audio.speaker:
            return
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if abs(event.delta_y) > 0:
                self.audio.speaker.volume -= event.delta_y
            if abs(event.delta_x) > 0:
                self.audio.speaker.volume += event.delta_x

    def _on_speaker_changed(self, *_) -> None:
        if not self.audio.speaker:
            return

        is_bt = "bluetooth" in self.audio.speaker.icon_name
        vol_high = icons.bluetooth_connected if is_bt else icons.vol_high
        vol_med = icons.bluetooth if is_bt else icons.vol_medium
        vol_mute = icons.bluetooth_off if is_bt else icons.vol_off
        vol_off = icons.bluetooth_disconnected if is_bt else icons.vol_mute

        self.progress_bar.value = self.audio.speaker.volume / 100

        if self.audio.speaker.muted:
            self.control_button.get_child().set_markup(vol_mute)
            self.progress_bar.add_style_class("muted")
            self.control_label.add_style_class("muted")
            self.set_tooltip_text("Muted")
            return

        self.progress_bar.remove_style_class("muted")
        self.control_label.remove_style_class("muted")
        self.set_tooltip_text(f"{round(self.audio.speaker.volume)}%")

        if self.audio.speaker.volume > 74:
            self.control_button.get_child().set_markup(vol_high)
        elif self.audio.speaker.volume > 0:
            self.control_button.get_child().set_markup(vol_med)
        else:
            self.control_button.get_child().set_markup(vol_off)


class MicSmall(BaseSmallControl):
    def __init__(self, **kwargs):
        super().__init__("button-bar-mic", "button-mic", icons.mic, **kwargs)
        self.audio = Audio()
        self.control_button.connect("clicked", self._toggle_mute)
        self.audio.connect("notify::microphone", self._on_new_microphone)
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self._on_microphone_changed)
        self._on_microphone_changed()

    def _on_new_microphone(self, *args) -> None:
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self._on_microphone_changed)
            self._on_microphone_changed()

    def _toggle_mute(self, event) -> None:
        if self.audio.microphone:
            self.audio.microphone.muted = not self.audio.microphone.muted
            if self.audio.microphone.muted:
                self.control_button.get_child().set_markup(icons.mic_mute)
                self.progress_bar.add_style_class("muted")
                self.control_label.add_style_class("muted")
            else:
                self._on_microphone_changed()
                self.progress_bar.remove_style_class("muted")
                self.control_label.remove_style_class("muted")

    def _on_scroll(self, _, event) -> None:
        if not self.audio.microphone:
            return
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if abs(event.delta_y) > 0:
                self.audio.microphone.volume -= event.delta_y
            if abs(event.delta_x) > 0:
                self.audio.microphone.volume += event.delta_x

    def _on_microphone_changed(self, *_) -> None:
        if not self.audio.microphone:
            return
        if self.audio.microphone.muted:
            self.control_button.get_child().set_markup(icons.mic_mute)
            self.progress_bar.add_style_class("muted")
            self.control_label.add_style_class("muted")
            self.set_tooltip_text("Muted")
            return

        self.progress_bar.remove_style_class("muted")
        self.control_label.remove_style_class("muted")
        self.progress_bar.value = self.audio.microphone.volume / 100
        self.set_tooltip_text(f"{round(self.audio.microphone.volume)}%")
        icon = icons.mic if self.audio.microphone.volume >= 1 else icons.mic_mute
        self.control_button.get_child().set_markup(icon)


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


class BrightnessIcon(BaseIconControl):
    def __init__(self, **kwargs):
        self.brightness = Brightness.get_initial()
        if self.brightness.screen_brightness == -1:
            super().__init__("brightness-icon", "brightness-label-dash", icons.brightness_high, **kwargs)
            self.destroy()
            return

        super().__init__("brightness-icon", "brightness-label-dash", icons.brightness_high, **kwargs)
        self.brightness.connect("screen", self._on_brightness_changed)
        self._on_brightness_changed()

    def _on_scroll(self, _, event) -> None:
        if self.brightness.max_screen == -1:
            return

        step = 5
        current = self.brightness.screen_brightness

        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0:
                new_val = min(current + step, self.brightness.max_screen)
            elif event.delta_y > 0:
                new_val = max(current - step, 0)
            else:
                return
        else:
            if event.direction == Gdk.ScrollDirection.UP:
                new_val = min(current + step, self.brightness.max_screen)
            elif event.direction == Gdk.ScrollDirection.DOWN:
                new_val = max(current - step, 0)
            else:
                return

        self._schedule_update(new_val, self._apply_brightness)

    def _apply_brightness(self) -> bool:
        if self._pending_value is not None and self._pending_value != self.brightness.screen_brightness:
            self.brightness.screen_brightness = self._pending_value
            self._pending_value = None
            return True
        self._update_source_id = None
        return False

    def _on_brightness_changed(self, *args) -> None:
        if self.brightness.max_screen == -1:
            return
        self._updating_from_source = True
        normalized = self.brightness.screen_brightness / self.brightness.max_screen
        pct = int(normalized * 100)
        self.control_label.set_markup("󰃠")
        self.set_tooltip_text(f"{pct}%")
        self._updating_from_source = False


class VolumeIcon(BaseIconControl):
    def __init__(self, **kwargs):
        super().__init__("vol-icon", "vol-label-dash", "", **kwargs)
        self.audio = Audio()
        self._periodic_update_source_id = None
        self.control_button.connect("clicked", self._toggle_mute)
        self.audio.connect("notify::speaker", self._on_new_speaker)
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self._on_speaker_changed)
        self._periodic_update_source_id = GLib.timeout_add_seconds(2, self._update_device_icon)

    def _on_new_speaker(self, *args) -> None:
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self._on_speaker_changed)
            self._on_speaker_changed()

    def _toggle_mute(self, event) -> None:
        if self.audio.speaker:
            self.audio.speaker.muted = not self.audio.speaker.muted
            self._on_speaker_changed()

    def _on_scroll(self, _, event) -> None:
        if not self.audio.speaker:
            return

        step = 5
        current = self.audio.speaker.volume

        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0:
                new_val = min(current + step, 100)
            elif event.delta_y > 0:
                new_val = max(current - step, 0)
            else:
                return
        else:
            if event.direction == Gdk.ScrollDirection.UP:
                new_val = min(current + step, 100)
            elif event.direction == Gdk.ScrollDirection.DOWN:
                new_val = max(current - step, 0)
            else:
                return

        self._schedule_update(new_val, self._apply_volume)

    def _apply_volume(self) -> bool:
        if self._pending_value is not None and self._pending_value != self.audio.speaker.volume:
            self.audio.speaker.volume = self._pending_value
            self._pending_value = None
            return True
        self._update_source_id = None
        return False

    def _on_speaker_changed(self, *_) -> None:
        if not self.audio.speaker:
            self.control_label.set_markup("")
            self.remove_style_class("muted")
            self.control_label.remove_style_class("muted")
            self.control_button.remove_style_class("muted")
            self.set_tooltip_text("No audio device")
            return

        if self.audio.speaker.muted:
            self.control_label.set_markup(icons.headphones)
            self.add_style_class("muted")
            self.control_label.add_style_class("muted")
            self.control_button.add_style_class("muted")
            self.set_tooltip_text("Muted")
        else:
            self.remove_style_class("muted")
            self.control_label.remove_style_class("muted")
            self.control_button.remove_style_class("muted")
            self._update_device_icon()
            self.set_tooltip_text(f"{round(self.audio.speaker.volume)}%")

    def _update_device_icon(self) -> bool:
        if not self.audio.speaker:
            self.control_label.set_markup("")
            return True
        if self.audio.speaker.muted:
            return True
        self.control_label.set_markup(icons.headphones)
        return True

    def destroy(self) -> None:
        self._cleanup_update_source()
        if hasattr(self, "_periodic_update_source_id") and self._periodic_update_source_id:
            GLib.source_remove(self._periodic_update_source_id)
        super().destroy()


class MicIcon(BaseIconControl):
    def __init__(self, **kwargs):
        super().__init__("mic-icon", "mic-label-dash", icons.mic, **kwargs)
        self.audio = Audio()
        self.control_button.connect("clicked", self._toggle_mute)
        self.audio.connect("notify::microphone", self._on_new_microphone)
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self._on_microphone_changed)
        self._on_microphone_changed()

    def _on_new_microphone(self, *args) -> None:
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self._on_microphone_changed)
            self._on_microphone_changed()

    def _toggle_mute(self, event) -> None:
        if self.audio.microphone:
            self.audio.microphone.muted = not self.audio.microphone.muted
            if self.audio.microphone.muted:
                self.control_button.get_child().set_markup("")
                self.control_label.add_style_class("muted")
                self.control_button.add_style_class("muted")
            else:
                self._on_microphone_changed()
                self.control_label.remove_style_class("muted")
                self.control_button.remove_style_class("muted")

    def _on_scroll(self, _, event) -> None:
        if not self.audio.microphone:
            return

        step = 5
        current = self.audio.microphone.volume

        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0:
                new_val = min(current + step, 100)
            elif event.delta_y > 0:
                new_val = max(current - step, 0)
            else:
                return
        else:
            if event.direction == Gdk.ScrollDirection.UP:
                new_val = min(current + step, 100)
            elif event.direction == Gdk.ScrollDirection.DOWN:
                new_val = max(current - step, 0)
            else:
                return

        self._schedule_update(new_val, self._apply_volume)

    def _apply_volume(self) -> bool:
        if self._pending_value is not None and self._pending_value != self.audio.microphone.volume:
            self.audio.microphone.volume = self._pending_value
            self._pending_value = None
            return True
        self._update_source_id = None
        return False

    def _on_microphone_changed(self, *_) -> None:
        if not self.audio.microphone:
            return
        if self.audio.microphone.muted:
            self.control_button.get_child().set_markup("")
            self.add_style_class("muted")
            self.control_label.add_style_class("muted")
            self.set_tooltip_text("Muted")
            return

        self.remove_style_class("muted")
        self.control_label.remove_style_class("muted")
        self.set_tooltip_text(f"{round(self.audio.microphone.volume)}%")
        icon = "" if self.audio.microphone.volume >= 1 else ""
        self.control_button.get_child().set_markup(icon)


class ControlSliders(Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="control-sliders",
            orientation="h",
            spacing=8,
            **kwargs,
        )
        brightness = Brightness.get_initial()

        if brightness.screen_brightness != -1:
            brightness_row = Box(orientation="h", spacing=0, h_expand=True, h_align="fill")
            brightness_row.add(BrightnessIcon())
            brightness_row.add(BrightnessSlider())
            self.add(brightness_row)

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
        brightness = Brightness.get_initial()
        children = []
        if brightness.screen_brightness != -1:
            children.append(BrightnessSmall())
        children.extend([VolumeSmall(), MicSmall()])
        super().__init__(
            name="control-small",
            orientation="h" if not data.VERTICAL else "v",
            spacing=4,
            children=children,
            **kwargs,
        )
        self.show_all()
