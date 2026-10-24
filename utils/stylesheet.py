"""The shell's stylesheet: the shipped CSS plus the user's colors and overrides.

The code folder can be read-only, so matugen's colors.css and the optional
user.css live in ~/.config/aw-shell/styles and are imported by absolute path.
fabric's compile_css inlines the imports; main.css's own relative imports
resolve against the code folder (pass base_path=APP_DIR).
"""

import config.paths as paths


def build_stylesheet() -> str:
    parts = [
        f'@import url("{paths.colors_css()}");',
        paths.MAIN_CSS.read_text(encoding="utf-8"),
    ]
    if paths.USER_CSS.is_file():
        parts.append(f'@import url("{paths.USER_CSS}");')  # last, so it overrides
    return "\n".join(parts)
