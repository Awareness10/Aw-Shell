"""Volume, microphone and brightness controls (sliders, bar knobs, dashboard
icons): scroll steps, mute, icons and style classes per level, and that a
change coming from the service updates the widget without setting it back."""

import time

import pytest
from conftest import pump, pump_until
from gi.repository import Gdk, GObject, Gtk

import modules.controls as controls
import modules.icons as icons
import modules.level_sources as level_sources
from services.brightness import Brightness

DEBOUNCE = 0.1  # DebouncedValueMixin._debounce_timeout, in seconds


class FakeStream(GObject.Object):
    """fabric's AudioStream: setters apply at once and emit "changed"."""
    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, volume=50.0, muted=False, icon_name="audio-card-analog"):
        super().__init__()
        self._volume = volume
        self._muted = muted
        self.icon_name = icon_name
        self.volume_sets = []
        self.mute_sets = []

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self.volume_sets.append(value)
        self._volume = max(0, min(value, 100))  # AudioStream clamps to max_volume
        self.emit("changed")

    @property
    def muted(self):
        return self._muted

    @muted.setter
    def muted(self, value):
        self.mute_sets.append(value)
        self._muted = value
        self.emit("changed")

    def change(self, volume=None, muted=None):
        """A change made elsewhere (wpctl, another widget)."""
        if volume is not None:
            self._volume = volume
        if muted is not None:
            self._muted = muted
        self.emit("changed")


class FakeAudio(GObject.Object):
    speaker = GObject.Property(type=GObject.Object)
    microphone = GObject.Property(type=GObject.Object)


class FakeBrightness(GObject.Object):
    __gsignals__ = {
        "screen": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "ready": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, value=40, max_screen=100):
        super().__init__()
        self._value = value
        self.max_screen = max_screen
        self.detecting = False
        self.sets = []

    @property
    def screen_brightness(self):
        return self._value

    @screen_brightness.setter
    def screen_brightness(self, value):
        # The real service applies it later and emits "screen" then
        self.sets.append(value)

    def change(self, value):
        self._value = value
        self.emit("screen", int(value / self.max_screen * 100))


@pytest.fixture
def audio(sandbox, monkeypatch):
    fake = FakeAudio()
    fake.speaker = FakeStream()
    fake.microphone = FakeStream()
    monkeypatch.setattr(level_sources, "Audio", lambda: fake)
    return fake


@pytest.fixture
def brightness(sandbox, monkeypatch):
    fake = FakeBrightness()
    monkeypatch.setattr(Brightness, "instance", fake)
    return fake


@pytest.fixture
def make():
    widgets = []

    def build(cls):
        widget = cls()
        widgets.append(widget)
        return widget
    yield build
    for widget in widgets:
        widget.destroy()


def scroll(widget, delta_y=0.0, delta_x=0.0, direction=Gdk.ScrollDirection.SMOOTH):
    event = Gdk.Event.new(Gdk.EventType.SCROLL)
    event.scroll.direction = direction
    event.scroll.delta_y = delta_y
    event.scroll.delta_x = delta_x
    widget.event_box.emit("scroll-event", event)


def settle():
    """Let the debounce timer run."""
    deadline = time.monotonic() + DEBOUNCE * 3
    while time.monotonic() < deadline:
        pump()
        time.sleep(0.01)


def has_class(widget, name):
    return widget.get_style_context().has_class(name)


def label(widget):
    return widget.control_label.get_label()


# Sliders ------------------------------------------------------------------

