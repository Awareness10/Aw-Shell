"""
Occlusion monitor for the PySide6 shell.

Polls Hyprland via IPC every 500ms to detect fullscreen windows
or windows overlapping shell surface regions. Emits occlusion_changed
on ShellState.

Port of utils/occlusion.py using hyprctl_json instead of subprocess.
"""

from PySide6.QtCore import QObject, QTimer

from core.hyprland import hyprctl_json


class OcclusionMonitor(QObject):
    """Polls for window occlusion and notifies ShellState."""

    POLL_INTERVAL = 500  # ms

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self._state = state
        self._regions: dict[str, tuple] = {}  # surface_id -> (side, size)
        self._last_results: dict[str, bool] = {}

        self._timer = QTimer(self)
        self._timer.setInterval(self.POLL_INTERVAL)
        self._timer.timeout.connect(self._poll)

    def register(self, surface_id: str, side: str, size: int):
        """Register a surface region to monitor.

        side: "top", "bottom", "left", "right"
        size: pixel depth from that edge
        """
        self._regions[surface_id] = (side, size)
        self._last_results[surface_id] = False

    def unregister(self, surface_id: str):
        self._regions.pop(surface_id, None)
        self._last_results.pop(surface_id, None)

    def start(self):
        if self._regions:
            self._timer.start()

    def stop(self):
        self._timer.stop()

    def _poll(self):
        try:
            workspace = hyprctl_json("activeworkspace")
            ws_id = workspace.get("id", -1)
            monitors = hyprctl_json("monitors")
            clients = hyprctl_json("clients")
        except Exception:
            return

        # Find screen dimensions for the active workspace's monitor
        screen_w, screen_h = 1920, 1080
        for mon in monitors:
            if mon.get("activeWorkspace", {}).get("id") == ws_id:
                screen_w = mon.get("width", 1920)
                screen_h = mon.get("height", 1080)
                break

        for surface_id, (side, size) in self._regions.items():
            rect = _side_to_rect(side, size, screen_w, screen_h)
            occluded = _check_rect(rect, ws_id, clients, screen_w, screen_h)

            if occluded != self._last_results.get(surface_id):
                self._last_results[surface_id] = occluded
                self._state.occlusion_changed.emit(surface_id, occluded)


def _side_to_rect(
    side: str, size: int, screen_w: int, screen_h: int
) -> tuple[int, int, int, int]:
    """Convert (side, size) to (x, y, width, height)."""
    if side == "top":
        return (0, 0, screen_w, size)
    elif side == "bottom":
        return (0, screen_h - size, screen_w, size)
    elif side == "left":
        return (0, 0, size, screen_h)
    elif side == "right":
        return (screen_w - size, 0, size, screen_h)
    return (0, 0, 0, 0)


def _check_rect(
    rect: tuple[int, int, int, int],
    workspace_id: int,
    clients: list,
    screen_w: int,
    screen_h: int,
) -> bool:
    """Check if any client window overlaps the rect on the given workspace."""
    ox, oy, ow, oh = rect
    ox2, oy2 = ox + ow, oy + oh

    for client in clients:
        if not client.get("mapped", False):
            continue
        if client.get("workspace", {}).get("id") != workspace_id:
            continue

        pos = client.get("at")
        size = client.get("size")
        if not pos or not size:
            continue

        wx, wy = pos
        ww, wh = size

        # Fullscreen check
        if (ww, wh) == (screen_w, screen_h) and (wx, wy) == (0, 0):
            if oy == 0 and oh > 0:
                return True

        # Rectangle intersection
        if not (wx + ww <= ox or wx >= ox2 or wy + wh <= oy or wy >= oy2):
            return True

    return False
