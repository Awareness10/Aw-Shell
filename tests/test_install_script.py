"""install.sh: moving an old ~/.config/aw-shell clone, being sourceable
without running the installer, and its steps on a fresh system. Sourced with
a temporary HOME and stub commands."""

import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "install.sh"


def _run(home: Path, snippet: str, **env) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}"; {snippet}'],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin", **env},
        capture_output=True, text=True,
    )


@pytest.fixture
def home(tmp_path):
    (tmp_path / ".config").mkdir()
    return tmp_path


def _clone(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "main.py").write_text("# shell")
    (path / "config.json").write_text("{}")
    return path


def test_sourcing_does_not_run_the_installer(home):
    result = _run(home, 'echo "dir=$INSTALL_DIR"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"dir={home}/.local/src/aw-shell"


def test_moves_an_old_clone(home):
    _clone(home / ".config" / "aw-shell")
    result = _run(home, "move_old_clone")
    assert result.returncode == 0, result.stderr
    assert not (home / ".config" / "aw-shell").exists()
    assert (home / ".local" / "src" / "aw-shell" / "config.json").exists()


def test_leaves_a_dev_symlink_to_migrate(home):
    repo = _clone(home / "repo")
    (home / ".config" / "aw-shell").symlink_to(repo)
    assert _run(home, "move_old_clone").returncode == 0
    assert (home / ".config" / "aw-shell").is_symlink()
    assert not (home / ".local" / "src" / "aw-shell").exists()


def test_never_overwrites_an_existing_install(home):
    _clone(home / ".config" / "aw-shell")
    existing = _clone(home / ".local" / "src" / "aw-shell")
    (existing / "marker").write_text("keep")
    result = _run(home, "move_old_clone")
    assert result.returncode == 0
    assert "Keeping the old install" in result.stdout
    assert (home / ".config" / "aw-shell" / "main.py").exists()
    assert (existing / "marker").read_text() == "keep"


def test_custom_install_dir(home):
    _clone(home / ".config" / "aw-shell")
    target = home / "elsewhere" / "aw"
    assert _run(home, "move_old_clone", AW_SHELL_DIR=str(target)).returncode == 0
    assert (target / "main.py").exists()


def test_nothing_to_move(home):
    (home / ".config" / "aw-shell").mkdir()  # already the new layout
    assert _run(home, "move_old_clone").returncode == 0
    assert (home / ".config" / "aw-shell").is_dir()
    assert not (home / ".local").exists()


def test_piped_into_bash_runs_main(home):
    """`curl ... | bash` must still install. A copy with main's call swapped
    for an echo, so nothing is installed here."""
    script = SCRIPT.read_text()
    assert script.count('\n  main "$@"\n') == 1
    piped = script.replace('\n  main "$@"\n', "\n  echo MAIN-RAN\n")
    result = subprocess.run(["bash"], input=piped, capture_output=True, text=True,
                            env={"HOME": str(home), "PATH": "/usr/bin:/bin"})
    assert result.stdout.strip() == "MAIN-RAN", result.stderr


def _fake_bin(home: Path, **commands: str) -> str:
    """PATH with stub commands (name -> bash body) in front of the system's."""
    bin_dir = home / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in commands.items():
        stub = bin_dir / name
        stub.write_text(f"#!/bin/bash\n{body}\n")
        stub.chmod(0o755)
    return f"{bin_dir}:/usr/bin:/bin"


@pytest.mark.parametrize("installed", [True, False])
def test_installs_base_devel_and_git_when_missing(home, installed):
    calls = home / "calls"
    path = _fake_bin(
        home,
        pacman=f'[[ "$1" == -T ]] && exit {0 if installed else 127}; exit 1',
        sudo=f'echo "$*" >> "{calls}"',
    )
    result = _run(home, "install_build_tools", PATH=path)
    assert result.returncode == 0, result.stderr
    if installed:
        assert not calls.exists()  # no sudo prompt when there's nothing to do
    else:
        assert calls.read_text() == "pacman -S --needed --noconfirm base-devel git\n"


def test_installs_the_cvc_typelib(home):
    """fabric.audio raises CvcImportError without it, so the shell never
    starts (tests/test_pkgbuild.py has the same for the AUR package)."""
    result = _run(home, 'printf "%s\\n" "${PACKAGES[@]}"')
    assert "cinnamon-desktop" in result.stdout.split()


def test_first_start_output_goes_to_a_log(home):
    """A shell that crashes on start must leave its traceback somewhere."""
    install = home / "inst"
    venv_bin = install / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("#!/bin/bash\nexit 0\n")
    (venv_bin / "python").chmod(0o755)
    path = _fake_bin(
        home, hyprctl="exit 0", killall="exit 1",
        uwsm='echo "CvcImportError: Cvc is not installed" >&2; exit 1',
    )
    result = _run(home, "start_shell", PATH=path, AW_SHELL_DIR=str(install))
    assert result.returncode == 0, result.stderr
    log = home / ".local" / "state" / "aw-shell" / "shell.log"
    for _ in range(50):  # the shell runs in the background (disowned)
        if "CvcImportError" in log.read_text():
            break
        time.sleep(0.05)
    assert "CvcImportError" in log.read_text()


@pytest.mark.parametrize("running", [True, False])
def test_shell_running(home, running):
    path = _fake_bin(home, pgrep=f"exit {0 if running else 1}")
    result = _run(home, "shell_running 0", PATH=path)
    assert (result.returncode == 0) is running


def test_warns_about_packages_that_did_not_install(home):
    # Installed: cava, and matugen standing in for matugen-bin
    path = _fake_bin(home, pacman='[[ "$2" == cava || "$2" == matugen ]]')
    result = _run(home, "PACKAGES=(cava matugen-bin awww-git tmux); aur_helper=yay; check_packages",
                  PATH=path)
    assert result.returncode == 0, result.stderr
    assert "didn't install: awww-git tmux\n" in result.stderr


def test_quiet_when_every_package_installed(home):
    path = _fake_bin(home, pacman="exit 0")
    result = _run(home, "aur_helper=yay; check_packages", PATH=path)
    assert result.returncode == 0
    assert result.stderr == ""