@pytest.mark.parametrize("cls, kind, style", [
    (controls.VolumeSlider, "speaker", "vol"),
    (controls.MicSlider, "microphone", "mic"),
])
def test_audio_slider(audio, make, cls, kind, style):
    stream = audio.get_property(kind)
    stream.change(volume=30)
    slider = make(cls)
    assert slider.get_name() == "control-slider" and has_class(slider, style)
    assert slider.get_value() == pytest.approx(0.3)
    assert not has_class(slider, "muted")
    assert slider.get_tooltip_text() is None

    stream.change(volume=60, muted=True)
    assert slider.get_value() == pytest.approx(0.6)
    assert has_class(slider, "muted")
    stream.change(muted=False)
    assert not has_class(slider, "muted")
    settle()
    assert stream.volume_sets == [] and stream.mute_sets == []

    slider.emit("change-value", Gtk.ScrollType.JUMP, 0.2)
    slider.emit("change-value", Gtk.ScrollType.JUMP, 0.45)
    assert stream.volume_sets == []  # debounced
    assert pump_until(lambda: stream.volume_sets)
    settle()
    assert stream.volume_sets == [pytest.approx(45)]


def test_audio_slider_follows_a_new_stream(audio, make):
    slider = make(controls.VolumeSlider)
    audio.speaker = FakeStream(volume=80, muted=True)
    assert slider.get_value() == pytest.approx(0.8)
    assert has_class(slider, "muted")
    audio.speaker.change(volume=20)
    assert slider.get_value() == pytest.approx(0.2)


def test_audio_slider_without_a_stream(audio, make):
    audio.speaker = None
    slider = make(controls.VolumeSlider)
    slider.emit("change-value", Gtk.ScrollType.JUMP, 0.5)
    settle()
    audio.speaker = FakeStream(volume=70)
    assert slider.get_value() == pytest.approx(0.7)


def test_brightness_slider(brightness, make):
    brightness.max_screen = 400
    brightness.change(100)
    slider = make(controls.BrightnessSlider)
    assert slider.get_name() == "control-slider" and has_class(slider, "brightness")
    adjustment = slider.get_adjustment()
    assert (adjustment.get_lower(), adjustment.get_upper()) == (0, 400)
    assert slider.get_value() == 100
    assert slider.get_tooltip_text() is None  # only set on a change

    brightness.change(300)
    assert slider.get_value() == 300
    assert slider.get_tooltip_text() == "75%"
    settle()
    assert brightness.sets == []

    slider.emit("change-value", Gtk.ScrollType.JUMP, 120)
    slider.emit("change-value", Gtk.ScrollType.JUMP, 200)
    assert pump_until(lambda: brightness.sets)
    settle()
    assert brightness.sets == [200]

    # Moving back to where it is doesn't set it again
    slider.emit("change-value", Gtk.ScrollType.JUMP, 300)
    settle()
    assert brightness.sets == [200]


# Bar knobs ----------------------------------------------------------------

@pytest.mark.parametrize("volume, icon", [
    (0, icons.vol_mute), (1, icons.vol_medium), (50, icons.vol_medium),
    (74, icons.vol_medium), (75, icons.vol_high), (150, icons.vol_high),
])
def test_volume_knob_icon(audio, make, volume, icon):
    audio.speaker.change(volume=volume)
    knob = make(controls.VolumeSmall)
    assert knob.get_name() == "button-bar-vol"
    assert knob.progress_bar.get_name() == "button-volume"
    assert label(knob) == icon
    assert knob.get_tooltip_text() == f"{volume}%"
    assert not has_class(knob.progress_bar, "muted")
    assert not has_class(knob.control_label, "muted")


@pytest.mark.parametrize("volume, muted, icon", [
    (0, False, icons.bluetooth_disconnected), (50, False, icons.bluetooth),
    (80, False, icons.bluetooth_connected), (80, True, icons.bluetooth_off),
])
def test_volume_knob_bluetooth_icons(audio, make, volume, muted, icon):
    audio.speaker = FakeStream(volume=volume, muted=muted, icon_name="audio-headset-bluetooth")
    assert label(make(controls.VolumeSmall)) == icon


