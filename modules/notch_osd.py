"""The volume and microphone displays the compact notch shows for a moment
when a level changes: icon, bar and label, styled per level."""

from dataclasses import dataclass

from fabric.widgets.box import Box
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from gi.repository import Gtk

from modules.level_sources import AudioSource, MicrophoneSource, SpeakerSource


@dataclass(frozen=True)
class DisplayStyle:
    kind: str  # "volume" or "mic": widget names and style class prefix
    muted_at_zero: bool  # volume 0 counts as muted
    icons: dict  # level ("muted", "low", "medium", "high") -> icon name


VOLUME = DisplayStyle("volume", True, {
    "muted": "audio-volume-muted-symbolic",
    "low": "audio-volume-low-symbolic",
    "medium": "audio-volume-medium-symbolic",
    "high": "audio-volume-high-symbolic",
})
MIC = DisplayStyle("mic", False, {
    "muted": "microphone-disabled-symbolic",
    "low": "microphone-sensitivity-high-symbolic",
    "medium": "microphone-sensitivity-high-symbolic",
    "high": "microphone-sensitivity-high-symbolic",
})
LEVELS = ("muted", "low", "medium", "high")


def level(volume: int, muted: bool, muted_at_zero: bool) -> str:
    if muted or (muted_at_zero and volume == 0):
        return "muted"
    if volume <= 33:
        return "low"
    return "medium" if volume <= 66 else "high"


class LevelDisplay:
    """One display (volume or mic) over its audio source."""

    def __init__(self, source: AudioSource, style: DisplayStyle):
        self.source = source
        self.style = style
        self.icon = Image(
            name=f"{style.kind}-display-icon", icon_name=style.icons["high"], icon_size=16
        )
        self.label = Label(name=f"{style.kind}-display-label", label="...")
        self.bar = Gtk.ProgressBar(name=f"{style.kind}-display-bar")
        self.bar.set_fraction(1.0)
        self.bar.set_show_text(False)
        self.bar.set_hexpand(False)
        for widget in (self.icon, self.label, self.bar):
            widget.set_valign(Gtk.Align.CENTER)
        self.box = Box(
            name=f"{style.kind}-display-box",
            orientation="h",
            spacing=8,
            h_align="center",
            v_align="center",
            children=[self.icon, self.bar, self.label],
        )

    def update(self) -> bool:
        """Show the source's level; False when there's no device."""
        if not self.source.available:
            return False
        volume = int(round(self.source.value))
        current = level(volume, self.source.muted, self.style.muted_at_zero)
        self.bar.set_fraction(volume / 100.0)
        for widget in (self.box, self.icon, self.bar):
            context = widget.get_style_context()
            for name in LEVELS:
                context.remove_class(f"{self.style.kind}-{name}")
            context.add_class(f"{self.style.kind}-{current}")
        self.icon.set_from_icon_name(self.style.icons[current], 16)
        self.label.set_text("Muted" if current == "muted" else f"{volume}%")
        return True


class AudioDisplays:
    """The volume and mic displays, following the default devices.

    show(display) is called for a level change on the current device; a new
    default device, and anything before arm(), only updates the widgets.
    """

    def __init__(self, show):
        self._show = show
        self._armed = False
        self.volume = LevelDisplay(SpeakerSource(), VOLUME)
        self.mic = LevelDisplay(MicrophoneSource(), MIC)

    def connect(self) -> None:
        for display in (self.volume, self.mic):
            display.source.watch(
                lambda d=display: self._changed(d),
                on_new_stream=lambda d=display: d.update(),
            )
            display.update()

    def arm(self) -> None:
        self._armed = True

    def _changed(self, display: LevelDisplay) -> None:
        if display.update() and self._armed:
            self._show(display)

    def disconnect(self) -> None:
        for display in (self.volume, self.mic):
            display.source.unwatch()
