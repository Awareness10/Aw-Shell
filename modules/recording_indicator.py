import time

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from gi.repository import GLib

import config.data as data
import modules.icons as icons
from modules.tools import ToolsStatusMonitor, toggle_screenrecord


class RecordingIndicator(Button):
    """Bar pill shown while a screen recording runs: a pulsing dot and the
    elapsed time. Clicking it stops the recording."""

    def __init__(self, **kwargs):
        self.dot = Label(name="recording-dot", markup=icons.dot)
        self.elapsed = Label(name="recording-time", label="00:00", visible=not data.VERTICAL)
        self.elapsed.set_no_show_all(data.VERTICAL)

        super().__init__(
            name="recording-indicator",
            tooltip_markup="<b>Recording</b>\nClick to stop.",
            on_clicked=lambda *_: toggle_screenrecord(),
            child=Box(
                orientation="v" if data.VERTICAL else "h",
                spacing=4,
                children=[self.dot, self.elapsed],
            ),
            h_align="center",
            v_align="center",
            **kwargs,
        )

        # Stay hidden through the bar's show_all until a recording starts
        self.set_no_show_all(True)
        self.hide()
        self._timer_id = None

        ToolsStatusMonitor.get().connect(self._on_status)

    def _on_status(self, recording, _pomodoro, _gamemode):
        if recording:
            self._tick()
            # show_all() is a no-op on a no_show_all widget
            self.get_child().show_all()
            self.show()
            if self._timer_id is None:
                self._timer_id = GLib.timeout_add_seconds(1, self._tick)
        else:
            self.hide()
            if self._timer_id is not None:
                GLib.source_remove(self._timer_id)
                self._timer_id = None

    def _tick(self) -> bool:
        since = ToolsStatusMonitor.get().recording_since
        seconds = int(time.time() - since) if since else 0
        hours, rest = divmod(seconds, 3600)
        minutes, seconds = divmod(rest, 60)
        text = f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"
        self.elapsed.set_label(text)
        return True
