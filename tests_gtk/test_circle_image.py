"""CircleImage: the player shows the wallpaper (often 5K) in a ~200 px
circle on every monitor; decode it once, and no bigger than needed."""

import pytest
from gi.repository import GdkPixbuf

import widgets.circle_image as circle_image
from widgets.circle_image import CircleImage


def _save(path, width, height, kind="png"):
    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, width, height)
    pixbuf.savev(path, kind, [], [])


@pytest.fixture
def wallpaper(tmp_path, sandbox):
    path = tmp_path / "wall.png"
    _save(str(path), 3000, 1500)
    circle_image._loaded.clear()
    return str(path)


@pytest.mark.parametrize("kind", ["png", "jpeg"])
def test_wallpaper_decoded_once_at_reduced_size(wallpaper, monkeypatch, kind):
    if kind == "jpeg":
        _save(wallpaper, 3000, 1500, "jpeg")  # decoded at 1/2 to 1/8 size
    decodes = []
    real = circle_image._decode
    monkeypatch.setattr(circle_image, "_decode", lambda path: decodes.append(path) or real(path))
    first = CircleImage(image_file=wallpaper, size=162)
    second = CircleImage(image_file=wallpaper, size=198)
    assert len(decodes) == 1  # every monitor's player shares the decoded image
    source = first._orig_image
    assert circle_image.SOURCE_SIDE <= min(source.get_width(), source.get_height()) < 1500
    assert source.get_width() == 2 * source.get_height()  # same shape
    assert (first._image.get_width(), first._image.get_height()) == (162, 162)
    assert (second._image.get_width(), second._image.get_height()) == (198, 198)


def test_transparency_kept(tmp_path, sandbox):
    path = str(tmp_path / "icon.png")
    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 64, 64)
    pixbuf.fill(0x00000000)
    pixbuf.savev(path, "png", [], [])
    assert circle_image.load_pixbuf(path).get_has_alpha()


def test_falls_back_to_gdkpixbuf(wallpaper, monkeypatch):
    """Formats Pillow can't read (e.g. SVG) still load."""
    import builtins
    real_import = builtins.__import__

    def no_pillow(name, *args, **kwargs):
        if name == "PIL":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pillow)
    image = CircleImage(image_file=wallpaper, size=100)
    assert (image._image.get_width(), image._image.get_height()) == (100, 100)


def test_changed_file_is_decoded_again(wallpaper, monkeypatch):
    import os
    CircleImage(image_file=wallpaper, size=100)
    _save(wallpaper, 400, 800)
    os.utime(wallpaper, ns=(1, 1))  # a new modification time
    image = CircleImage(image_file=wallpaper, size=100)
    source = image._orig_image
    assert (source.get_width(), source.get_height()) == (400, 800)  # small: kept as is
