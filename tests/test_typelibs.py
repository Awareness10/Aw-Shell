"""utils/typelibs.py: the Gray library install.sh builds for clone installs
is found by GObject-Introspection."""

import re
from pathlib import Path

from utils.typelibs import GRAY_LIB_DIR, add_private_typelibs

REPO = Path(__file__).resolve().parent.parent


def test_adds_the_private_typelib_folder_first(tmp_path):
    typelibs = tmp_path / ".local" / "lib" / "aw-shell" / "girepository-1.0"
    typelibs.mkdir(parents=True)
    env = {"GI_TYPELIB_PATH": "/usr/lib/aw-shell/lib/girepository-1.0"}
    add_private_typelibs(env, home=tmp_path)
    assert env["GI_TYPELIB_PATH"] == f"{typelibs}:/usr/lib/aw-shell/lib/girepository-1.0"
    add_private_typelibs(env, home=tmp_path)  # idempotent
    assert env["GI_TYPELIB_PATH"].count(str(typelibs)) == 1


def test_without_a_private_build_nothing_changes(tmp_path):
    env = {}
    add_private_typelibs(env, home=tmp_path)
    assert "GI_TYPELIB_PATH" not in env


def test_install_sh_builds_gray_where_the_shell_looks():
    install = (REPO / "install.sh").read_text()
    assert 'GRAY_LIB_DIR="$HOME/.local/lib/aw-shell"' in install
    assert GRAY_LIB_DIR == Path(".local") / "lib" / "aw-shell"


def test_install_sh_builds_the_pinned_gray_commit():
    install = (REPO / "install.sh").read_text()
    pkgbuild = (REPO / "packaging" / "aur" / "PKGBUILD").read_text()
    pinned = re.search(r"^_gray_commit=(\w+)", pkgbuild, re.M).group(1)
    assert f"GRAY_COMMIT={pinned}" in install
    assert "gray-git" not in install  # the broken AUR package


def test_main_adds_it_before_anything_imports_gi():
    """GObject-Introspection reads GI_TYPELIB_PATH once, on first use, and
    importing anything from config/ already uses it."""
    lines = (REPO / "main.py").read_text().splitlines()
    call = next(i for i, line in enumerate(lines) if "add_private_typelibs(" in line)
    first_import = next(i for i, line in enumerate(lines)
                        if re.match(r"\s*(from|import) (fabric|gi|config|modules)\b", line))
    assert call < first_import
