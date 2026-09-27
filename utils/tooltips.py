"""Skip redundant tooltip updates.

Every set_tooltip_text/markup call makes GTK3 re-query the tooltip under the
pointer, which restarts its 500ms hover delay. With several widgets refreshing
their tooltip on timers, the delay never elapses and no tooltip ever shows, so
only pass a call through when the tooltip actually changes.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


def install_tooltip_dedup() -> None:
    set_text = Gtk.Widget.set_tooltip_text
    set_markup = Gtk.Widget.set_tooltip_markup

    def set_tooltip_text(self, text):
        # GTK stores an empty tooltip as None
        if (text or None) != self.get_tooltip_text():
            set_text(self, text)

    def set_tooltip_markup(self, markup):
        if (markup or None) != self.get_tooltip_markup():
            set_markup(self, markup)

    Gtk.Widget.set_tooltip_text = set_tooltip_text
    Gtk.Widget.set_tooltip_markup = set_tooltip_markup
