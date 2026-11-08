import math
import os
from typing import Literal

import cairo
import gi
from fabric.core.service import Property
from fabric.widgets.widget import Widget

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

# The player's cover is the wallpaper (often 5K), shown at most ~200 px wide:
# decoded once for every monitor's player, and no bigger than needed (JPEG
# decodes at 1/2 to 1/8 size, ~20 ms for a 5K wallpaper instead of ~140 ms)
SOURCE_SIDE = 512
_loaded: dict = {}  # path -> (mtime, pixbuf), for the last file loaded


def _decode(path: str) -> GdkPixbuf.Pixbuf:
    """The image, shortest side at least SOURCE_SIDE (when it's that big).
    GdkPixbuf decodes the whole image even when asked for a smaller size, so
    Pillow does it, with GdkPixbuf for formats Pillow can't read."""
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.draft("RGB", (SOURCE_SIDE, SOURCE_SIDE))
            has_alpha = image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
            image = image.convert("RGBA" if has_alpha else "RGB")
            factor = min(image.size) // SOURCE_SIDE
            if factor > 1:  # formats without draft, e.g. PNG
                image = image.reduce(factor)
            width, height = image.size
            channels = 4 if has_alpha else 3
            return GdkPixbuf.Pixbuf.new_from_bytes(
                GLib.Bytes.new(image.tobytes()), GdkPixbuf.Colorspace.RGB,
                has_alpha, 8, width, height, width * channels,
            )
    except Exception:
        return GdkPixbuf.Pixbuf.new_from_file(path)


def load_pixbuf(path: str) -> GdkPixbuf.Pixbuf:
    """The image at path, no bigger than needed; shared while unchanged."""
    try:
        mtime = os.stat(path).st_mtime_ns
    except OSError:
        mtime = None
    cached = _loaded.get(path)
    if cached and mtime is not None and cached[0] == mtime:
        return cached[1]
    pixbuf = _decode(path)
    _loaded.clear()
    _loaded[path] = (mtime, pixbuf)
    return pixbuf


class CircleImage(Gtk.DrawingArea, Widget):
    """A widget that displays an image in a circular shape with a 1:1 aspect ratio."""

    @Property(int, "read-write")
    def angle(self) -> int:
        return self._angle

    @angle.setter
    def angle(self, value: int):
        self._angle = value % 360
        self.queue_draw()

    def __init__(
        self,
        image_file: str | None = None,
        pixbuf: GdkPixbuf.Pixbuf | None = None,
        name: str | None = None,
        visible: bool = True,
        all_visible: bool = False,
        style: str | None = None,
        tooltip_text: str | None = None,
        tooltip_markup: str | None = None,
        h_align: Literal["fill", "start", "end", "center", "baseline"] | Gtk.Align | None = None,
        v_align: Literal["fill", "start", "end", "center", "baseline"] | Gtk.Align | None = None,
        h_expand: bool = False,
        v_expand: bool = False,
        size: int | None = None,
        **kwargs,
    ):
        Gtk.DrawingArea.__init__(self)
        Widget.__init__(
            self,
            name=name,
            visible=visible,
            all_visible=all_visible,
            style=style,
            tooltip_text=tooltip_text,
            tooltip_markup=tooltip_markup,
            h_align=h_align,
            v_align=v_align,
            h_expand=h_expand,
            v_expand=v_expand,
            size=size,
            **kwargs,
        )
        self.size = size if size is not None else 100  # Default size if not provided
        self._angle = 0
        self._orig_image: GdkPixbuf.Pixbuf | None = None  # Original image for reprocessing
        self._image: GdkPixbuf.Pixbuf | None = None
        if image_file:
            pix = load_pixbuf(image_file)
            self._orig_image = pix
            self._image = self._process_image(pix)
        elif pixbuf:
            self._orig_image = pixbuf
            self._image = self._process_image(pixbuf)
        self.connect("draw", self.on_draw)

    def _process_image(self, pixbuf: GdkPixbuf.Pixbuf) -> GdkPixbuf.Pixbuf:
        """Crop the image to a centered square and scale it to the widget’s size."""
        width, height = pixbuf.get_width(), pixbuf.get_height()
        if width != height:
            square_size = min(width, height)
            x_offset = (width - square_size) // 2
            y_offset = (height - square_size) // 2
            pixbuf = pixbuf.new_subpixbuf(x_offset, y_offset, square_size, square_size)
        else:
            square_size = width
        if square_size != self.size:
            pixbuf = pixbuf.scale_simple(self.size, self.size, GdkPixbuf.InterpType.BILINEAR)
        return pixbuf

    def on_draw(self, widget: "CircleImage", ctx: cairo.Context):
        if self._image:
            ctx.save()
            # Create a circular clipping path
            ctx.arc(self.size / 2, self.size / 2, self.size / 2, 0, 2 * math.pi)
            ctx.clip()
            # Rotate around the center of the square image
            ctx.translate(self.size / 2, self.size / 2)
            ctx.rotate(self._angle * math.pi / 180.0)
            ctx.translate(-self.size / 2, -self.size / 2)
            Gdk.cairo_set_source_pixbuf(ctx, self._image, 0, 0)
            ctx.paint()
            ctx.restore()

    def set_image_from_file(self, new_image_file: str):
        if not new_image_file:
            return
        pixbuf = load_pixbuf(new_image_file)
        self._orig_image = pixbuf
        self._image = self._process_image(pixbuf)
        self.queue_draw()

    def set_image_from_pixbuf(self, pixbuf: GdkPixbuf.Pixbuf):
        if not pixbuf:
            return
        self._orig_image = pixbuf
        self._image = self._process_image(pixbuf)
        self.queue_draw()

    def set_image_size(self, size: int):
        self.size = size
        if self._orig_image:
            self._image = self._process_image(self._orig_image)
        self.queue_draw()