def test_volume_knob_mute(audio, make):
    stream = audio.speaker
    stream.change(volume=40)
    knob = make(controls.VolumeSmall)
    knob.control_button.clicked()
    assert stream.mute_sets == [True]
    assert label(knob) == icons.vol_off
    assert knob.get_tooltip_text() == "Muted"
    assert has_class(knob.progress_bar, "muted") and has_class(knob.control_label, "muted")

    stream.change(volume=60)  # the ring still follows the volume while muted
    assert knob.progress_bar.value == pytest.approx(0.6)
    assert label(knob) == icons.vol_off

    knob.control_button.clicked()
    assert stream.mute_sets == [True, False]
    assert label(knob) == icons.vol_medium
    assert knob.get_tooltip_text() == "60%"
    assert not has_class(knob.progress_bar, "muted")
    assert not has_class(knob.control_label, "muted")
    assert stream.volume_sets == []


@pytest.mark.parametrize("cls, kind", [
    (controls.VolumeSmall, "speaker"), (controls.MicSmall, "microphone"),
])
def test_audio_knob_scroll(audio, make, cls, kind):
    stream = audio.get_property(kind)
    knob = make(cls)
    scroll(knob, delta_y=1.5)  # smooth scroll: volume follows the delta, at once
    assert stream.volume_sets == [48.5]
    scroll(knob, delta_x=2.0)
    assert stream.volume_sets == [48.5, 50.5]
    scroll(knob, delta_y=-3.0, delta_x=1.0)
    assert stream.volume_sets == [48.5, 50.5, 53.5, 54.5]
    scroll(knob, delta_y=-80)  # the stream clamps
    assert stream.volume == 100
    scroll(knob, direction=Gdk.ScrollDirection.UP)  # only smooth scrolling counts
    settle()
    assert len(stream.volume_sets) == 5
    assert knob.progress_bar.value == pytest.approx(1.0)


def test_audio_knob_follows_a_new_stream(audio, make):
    knob = make(controls.VolumeSmall)
    audio.speaker = FakeStream(volume=0)
    assert label(knob) == icons.vol_mute
    audio.speaker.change(volume=90)
    assert label(knob) == icons.vol_high
    assert audio.speaker.volume_sets == []


@pytest.mark.parametrize("volume, icon", [
    (0, icons.mic_mute), (0.5, icons.mic_mute), (1, icons.mic), (50, icons.mic),
    (100, icons.mic), (150, icons.mic),
])
def test_mic_knob_icon(audio, make, volume, icon):
    audio.microphone.change(volume=volume)
    knob = make(controls.MicSmall)
    assert knob.get_name() == "button-bar-mic"
    assert knob.progress_bar.get_name() == "button-mic"
    assert label(knob) == icon
    assert knob.get_tooltip_text() == f"{round(volume)}%"
    assert knob.progress_bar.value == pytest.approx(volume / 100)


def test_mic_knob_mute(audio, make):
    stream = audio.microphone
    stream.change(volume=40)
    knob = make(controls.MicSmall)
    knob.control_button.clicked()
    assert stream.mute_sets == [True]
    assert label(knob) == icons.mic_mute
    assert knob.get_tooltip_text() == "Muted"
    assert has_class(knob.progress_bar, "muted") and has_class(knob.control_label, "muted")

    stream.change(volume=70)  # unlike volume, the ring stays put while muted
    assert knob.progress_bar.value == pytest.approx(0.4)

    knob.control_button.clicked()
    assert stream.mute_sets == [True, False]
    assert label(knob) == icons.mic
    assert knob.get_tooltip_text() == "70%"
    assert knob.progress_bar.value == pytest.approx(0.7)
    assert not has_class(knob.progress_bar, "muted")
    assert not has_class(knob.control_label, "muted")

    stream.change(muted=True)  # muted elsewhere
    assert label(knob) == icons.mic_mute
    assert has_class(knob.progress_bar, "muted") and has_class(knob.control_label, "muted")
    assert stream.volume_sets == [] and stream.mute_sets == [True, False]


@pytest.mark.parametrize("value, icon", [
    (0, icons.brightness_low), (23, icons.brightness_low), (24, icons.brightness_medium),
    (74, icons.brightness_medium), (75, icons.brightness_high), (100, icons.brightness_high),
])
def test_brightness_knob_icon(brightness, make, value, icon):
    brightness.change(value)
    knob = make(controls.BrightnessSmall)
    assert knob.get_name() == "button-bar-brightness"
    assert knob.progress_bar.get_name() == "button-brightness"
    assert label(knob) == icon
    assert knob.get_tooltip_text() == f"{value}%"
    assert knob.progress_bar.value == pytest.approx(value / 100)


