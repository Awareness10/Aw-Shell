"""Tracks which monitors have a window covering their top edge.

State is recomputed over Hyprland's IPC socket when window or workspace
events arrive, rather than by polling hyprctl subprocesses.
"""

import json

from gi.repository import GLib
from loguru import logger

TOP_EDGE_SIZE = 40

# Events after which a window may cover or uncover a monitor's top edge
_REFRESH_EVENTS = (
    "openwindow",
    "closewindow",
    "movewindowv2",
    "workspacev2",
    "focusedmonv2",
    "moveworkspacev2",
    "activespecialv2",
    "fullscreen",
    "changefloatingmode",
    "monitoraddedv2",
    "monitorremovedv2",
    "activewindowv2",
)


def _logical_size(monitor: dict) -> tuple[float, float]:
    # Client geometry is in logical pixels; monitor size is physical
    scale = monitor.get("scale") or 1.0
    width = monitor.get("width", 0) / scale
    height = monitor.get("height", 0) / scale
    if monitor.get("transform", 0) % 2:  # rotated 90/270
        width, height = height, width
    return width, height


def is_top_edge_occluded(monitor: dict, clients: list[dict], size: int = TOP_EDGE_SIZE) -> bool:
    """Whether any visible window on `monitor` overlaps its top `size` pixels."""
    width, _ = _logical_size(monitor)
    x1, y1 = monitor.get("x", 0), monitor.get("y", 0)
    x2, y2 = x1 + width, y1 + size

    workspaces = {monitor.get("activeWorkspace", {}).get("id")}
    special = monitor.get("specialWorkspace", {}).get("id")
    if special:
        workspaces.add(special)

    for client in clients:
        if not client.get("mapped", False) or client.get("hidden", False):
            continue
        if client.get("workspace", {}).get("id") not in workspaces:
            continue
        at, dims = client.get("at"), client.get("size")
        if not at or not dims:
            continue
        cx1, cy1 = at
        cx2, cy2 = cx1 + dims[0], cy1 + dims[1]
        if cx1 < x2 and cx2 > x1 and cy1 < y2 and cy2 > y1:
            return True
    return False


class OcclusionWatcher:
    """Shared, event-driven occlusion state for every monitor."""

    DEBOUNCE_MS = 50
    # Hyprland emits no event for resizing or dragging a window, so
    # re-check occasionally to catch those
    SAFETY_REFRESH_SECONDS = 5
    _instance = None

    @classmethod
    def get(cls) -> "OcclusionWatcher":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        from fabric.hyprland.widgets import get_hyprland_connection

        self._conn = get_hyprland_connection()
        self._occluded: dict[str, bool] = {}
        self._focused: str | None = None
        self._listeners = []
        self._refresh_source_id = None

        for event in _REFRESH_EVENTS:
            self._conn.connect(f"event::{event}", self._schedule_refresh)
        GLib.timeout_add_seconds(self.SAFETY_REFRESH_SECONDS, self._safety_refresh)
        self.refresh()

    def connect(self, callback) -> None:
        """Call `callback()` whenever any monitor's occlusion changes."""
        self._listeners.append(callback)

    def is_occluded(self, monitor_name: str | None) -> bool:
        """Occlusion for `monitor_name`, or the focused monitor if unknown."""
        if monitor_name not in self._occluded:
            monitor_name = self._focused
        return self._occluded.get(monitor_name, False)

    def refresh(self) -> None:
        monitors = self._query("j/monitors")
        clients = self._query("j/clients")
        if monitors is None or clients is None:
            return

        occluded = {m.get("name"): is_top_edge_occluded(m, clients) for m in monitors}
        self._focused = next((m.get("name") for m in monitors if m.get("focused")), None)
        if occluded != self._occluded:
            self._occluded = occluded
            for callback in list(self._listeners):
                callback()

    def _query(self, command: str):
        try:
            return json.loads(self._conn.send_command(command).reply.decode())
        except (ValueError, AttributeError) as e:
            logger.warning(f"[Occlusion] {command} failed: {e}")
            return None

    def _schedule_refresh(self, *_) -> None:
        # Events arrive in bursts (e.g. workspace + focus + activewindow);
        # coalesce them into one refresh
        if self._refresh_source_id is None:
            self._refresh_source_id = GLib.timeout_add(self.DEBOUNCE_MS, self._debounced_refresh)

    def _debounced_refresh(self) -> bool:
        self._refresh_source_id = None
        self.refresh()
        return False

    def _safety_refresh(self) -> bool:
        self.refresh()
        return True
