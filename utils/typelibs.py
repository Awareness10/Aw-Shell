"""Where GObject-Introspection finds the Gray library built for clone installs.

The AUR's gray-git can't install, so install.sh builds Gray (the system tray
library) into ~/.local/lib/aw-shell; the AUR package bundles its own and its
launcher sets the path. GI reads GI_TYPELIB_PATH once, the first time anything
uses it (importing config/ already does), so main.py calls this first.

No imports from the shell or gi here, on purpose.
"""

import os
from pathlib import Path

GRAY_LIB_DIR = Path(".local") / "lib" / "aw-shell"  # relative to HOME; install.sh too


def add_private_typelibs(environ=os.environ, home: Path | None = None) -> None:
    typelibs = (home or Path.home()) / GRAY_LIB_DIR / "girepository-1.0"
    if not typelibs.is_dir():
        return
    current = [p for p in environ.get("GI_TYPELIB_PATH", "").split(os.pathsep) if p]
    if str(typelibs) not in current:
        environ["GI_TYPELIB_PATH"] = os.pathsep.join([str(typelibs), *current])
