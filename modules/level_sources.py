"""What the volume, microphone and brightness controls adjust.

One small adapter per source gives the controls in modules/controls.py the
same interface (value, maximum, mute, change notifications, icons), so each
kind of control is written once for all three."""

from fabric.audio.service import Audio

import modules.icons as icons
from services.brightness import Brightness


class LevelSource:
    has_mute = False
    # Audio streams come and go, so their controls wait for one; brightness
    # controls are only built once there's a backend (when_brightness_ready)
    appears_later = False
    # Whether a knob's ring keeps following the level while muted
    progress_while_muted = True

    def __init__(self):
        self._handlers = []

    def _connect(self, obj, signal, callback) -> None:
        self._handlers.append((obj, obj.connect(signal, callback)))

    def unwatch(self) -> None:
        for obj, handler in self._handlers:
            if obj.handler_is_connected(handler):
                obj.disconnect(handler)
        self._handlers.clear()

    @property
    def muted(self) -> bool:
        return False

    @property
    def fraction(self) -> float:
        return self.value / self.maximum if self.maximum > 0 else 0

    def tooltip(self) -> str:
        return "Muted" if self.muted else f"{round(self.percent)}%"


class AudioSource(LevelSource):
    """The default speaker or microphone; follows it when it changes."""
    has_mute = True
    appears_later = True
    maximum = 100
    kind = ""  # the Audio property: "speaker" or "microphone"

    def __init__(self):
        super().__init__()
        self.audio = Audio()

    @property
    def stream(self):
        return getattr(self.audio, self.kind)

    @property
    def available(self) -> bool:
        return self.stream is not None

    @property
    def value(self) -> float:
        return self.stream.volume

    def set_value(self, value: float) -> None:
        self.stream.volume = value

    @property
    def percent(self) -> float:
        return self.stream.volume  # already a percentage; over 100 when amplified

    @property
    def muted(self) -> bool:
        return self.stream.muted

    def toggle_mute(self) -> None:
        self.stream.muted = not self.stream.muted

    def watch(self, callback) -> None:
        """Calls callback() when the stream changes or another one takes over."""
        def on_new_stream(*_):
            if self.stream:
                self._connect(self.stream, "changed", lambda *_: callback())
                callback()

        self._connect(self.audio, f"notify::{self.kind}", on_new_stream)
        if self.stream:
            self._connect(self.stream, "changed", lambda *_: callback())


class SpeakerSource(AudioSource):
    kind = "speaker"

    def knob_icon(self) -> str:
        is_bt = "bluetooth" in self.stream.icon_name
        if self.muted:
            return icons.bluetooth_off if is_bt else icons.vol_off
        if self.value > 74:
            return icons.bluetooth_connected if is_bt else icons.vol_high
        if self.value > 0:
            return icons.bluetooth if is_bt else icons.vol_medium
        return icons.bluetooth_disconnected if is_bt else icons.vol_mute

    def dash_icon(self) -> str:
        return icons.headphones


class MicrophoneSource(AudioSource):
    kind = "microphone"
    progress_while_muted = False

    def knob_icon(self) -> str:
        return icons.mic_mute if self.muted or self.value < 1 else icons.mic

    dash_icon = knob_icon


class BrightnessSource(LevelSource):
    """Screen brightness in the backend's raw units (0 to max_screen)."""

    def __init__(self):
        super().__init__()
        self.client = Brightness.get_initial()

    @property
    def available(self) -> bool:
        return self.client.screen_brightness != -1

    @property
    def maximum(self) -> int:
        return self.client.max_screen

    @property
    def value(self) -> int:
        return self.client.screen_brightness

    def set_value(self, value: float) -> None:
        self.client.screen_brightness = value

    @property
    def percent(self) -> int:
        return int(self.fraction * 100)

    def watch(self, callback) -> None:
        self._connect(self.client, "screen", lambda *_: callback())

    def knob_icon(self) -> str:
        if self.percent >= 75:
            return icons.brightness_high
        if self.percent >= 24:
            return icons.brightness_medium
        return icons.brightness_low

    def dash_icon(self) -> str:
        return "󰃠"
