"""`aw-shell --migrate`: move an old install to the current layout.

Old installs kept the code and the user's files together in
~/.config/aw-shell: a git clone, or (dev mode) a symlink to one. Now the code
lives elsewhere (/usr/share/aw-shell, ~/.local/src/aw-shell, ...) and
~/.config/aw-shell holds only the user's files. Nothing is deleted or
overwritten: an old clone is kept as a backup, since users may have edited it.

The shell never moves the folder it runs from; install.sh moves an old clone
to ~/.local/src/aw-shell first, then runs --migrate from there.
"""

import shutil
from datetime import date
from pathlib import Path

from . import paths
from .legacy import move_legacy_files
from .settings_constants import APP_NAME, APP_NAME_CAP
from .settings_utils import write_generated_config


class MigrationError(Exception):
    pass


def _free_name(path: Path) -> Path:
    candidate, n = path, 2
    while candidate.exists() or candidate.is_symlink():
        candidate = path.with_name(f"{path.name}-{n}")
        n += 1
    return candidate


def _copy_user_files(src: Path, dest: Path) -> list[str]:
    lines = []
    for rel in paths.USER_FILES:
        source, target = src / rel, dest / rel
        if source.is_file() and not target.exists():
            paths.ensure_dir(target.parent)
            shutil.copy2(source, target)
            lines.append(f"Copied {rel} from {src}")
    return lines


def migrate(user_dir: Path, app_dir: Path, today: date | None = None) -> list[str]:
    """Give user_dir its own folder with the user's files; returns what was done."""
    today = today or date.today()
    if user_dir.is_symlink():  # dev mode: a link to the clone
        source = user_dir.resolve()
        user_dir.unlink()  # the link only; the clone stays as it is
        paths.ensure_dir(user_dir)
        return [f"Replaced the link {user_dir} -> {source} with a folder",
                *_copy_user_files(source, user_dir)]
    if (user_dir / "main.py").exists():  # an old clone
        if user_dir.resolve() == app_dir.resolve():
            raise MigrationError(
                f"{APP_NAME_CAP} is running from the old install at {user_dir}, so it can't "
                "move it. Run install.sh, which moves it, or move it yourself:\n"
                f"  mv {user_dir} ~/.local/src/{APP_NAME}\n"
                f"  cd ~/.local/src/{APP_NAME} && .venv/bin/python main.py --migrate"
            )
        backup = _free_name(user_dir.with_name(f"{user_dir.name}.bak-{today.isoformat()}"))
        user_dir.rename(backup)
        paths.ensure_dir(user_dir)
        return [f"Kept the old install as {backup}", *_copy_user_files(backup, user_dir)]
    has_settings = (user_dir / "config" / "config.json").exists()
    if not has_settings and (app_dir / "config" / "config.json").exists():
        # A clone that install.sh already moved out of ~/.config
        return _copy_user_files(app_dir, user_dir)
    return []


def old_install_notice(user_dir: Path, app_dir: Path) -> str | None:
    """A message for users who installed a package but still have an old
    clone in ~/.config/aw-shell; None otherwise (dev mode included)."""
    if (user_dir / "main.py").exists() and user_dir.resolve() != app_dir.resolve():
        return (f"An old {APP_NAME_CAP} install is still in {user_dir}. "
                f"Run '{APP_NAME} --migrate' to keep your settings and move it aside.")
    return None


def main() -> int:
    try:
        lines = migrate(paths.USER_DIR, paths.APP_DIR)
    except MigrationError as e:
        print(e)
        return 1
    lines += [f"Moved {old} to {new}" for old, new in move_legacy_files()]
    if paths.CONFIG_FILE.exists():
        write_generated_config()
        lines.append(f"Rewrote {APP_NAME}.lua and matugen's config for the new paths")
    if not lines:
        print("Nothing to migrate.")
        return 0
    print("\n".join(lines))
    print(f"Run 'hyprctl reload' and restart {APP_NAME_CAP} to use the new folders.")
    return 0
