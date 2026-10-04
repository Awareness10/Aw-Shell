"""Tooltip dedup: only real changes may reach GTK (each call restarts the
hover delay, so timers refreshing an unchanged tooltip would hide it forever)."""

import pytest
from gi.repository import Gtk

from utils.tooltips import install_tooltip_dedup


@pytest.fixture
def reaching_gtk():
    """Install the dedup over counting wrappers; restore GTK's methods after."""
    original_text = Gtk.Widget.set_tooltip_text
    original_markup = Gtk.Widget.set_tooltip_markup
    calls = []

    def counting_text(self, text):
        calls.append(("text", text))
        original_text(self, text)

    def counting_markup(self, markup):
        calls.append(("markup", markup))
        original_markup(self, markup)

    Gtk.Widget.set_tooltip_text = counting_text
    Gtk.Widget.set_tooltip_markup = counting_markup
    install_tooltip_dedup()
    yield calls
    Gtk.Widget.set_tooltip_text = original_text
    Gtk.Widget.set_tooltip_markup = original_markup


@pytest.fixture
def label():
    widget = Gtk.Label()
    yield widget
    widget.destroy()


def test_unchanged_text_is_skipped(reaching_gtk, label):
    label.set_tooltip_text("CPU 12%")
    label.set_tooltip_text("CPU 12%")
    assert reaching_gtk == [("text", "CPU 12%")]
    assert label.get_tooltip_text() == "CPU 12%"


def test_changed_text_passes_through(reaching_gtk, label):
    label.set_tooltip_text("CPU 12%")
    label.set_tooltip_text("CPU 13%")
    assert reaching_gtk == [("text", "CPU 12%"), ("text", "CPU 13%")]
    assert label.get_tooltip_text() == "CPU 13%"


def test_empty_text_counts_as_no_tooltip(reaching_gtk, label):
    label.set_tooltip_text("")
    label.set_tooltip_text(None)
    assert reaching_gtk == []


def test_clearing_a_tooltip_passes_through(reaching_gtk, label):
    label.set_tooltip_text("Recording")
    label.set_tooltip_text(None)
    assert reaching_gtk == [("text", "Recording"), ("text", None)]
    assert label.get_tooltip_text() is None


def test_markup_is_deduplicated_too(reaching_gtk, label):
    label.set_tooltip_markup("<b>Battery</b> 80%")
    label.set_tooltip_markup("<b>Battery</b> 80%")
    label.set_tooltip_markup("<b>Battery</b> 79%")
    assert reaching_gtk == [("markup", "<b>Battery</b> 80%"), ("markup", "<b>Battery</b> 79%")]
