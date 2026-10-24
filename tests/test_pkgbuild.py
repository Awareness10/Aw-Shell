"""packaging/aur/PKGBUILD stays in sync with the code: pinned commits match
uv.lock, and every Python dependency and GTK typelib has its Arch package."""

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
AUR = REPO / "packaging" / "aur"

# pyproject dependency -> Arch package, or why it isn't one
PYTHON_PACKAGES = {
    "dbus-python": "python-dbus",
    "ijson": "python-ijson",
    "loguru": "python-loguru",
    "numpy": "python-numpy",
    "pillow": "python-pillow",
    "psutil": "python-psutil",
    "pycairo": "python-cairo",
    "pygobject": "python-gobject",
    "pyside6": "pyside6",
    "pywayland": "python-pywayland",
    "requests": "python-requests",
    "setproctitle": "python-setproctitle",
    "toml": "python-toml",
    "watchdog": "python-watchdog",
    "fabric": "bundled",  # the Awareness10 fork, see the PKGBUILD
    "glaze": "bundled",  # not packaged for Arch
    "pyopengl": "unused",  # listed in pyproject, but nothing imports OpenGL
}

# GI namespace -> Arch package providing its typelib
TYPELIBS = {
    "Gtk": "gtk3",
    "Gdk": "gtk3",
    "GdkPixbuf": "gdk-pixbuf2",
    "GioUnix": "glib2",
    "GtkLayerShell": "gtk-layer-shell",
    "NM": "libnm",
    "Playerctl": "playerctl",
    "Gray": "gray-git",
    "Cvc": "cinnamon-desktop",  # fabric.audio
}


def _pkgbuild(expr: str) -> str:
    return subprocess.run(
        ["bash", "-c", f'source PKGBUILD && printf "%s\\n" {expr}'],
        cwd=AUR, capture_output=True, text=True, check=True,
    ).stdout


@pytest.fixture(scope="module")
def depends() -> set[str]:
    return set(_pkgbuild('"${depends[@]}"').split())


def _locked_commit(name: str) -> str:
    lock = tomllib.loads((REPO / "uv.lock").read_text())
    package = next(p for p in lock["package"] if p["name"] == name)
    return package["source"]["git"].rsplit("#", 1)[1]


@pytest.mark.parametrize("name", ["fabric", "glaze"])
def test_bundled_commits_match_uv_lock(name):
    assert _pkgbuild(f'"$_{name}_commit"').strip() == _locked_commit(name)


def test_every_python_dependency_has_an_arch_package(depends):
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    for requirement in pyproject["project"]["dependencies"]:
        name = re.split(r"[<>=!~ ;\[]", requirement, maxsplit=1)[0].lower()
        assert name in PYTHON_PACKAGES, f"{name}: add it to PYTHON_PACKAGES and the PKGBUILD"
        package = PYTHON_PACKAGES[name]
        if package not in ("bundled", "unused"):
            assert package in depends, f"{name} needs {package} in depends"
    assert "python-click" in depends  # fabric's own dependency


def test_every_typelib_the_shell_loads_has_its_package(depends):
    namespaces = set()
    for folder in ("config", "modules", "services", "utils", "widgets"):
        for path in (REPO / folder).rglob("*.py"):
            namespaces |= set(re.findall(r"require_version\(['\"](\w+)['\"]", path.read_text()))
    assert {"Gtk", "GtkLayerShell", "NM", "Gray"} <= namespaces  # the scan works
    assert "cinnamon-desktop" in depends  # Cvc, loaded by fabric.audio (not scanned)
    for namespace in namespaces:
        assert namespace in TYPELIBS, f"{namespace}: add its package to TYPELIBS and the PKGBUILD"
        assert TYPELIBS[namespace] in depends, namespace


def test_launcher_runs_the_bundled_libraries():
    launcher = (AUR / "aw-shell.sh").read_text()
    assert "export AW_SHELL_LAUNCH=/usr/bin/aw-shell" in launcher
    assert "/usr/share/aw-shell/vendor" in launcher
    assert "exec python /usr/share/aw-shell/main.py" in launcher


def test_does_not_ship_development_scripts():
    pkgbuild = (AUR / "PKGBUILD").read_text()
    for script in (REPO / "scripts").iterdir():
        if script.name.startswith(("test-", "aur-")):
            assert f"$app/scripts/{script.name}" in pkgbuild, script.name
