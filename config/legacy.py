"""Files that older versions kept elsewhere, moved to their current place.

main.py runs move_legacy_files() at startup, before any widget reads them, so
users keep their kanban board, pins and history after an update.
"""

import shutil
from pathlib import Path

from loguru import logger

from . import paths

LEGACY_FILES: list[tuple[Path, Path]] = [
    (Path.home() / ".kanban.json", paths.KANBAN_FILE),
    (Path.home() / ".pins.json", paths.PINS_FILE),
    (paths.CACHE_DIR / "calc.json", paths.CALC_HISTORY),
    (paths.CACHE_DIR / "conversion.json", paths.CONVERSION_HISTORY),
    # In the shared /tmp before; the cached images it lists stay valid until reboot
    (Path("/tmp") / paths.APP_NAME / "notifications" / "notification_history.json",
     paths.NOTIFICATION_HISTORY),
]


def move_legacy_files(moves: list[tuple[Path, Path]] | None = None) -> list[tuple[Path, Path]]:
    """Move each old file to its new place unless something is already there.

    Never overwrites and never raises: startup must not fail because of this.
    Returns the moves that happened.
    """
    moved = []
    for old, new in LEGACY_FILES if moves is None else moves:
        if not old.exists() or new.exists():
            continue
        try:
            paths.ensure_dir(new.parent)
            shutil.move(old, new)
        except OSError as e:
            logger.warning(f"Could not move {old} to {new}: {e}")
            continue
        logger.info(f"Moved {old} to {new}")
        moved.append((old, new))
    return moved