def test_brightness_knob_raw_values(brightness, make):
    brightness.max_screen = 96000
    brightness.change(48000)
    knob = make(controls.BrightnessSmall)
    assert knob.progress_bar.value == pytest.approx(0.5)
    assert knob.get_tooltip_text() == "50%"
    brightness.change(72000)
    assert label(knob) == icons.brightness_high
    assert knob.get_tooltip_text() == "75%"
    settle()
    assert brightness.sets == []


def test_brightness_knob_scroll(brightness, make):
    knob = make(controls.BrightnessSmall)
    scroll(knob, delta_y=-1)
    scroll(knob, delta_y=-1)
    assert brightness.sets == []  # debounced
    assert pump_until(lambda: brightness.sets)
    settle()
    assert brightness.sets == [45]  # both steps from 40: the service hadn't changed yet

    brightness.change(45)
    scroll(knob, delta_y=0.3)
    settle()
    assert brightness.sets == [45, 40]

    brightness.change(98)
    scroll(knob, delta_y=-1)
    settle()
    brightness.change(3)
    scroll(knob, delta_y=1)
    settle()
    assert brightness.sets == [45, 40, 100, 0]

    scroll(knob, direction=Gdk.ScrollDirection.UP)  # only smooth scrolling counts
    scroll(knob, delta_x=1)
    settle()
    assert brightness.sets == [45, 40, 100, 0]


def test_brightness_knob_has_no_mute(brightness, make):
    knob = make(controls.BrightnessSmall)
    knob.control_button.clicked()
    assert not has_class(knob.progress_bar, "muted")
    assert knob.get_tooltip_text() == "40%"


# Dashboard icons ----------------------------------------------------------

def test_brightness_icon(brightness, make):
    icon = make(controls.BrightnessIcon)
    assert icon.get_name() == "brightness-icon"
    assert icon.control_label.get_name() == "brightness-label-dash"
    assert label(icon) == "󰃠"
    assert icon.get_tooltip_text() == "40%"
    brightness.change(90)
    assert label(icon) == "󰃠"
    assert icon.get_tooltip_text() == "90%"
    settle()
    assert brightness.sets == []


@pytest.mark.parametrize("cls, max_value", [
    (controls.BrightnessIcon, 100), (controls.VolumeIcon, 100), (controls.MicIcon, 100),
])
def test_icon_scroll_steps(audio, brightness, make, cls, max_value):
    widget = make(cls)
    if cls is controls.BrightnessIcon:
        sets, change = brightness.sets, brightness.change
    else:
        stream = audio.speaker if cls is controls.VolumeIcon else audio.microphone
        sets, change = stream.volume_sets, lambda v: stream.change(volume=v)

    change(40)
    scroll(widget, delta_y=-0.2)
    scroll(widget, delta_y=-0.2)
    assert sets == []  # debounced
    assert pump_until(lambda: sets)
    settle()
    assert sets == [45]

    for start, kwargs in [
        (45, {"delta_y": 1}),
        (45, {"direction": Gdk.ScrollDirection.UP}),
        (45, {"direction": Gdk.ScrollDirection.DOWN}),
        (98, {"delta_y": -1}),
        (3, {"direction": Gdk.ScrollDirection.DOWN}),
    ]:
        change(start)
        scroll(widget, **kwargs)
        settle()
    assert sets == [45, 40, 50, 40, max_value, 0]

    change(50)
    scroll(widget, delta_x=1)  # sideways or left/right doesn't count
    scroll(widget, direction=Gdk.ScrollDirection.LEFT)
    settle()
    assert sets == [45, 40, 50, 40, max_value, 0]


