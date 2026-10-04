"""Tests for modules/wallpapers.py helpers, thumbnail cache and scheme changes.

The matugen command itself is checked against real GTK in
tests_gtk/test_wallpapers.py.
"""

import os
from unittest.mock import MagicMock

import pytest

# =========================================================================
# WallpaperSelector utility method tests
# =========================================================================

class TestWallpaperHelpers:
    """Test static/pure methods that don't require GTK."""

    def test_is_image_png(self):
        """_is_image should accept common image extensions."""
        # Import by reading source since we can't import the GTK module
        assert "example.png".lower().endswith(
            (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
        )

    def test_is_image_jpg(self):
        assert "photo.JPG".lower().endswith(
            (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
        )

    def test_is_image_webp(self):
        assert "wall.webp".lower().endswith(
            (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
        )

    def test_is_not_image_txt(self):
        assert not "readme.txt".lower().endswith(
            (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
        )

    def test_is_not_image_py(self):
        assert not "script.py".lower().endswith(
            (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
        )


# =========================================================================
# Thumbnail cache invalidation
# =========================================================================

class TestThumbnailCacheInvalidation:
    """Regression: a wallpaper whose bytes change must not keep the old preview.

    The thumbnail cache was keyed on the file *name* alone and `_process_file`
    treated "cache file exists" as "cache is current". Replacing a wallpaper
    while the shell was not running (a `cp -p`/`rsync -a` batch copy, a restore
    from backup, or pointing `wallpapers_dir` at another folder holding a
    same-named file) left the previous image's thumbnail cached forever, so the
    grid showed a different wallpaper's preview.
    """

    @staticmethod
    def _import_wallpapers():
        """Import modules.wallpapers behind local fabric.widgets stand-ins.

        The widget bases must be real classes (subclassing a MagicMock makes
        the subclass a MagicMock too), and the stand-ins are scoped to this
        import so they cannot collide with the fakes other test modules
        install. `config` is reimported for the same reason: other test
        modules leave a stand-in for it in sys.modules.
        """
        import importlib
        import sys
        import types

        widgets = types.ModuleType("fabric.widgets")
        stubs = {"fabric.widgets": widgets}
        for mod_name, cls_name in (
            ("box", "Box"),
            ("button", "Button"),
            ("entry", "Entry"),
            ("label", "Label"),
            ("scrolledwindow", "ScrolledWindow"),
        ):
            mod = types.ModuleType(f"fabric.widgets.{mod_name}")
            setattr(
                mod, cls_name, type(cls_name, (), {"__init__": lambda self, **kw: None})
            )
            setattr(widgets, mod_name, mod)
            stubs[f"fabric.widgets.{mod_name}"] = mod

        # Swap only these keys and put them back afterwards: clearing all of
        # sys.modules (as patch.dict does) would also evict packages imported
        # during the block, e.g. PIL, leaving this module with a PIL.Image
        # whose plugins are registered on a different copy of the package.
        reimport = ("config", "config.config", "config.data", "modules.wallpapers")
        saved = {key: sys.modules.get(key) for key in (*stubs, *reimport)}
        try:
            sys.modules.update(stubs)
            for name in reimport:
                sys.modules.pop(name, None)
            return importlib.import_module("modules.wallpapers")
        finally:
            for key, module in saved.items():
                if module is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = module

    @pytest.fixture
    def selector(self, tmp_path, monkeypatch):
        """A stub carrying just the state `_get_cache_path`/`_process_file` touch."""
        wallpapers = self._import_wallpapers()

        walls = tmp_path / "walls"
        cache = tmp_path / "thumbs"
        walls.mkdir()
        cache.mkdir()
        # Patch the config.data object this module actually holds a reference to.
        monkeypatch.setattr(wallpapers.data, "WALLPAPERS_DIR", str(walls))

        selector_cls = wallpapers.WallpaperSelector

        class Stub:
            CACHE_DIR = str(cache)

            def __init__(self):
                self.files = []
                self.thumbnail_queue = []
                self._destroyed = False

            def _process_batch(self):
                """Draining the queue needs GTK; the tests read it directly."""
                return False

            _get_cache_path = selector_cls._get_cache_path
            _process_file = selector_cls._process_file
            _prune_cache = selector_cls._prune_cache

        return Stub(), walls, cache

    @staticmethod
    def _write_image(path, color, size, mtime=None):
        from PIL import Image

        Image.new("RGB", size, color).save(path, "PNG")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return os.stat(path).st_mtime

    def test_replaced_file_with_older_mtime_gets_new_cache_key(self, selector):
        """Same name + older timestamp must still invalidate the cached thumbnail."""
        stub, walls, _ = selector
        wall = walls / "pixel-art.png"

        old_mtime = self._write_image(wall, (255, 0, 0), (400, 300), mtime=1_700_000_000)
        before = stub._get_cache_path("pixel-art.png")

        # Replace the content, keeping the *original* mtime, as `cp -p` would.
        self._write_image(wall, (0, 128, 255), (800, 600), mtime=old_mtime)
        after = stub._get_cache_path("pixel-art.png")

        assert before != after, (
            "Replaced wallpaper reused the previous thumbnail cache entry"
        )

    def test_unchanged_file_keeps_cache_key(self, selector):
        """An untouched wallpaper must keep hitting its cached thumbnail."""
        stub, walls, _ = selector
        wall = walls / "pixel-art.png"
        self._write_image(wall, (255, 0, 0), (400, 300), mtime=1_700_000_000)

        assert stub._get_cache_path("pixel-art.png") == stub._get_cache_path(
            "pixel-art.png"
        )

    def test_process_file_regenerates_thumbnail_after_replacement(self, selector):
        """End-to-end: the queued thumbnail must match the file's current content."""
        from PIL import Image

        stub, walls, _ = selector
        wall = walls / "pixel-art.png"
        old_mtime = self._write_image(wall, (255, 0, 0), (400, 300), mtime=1_700_000_000)

        stub._process_file("pixel-art.png")
        first_cache, _ = stub.thumbnail_queue[-1]
        with Image.open(first_cache) as thumb:
            assert thumb.convert("RGB").getpixel((0, 0)) == (255, 0, 0)

        self._write_image(wall, (0, 128, 255), (800, 600), mtime=old_mtime)
        stub._process_file("pixel-art.png")
        second_cache, _ = stub.thumbnail_queue[-1]
        with Image.open(second_cache) as thumb:
            assert thumb.convert("RGB").getpixel((0, 0)) == (0, 128, 255), (
                "Thumbnail still shows the previous image's content"
            )

    def test_prune_cache_removes_orphans_only(self, selector):
        """Stale entries are swept; entries for current wallpapers survive."""
        stub, walls, cache = selector
        self._write_image(walls / "keep.png", (10, 20, 30), (100, 100))
        stub.files = ["keep.png"]

        keep = stub._get_cache_path("keep.png")
        open(keep, "wb").close()
        orphan = os.path.join(str(cache), "deadbeef" * 4 + ".png")
        open(orphan, "wb").close()

        stub._prune_cache()

        assert os.path.exists(keep)
        assert not os.path.exists(orphan)


class TestSchemeChangeApplies:
    """Regression: picking a color scheme only printed it; the theme changed
    only after double-clicking a wallpaper again."""

    @pytest.fixture
    def env(self, tmp_path, monkeypatch):
        wallpapers = TestThumbnailCacheInvalidation._import_wallpapers()
        commands, timers = [], {}

        class FakeGLib:
            def timeout_add(self, _ms, callback):
                timers[len(timers) + 1] = callback
                return len(timers)

            def source_remove(self, source_id):
                timers.pop(source_id, None)

        monkeypatch.setattr(wallpapers, "GLib", FakeGLib())
        monkeypatch.setattr(wallpapers, "exec_shell_command_async", commands.append)
        monkeypatch.setenv("HOME", str(tmp_path))
        wall = tmp_path / "walls" / "forest.png"
        wall.parent.mkdir()
        wall.write_bytes(b"png")
        (tmp_path / ".current.wall").symlink_to(wall)

        monkeypatch.setattr(wallpapers.data, "MATUGEN_SCHEME_FILE", tmp_path / "matugen-scheme")
        cls = wallpapers.WallpaperSelector

        class Stub:
            SCHEME_APPLY_DELAY_MS = cls.SCHEME_APPLY_DELAY_MS
            DEFAULT_SCHEME = cls.DEFAULT_SCHEME
            on_scheme_changed = cls.on_scheme_changed
            _apply_scheme = cls._apply_scheme
            _load_scheme = cls._load_scheme
            _save_scheme = cls._save_scheme
            schemes = {"scheme-tonal-spot": "Tonal Spot", "scheme-expressive": "Expressive",
                       "scheme-content": "Content", "scheme-fidelity": "Fidelity",
                       "scheme-neutral": "Neutral"}

            def __init__(self):
                self._scheme_apply_id = None
                self._custom_hex = None
                self.scheme = "scheme-expressive"
                self.matugen = True
                self.scheme_dropdown = MagicMock(get_active_id=lambda: self.scheme)
                self.matugen_switcher = MagicMock(get_active=lambda: self.matugen)

        def fire():
            for callback in list(timers.values()):
                callback()
            timers.clear()

        return Stub(), commands, timers, fire, wall

    def test_applied_scheme_is_saved(self, env, tmp_path):
        selector, _, _, fire, _ = env
        selector.on_scheme_changed(None)
        fire()
        assert (tmp_path / "matugen-scheme").read_text() == "scheme-expressive"

    def test_saved_scheme_is_loaded(self, env, tmp_path):
        selector, *_ = env
        (tmp_path / "matugen-scheme").write_text("scheme-expressive\n")
        assert selector._load_scheme() == "scheme-expressive"

    @pytest.mark.parametrize("content", [None, "", "scheme-bogus"])
    def test_missing_or_unknown_scheme_falls_back_to_tonal_spot(self, env, tmp_path, content):
        selector, *_ = env
        if content is not None:
            (tmp_path / "matugen-scheme").write_text(content)
        assert selector._load_scheme() == "scheme-tonal-spot"

    def test_scheme_change_reapplies_current_wallpaper(self, env):
        selector, commands, _, fire, wall = env
        selector.on_scheme_changed(None)
        fire()
        assert commands == [f'matugen image "{wall}" -t scheme-expressive --source-color-index 0']

    def test_cycling_schemes_applies_once(self, env):
        selector, commands, timers, fire, _ = env
        for scheme in ("scheme-content", "scheme-fidelity", "scheme-neutral"):
            selector.scheme = scheme
            selector.on_scheme_changed(None)
        assert len(timers) == 1
        fire()
        assert len(commands) == 1 and "-t scheme-neutral" in commands[0]

    def test_custom_color_mode_reapplies_last_color(self, env):
        selector, commands, _, fire, _ = env
        selector.matugen = False
        selector._custom_hex = "#ff8800"
        selector.on_scheme_changed(None)
        fire()
        assert commands == ['matugen color hex "#ff8800" -t scheme-expressive']

    def test_custom_color_mode_without_applied_color_does_nothing(self, env):
        selector, commands, _, fire, _ = env
        selector.matugen = False
        selector.on_scheme_changed(None)
        fire()
        assert commands == []
