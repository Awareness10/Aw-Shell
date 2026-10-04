"""Every way of applying a wallpaper must run matugen non-interactively.

matugen 4.0 asks which source color to use when it has a TTY and fails with
"not a terminal" without one; the shell never has one, so each `matugen image`
call needs `--source-color-index 0`.
"""

import os
import time
from pathlib import Path

import pytest
from gi.repository import Gtk

WALLPAPER = "example.jpg"


@pytest.fixture
def selector(sandbox, run_pending):
    from modules.wallpapers import WallpaperSelector

    current_wall = Path.home() / ".current.wall"
    original = os.readlink(current_wall)
    widget = WallpaperSelector()
    widget.matugen_switcher.set_active(True)
    run_pending()
    yield widget
    widget.destroy()
    current_wall.unlink(missing_ok=True)
    current_wall.symlink_to(original)


def matugen_calls(sandbox, run_pending, before, timeout=5.0):
    """matugen commands logged since `before`; the stub runs asynchronously."""
    deadline = time.monotonic() + timeout
    while True:
        run_pending()
        calls = [c for c in sandbox.commands()[before:] if c.startswith("matugen ")]
        if calls or time.monotonic() > deadline:
            return calls
        time.sleep(0.05)


def assert_non_interactive(calls):
    assert len(calls) == 1, calls
    assert calls[0].startswith("matugen image ")
    assert calls[0].endswith(" --source-color-index 0")


def test_selecting_wallpaper(sandbox, run_pending, selector):
    before = len(sandbox.commands())
    model = selector.viewport.get_model()
    model.clear()
    model.append([None, WALLPAPER])
    selector.on_wallpaper_selected(selector.viewport, Gtk.TreePath.new_first())
    assert_non_interactive(matugen_calls(sandbox, run_pending, before))


def test_random_wallpaper(sandbox, run_pending, selector):
    before = len(sandbox.commands())
    selector.files = [WALLPAPER]
    selector.set_random_wallpaper(None)
    assert_non_interactive(matugen_calls(sandbox, run_pending, before))


def test_changing_scheme(sandbox, run_pending, selector):
    before = len(sandbox.commands())
    selector._apply_scheme()
    assert_non_interactive(matugen_calls(sandbox, run_pending, before))


def _pump_until(run_pending, condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        run_pending()
        time.sleep(0.02)
    return condition()


def test_loads_every_wallpaper_and_normalises_names(run_pending, monkeypatch, tmp_path):
    """Names with capitals or spaces get renamed; loading must not stop at the
    first rename."""
    from PIL import Image

    import config.data as data
    from modules.wallpapers import WallpaperSelector

    walls = tmp_path / "walls"
    walls.mkdir()
    for name in ("Big Sky.jpg", "Night City.PNG", "forest.jpg"):
        Image.new("RGB", (8, 8), "teal").save(walls / name, format="PNG")
    monkeypatch.setattr(data, "WALLPAPERS_DIR", str(walls))
    monkeypatch.setattr(WallpaperSelector, "CACHE_DIR", str(tmp_path / "thumbs"))

    selector = WallpaperSelector()
    try:
        expected = ["big-sky.jpg", "forest.jpg", "night-city.png"]
        assert _pump_until(run_pending, lambda: len(selector.viewport.get_model()) == 3), \
            f"files={selector.files}, on disk={sorted(os.listdir(walls))}"
        assert selector.files == expected
        assert sorted(os.listdir(walls)) == expected
    finally:
        selector.destroy()
        run_pending()