def test_volume_icon(audio, make):
    stream = audio.speaker
    icon = make(controls.VolumeIcon)
    assert icon.get_name() == "vol-icon"
    assert icon.control_label.get_name() == "vol-label-dash"
    # Not synced on creation: the device icon shows on the first change or
    # the 2-second refresh
    assert label(icon) == ""
    assert icon.get_tooltip_text() is None
    icon._update_device_icon()
    assert label(icon) == icons.headphones

    stream.change(volume=150)
    assert icon.get_tooltip_text() == "150%"

    icon.control_button.clicked()
    assert stream.mute_sets == [True]
    assert label(icon) == icons.headphones
    assert icon.get_tooltip_text() == "Muted"
    for widget in (icon, icon.control_label, icon.control_button):
        assert has_class(widget, "muted")

    icon.control_button.clicked()
    assert stream.mute_sets == [True, False]
    assert icon.get_tooltip_text() == "150%"
    for widget in (icon, icon.control_label, icon.control_button):
        assert not has_class(widget, "muted")

    stream.change(muted=True)  # muted elsewhere
    for widget in (icon, icon.control_label, icon.control_button):
        assert has_class(widget, "muted")
    assert stream.volume_sets == []


def test_volume_icon_follows_a_new_stream(audio, make):
    icon = make(controls.VolumeIcon)
    audio.speaker = FakeStream(volume=30)
    assert label(icon) == icons.headphones
    assert icon.get_tooltip_text() == "30%"
    audio.speaker = None
    icon._update_device_icon()
    assert label(icon) == ""


@pytest.mark.parametrize("volume, icon_markup", [
    (0, icons.mic_mute), (0.5, icons.mic_mute), (1, icons.mic), (60, icons.mic), (150, icons.mic),
])
def test_mic_icon_levels(audio, make, volume, icon_markup):
    audio.microphone.change(volume=volume)
    icon = make(controls.MicIcon)
    assert icon.get_name() == "mic-icon"
    assert icon.control_label.get_name() == "mic-label-dash"
    assert label(icon) == icon_markup
    assert icon.get_tooltip_text() == f"{round(volume)}%"


def test_mic_icon_mute(audio, make):
    stream = audio.microphone
    icon = make(controls.MicIcon)
    icon.control_button.clicked()
    assert stream.mute_sets == [True]
    assert label(icon) == icons.mic_mute
    assert icon.get_tooltip_text() == "Muted"
    for widget in (icon, icon.control_label, icon.control_button):
        assert has_class(widget, "muted")

    icon.control_button.clicked()
    assert label(icon) == icons.mic
    assert icon.get_tooltip_text() == "50%"
    for widget in (icon, icon.control_label, icon.control_button):
        assert not has_class(widget, "muted")

    stream.change(muted=True)  # muted elsewhere
    assert label(icon) == icons.mic_mute
    assert has_class(icon, "muted") and has_class(icon.control_label, "muted")
    stream.change(muted=False)
    assert label(icon) == icons.mic
    assert not has_class(icon, "muted") and not has_class(icon.control_label, "muted")
    assert stream.volume_sets == []


def test_destroyed_controls_stop_listening(audio, brightness):
    """The services outlive the bars and dashboards (one per monitor)."""
    from fabric.widgets.box import Box

    def listening(obj, signal):
        signal_id, detail = GObject.signal_parse_name(signal, obj, True)
        return GObject.signal_has_handler_pending(obj, signal_id, detail, False)

    box = Box(children=[
        cls() for cls in (controls.BrightnessSlider, controls.BrightnessSmall,
                          controls.BrightnessIcon, controls.VolumeSlider, controls.VolumeSmall,
                          controls.VolumeIcon, controls.MicSlider, controls.MicSmall,
                          controls.MicIcon)
    ])
    assert listening(brightness, "screen") and listening(audio.speaker, "changed")
    box.destroy()  # children go through GTK's destroy, not the Python override
    for obj, signal in [(brightness, "screen"), (audio, "notify::speaker"),
                        (audio, "notify::microphone"), (audio.speaker, "changed"),
                        (audio.microphone, "changed")]:
        assert not listening(obj, signal), signal
    brightness.change(70)
    audio.speaker.change(volume=10)
