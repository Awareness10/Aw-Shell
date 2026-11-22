"""The notch's volume and microphone display: a change shows it in the compact
notch for VOLUME_DISPLAY_DURATION, with an icon, bar, label and style classes
per level; startup values and a new default device update it silently."""

from unittest.mock import patch

import pytest
from conftest import pump, pump_until
from test_controls import FakeAudio, FakeStream


@pytest.fixture(scope="module")
def osd():
    """One Notch on a fake audio service (building one is slow)."""
    audio = FakeAudio()
    audio.speaker = FakeStream(volume=40)
    audio.microphone = FakeStream(volume=60)
    with patch("modules.level_sources.Audio", return_value=audio):
        import modules.notch as notch_module
        with patch.object(notch_module, "Audio", return_value=audio, create=True):
            notch = notch_module.Notch(monitor_id=0)
            # startup: signals connect after 100 ms, the display arms 500 ms later
            assert pump_until(lambda: not notch._suppress_first_audio_display, timeout=5)
    notch.audio_fake = audio
    yield notch
    notch.destroy()
    pump()


@pytest.fixture
def notch(osd):
    osd._is_notch_open = False
    osd.VOLUME_DISPLAY_DURATION = 2000
    osd.compact_stack.set_visible_child(osd.active_window_box)
    yield osd
    osd._is_notch_open = False


def _classes(widget, prefix):
    return sorted(c for c in widget.get_style_context().list_classes() if c.startswith(prefix))


def _volume(notch):
    return {
        "shown": notch.compact_stack.get_visible_child() is notch.volume_box,
        "icon": notch.volume_icon.get_icon_name()[0],
        "label": notch.volume_label.get_text(),
        "fraction": round(notch.volume_bar.get_fraction(), 2),
        "classes": [_classes(w, "volume-")
                    for w in (notch.volume_box, notch.volume_icon, notch.volume_bar)],
    }


def _mic(notch):
    return {
        "shown": notch.compact_stack.get_visible_child() is notch.mic_box,
        "icon": notch.mic_icon.get_icon_name()[0],
        "label": notch.mic_label.get_text().strip(),
        "fraction": round(notch.mic_bar.get_fraction(), 2),
        "classes": [_classes(w, "mic-") for w in (notch.mic_box, notch.mic_icon, notch.mic_bar)],
    }


def test_startup_values_are_shown_silently(osd):
    assert osd.volume_label.get_text() == "40%"
    assert osd.mic_label.get_text().strip() == "60%"
    assert osd.compact_stack.get_visible_child() not in (osd.volume_box, osd.mic_box)


@pytest.mark.parametrize("volume, muted, icon, label, cls", [
    (20, False, "audio-volume-low-symbolic", "20%", "volume-low"),
    (33, False, "audio-volume-low-symbolic", "33%", "volume-low"),
    (34, False, "audio-volume-medium-symbolic", "34%", "volume-medium"),
    (66, False, "audio-volume-medium-symbolic", "66%", "volume-medium"),
    (67, False, "audio-volume-high-symbolic", "67%", "volume-high"),
    (100, False, "audio-volume-high-symbolic", "100%", "volume-high"),
    (0, False, "audio-volume-muted-symbolic", "Muted", "volume-muted"),
    (50, True, "audio-volume-muted-symbolic", "Muted", "volume-muted"),
    (49.6, False, "audio-volume-medium-symbolic", "50%", "volume-medium"),
])
def test_volume_change_shows_the_display(notch, volume, muted, icon, label, cls):
    notch.audio_fake.speaker.change(volume=volume, muted=muted)
    assert _volume(notch) == {
        "shown": True, "icon": icon, "label": label,
        "fraction": round(int(round(volume)) / 100, 2), "classes": [[cls]] * 3,
    }
    notch.audio_fake.speaker.change(muted=False)


@pytest.mark.parametrize("volume, muted, icon, label, cls", [
    (20, False, "microphone-sensitivity-high-symbolic", "20%", "mic-low"),
    (50, False, "microphone-sensitivity-high-symbolic", "50%", "mic-medium"),
    (90, False, "microphone-sensitivity-high-symbolic", "90%", "mic-high"),
    (0, False, "microphone-sensitivity-high-symbolic", "0%", "mic-low"),
    (50, True, "microphone-disabled-symbolic", "Muted", "mic-muted"),
])
def test_mic_change_shows_the_display(notch, volume, muted, icon, label, cls):
    notch.audio_fake.microphone.change(volume=volume, muted=muted)
    assert _mic(notch) == {
        "shown": True, "icon": icon, "label": label,
        "fraction": round(volume / 100, 2), "classes": [[cls]] * 3,
    }
    notch.audio_fake.microphone.change(muted=False)


def test_display_returns_to_the_window_title(notch):
    notch.VOLUME_DISPLAY_DURATION = 50
    notch.audio_fake.speaker.change(volume=30)
    assert notch.compact_stack.get_visible_child() is notch.volume_box
    assert pump_until(lambda: notch.compact_stack.get_visible_child() is notch.active_window_box)


def test_mic_change_replaces_a_shown_volume_display(notch):
    notch.audio_fake.speaker.change(volume=30)
    notch.audio_fake.microphone.change(volume=30)
    assert notch.compact_stack.get_visible_child() is notch.mic_box


def test_change_while_open_updates_without_showing(notch):
    notch._is_notch_open = True
    notch.audio_fake.speaker.change(volume=80)
    assert notch.volume_label.get_text() == "80%"
    assert notch.compact_stack.get_visible_child() is notch.active_window_box


def test_new_default_device_updates_silently(notch):
    old = notch.audio_fake.speaker
    new = FakeStream(volume=10)
    notch.audio_fake.speaker = new
    pump()
    assert notch.volume_label.get_text() == "10%"
    assert notch.compact_stack.get_visible_child() is notch.active_window_box
    new.change(volume=25)  # follows the new stream
    assert _volume(notch)["label"] == "25%" and _volume(notch)["shown"]
    notch.audio_fake.speaker = old
    pump()
