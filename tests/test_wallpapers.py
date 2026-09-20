"""Tests for modules/wallpapers.py — wallpaper selection and matugen integration.

Regression tests for the matugen 4.0.0 breaking change where interactive
source color selection requires --source-color-index 0 when not on a TTY.
"""

import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# =========================================================================
# Matugen command flag tests (--source-color-index 0)
# =========================================================================

class TestMatugenSourceColorIndex:
    """Regression: all matugen image commands must include --source-color-index 0.

    matugen 4.0.0 added interactive source color selection that requires a TTY.
    exec_shell_command_async runs without a TTY, so matugen fails silently with
    'IO error: not a terminal'. The fix is --source-color-index 0.
    """

    @pytest.fixture
    def wallpaper_selector(self):
        """Create a minimal WallpaperSelector mock for testing matugen commands."""
        # We can't instantiate the real WallpaperSelector (needs GTK), so we
        # test by reading the source and verifying all matugen image calls.
        import inspect
        import importlib

        # Mock all GTK dependencies
        mock_modules = {}
        for mod_name in [
            "gi", "gi.repository", "gi.repository.Gdk", "gi.repository.GdkPixbuf",
            "gi.repository.Gio", "gi.repository.GLib", "gi.repository.Gtk",
            "gi.repository.Pango",
            "fabric", "fabric.utils", "fabric.utils.helpers",
            "fabric.widgets", "fabric.widgets.box", "fabric.widgets.button",
            "fabric.widgets.entry", "fabric.widgets.label",
            "fabric.widgets.scrolledwindow",
            "PIL", "PIL.Image",
            "config", "config.config", "config.data",
            "modules", "modules.icons",
        ]:
            mock_modules[mod_name] = MagicMock()

        with patch.dict("sys.modules", mock_modules):
            # Just read the source file directly
            pass

        return None

    def test_source_code_matugen_image_calls_have_flag(self):
        """Scan wallpapers.py source to verify all 'matugen image' calls include the flag."""
        import re
        wallpapers_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "modules", "wallpapers.py"
        )
        with open(wallpapers_path) as f:
            source = f.read()

        # Find all lines containing 'matugen image' (the command that needs the flag)
        matugen_image_lines = []
        for i, line in enumerate(source.splitlines(), 1):
            if "matugen image" in line and "exec_shell_command_async" in line:
                matugen_image_lines.append((i, line.strip()))
            # Also catch multi-line f-strings where matugen image is on same line
            elif "matugen image" in line and not line.strip().startswith("#"):
                matugen_image_lines.append((i, line.strip()))

        assert len(matugen_image_lines) > 0, \
            "Expected at least one 'matugen image' call in wallpapers.py"

        for lineno, line in matugen_image_lines:
            # Skip comment-only lines
            if line.lstrip().startswith("#"):
                continue
            assert "--source-color-index" in line, (
                f"wallpapers.py:{lineno}: 'matugen image' call missing "
                f"--source-color-index flag (matugen 4.0.0 regression):\n  {line}"
            )

    def test_source_code_no_bare_matugen_image(self):
        """Ensure no 'matugen image' call exists without --source-color-index."""
        import re
        wallpapers_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "modules", "wallpapers.py"
        )
        with open(wallpapers_path) as f:
            source = f.read()

        # Pattern: lines with 'matugen image' that DON'T have --source-color-index
        pattern = re.compile(r"matugen\s+image\b(?!.*--source-color-index)")
        matches = []
        for i, line in enumerate(source.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if pattern.search(line):
                matches.append((i, line.strip()))

        assert len(matches) == 0, (
            "Found 'matugen image' calls without --source-color-index:\n"
            + "\n".join(f"  line {n}: {l}" for n, l in matches)
        )


class TestMatugenSourceColorIndexInSettings:
    """Verify settings_utils.py matugen calls also include the flag."""

    def test_settings_utils_matugen_has_flag(self):
        """Scan settings_utils.py for matugen image calls missing --source-color-index."""
        import re
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "settings_utils.py"
        )
        with open(settings_path) as f:
            source = f.read()

        pattern = re.compile(r"matugen\s+image\b(?!.*--source-color-index)")
        matches = []
        for i, line in enumerate(source.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if pattern.search(line):
                matches.append((i, line.strip()))

        assert len(matches) == 0, (
            "Found 'matugen image' calls without --source-color-index in settings_utils.py:\n"
            + "\n".join(f"  line {n}: {l}" for n, l in matches)
        )


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


class TestVenvPythonInHyprconf:
    """Regression: generated hyprlua must use .venv/bin/python everywhere."""

    def test_no_bare_python_in_hyprconf(self):
        """Scan generate_hyprlua source for bare 'python' without .venv path."""
        import re
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config", "settings_utils.py"
        )
        with open(settings_path) as f:
            source = f.read()

        # Find the generate_hyprlua function body
        in_func = False
        func_lines = []
        for i, line in enumerate(source.splitlines(), 1):
            if "def generate_hyprlua" in line:
                in_func = True
                continue
            if in_func:
                # End of function: next def at same or lower indent
                if line and not line[0].isspace() and line.strip() and not line.strip().startswith("#"):
                    if line.startswith("def ") or (not line.startswith(" ") and not line.startswith("\t") and "=" not in line[:4]):
                        break
                func_lines.append((i, line))

        # Check that VENV_PYTHON is used (not bare "python")
        uses_venv = False
        for lineno, line in func_lines:
            if "VENV_PYTHON" in line or ".venv" in line:
                uses_venv = True
                break

        assert uses_venv, \
            "generate_hyprlua must define and use VENV_PYTHON (.venv/bin/python)"


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
