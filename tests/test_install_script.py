"""install.sh: moving an old ~/.config/aw-shell clone, and being sourceable
without running the installer. Sourced with a temporary HOME."""

import subprocess
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
