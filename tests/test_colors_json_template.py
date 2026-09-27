"""The matugen template aw-shell renders to config/colors.json for other tools."""

import json
import re
from pathlib import Path

TEMPLATE = Path(__file__).parent.parent / "config" / "matugen" / "templates" / "colors.json"

# Colors matuwrap's theme reads (matuwrap/core/colors.py Colors)
MATUWRAP_KEYS = {
    "primary", "on_primary", "primary_container", "on_primary_container",
    "secondary", "on_secondary", "secondary_container", "tertiary", "error",
    "surface", "on_surface", "surface_container", "outline", "outline_variant",
}


def _render(text: str) -> dict:
    return json.loads(re.sub(r"\{\{[^}]+\}\}", "#000000", text))


def test_renders_to_flat_json_of_hex_colors():
    colors = _render(TEMPLATE.read_text())
    assert all(isinstance(v, str) and v.startswith("#") for v in colors.values())


def test_has_every_color_matuwrap_uses():
    assert MATUWRAP_KEYS <= set(_render(TEMPLATE.read_text()))


def test_each_key_uses_its_own_matugen_color():
    for key, placeholder in json.loads(TEMPLATE.read_text()).items():
        assert placeholder == f"{{{{colors.{key}.default.hex}}}}"
