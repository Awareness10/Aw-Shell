"""uninstall.sh: removes code, cache and the Hyprland line; asks before user
data; never deletes through a symlink. Runs with a temporary HOME."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "uninstall.sh"
DOFILE = 'dofile("{home}/.config/aw-shell/config/hypr/aw-shell.lua")'


@pytest.fixture
def home(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("killall", "fc-cache"):  # never touch the real session
        (bin_dir / name).write_text("#!/bin/sh\nexit 0\n")
        (bin_dir / name).chmod(0o755)
    for d in (".local/src/aw-shell", ".cache/aw-shell", ".config/aw-shell",
              ".local/share/aw-shell", ".local/state/aw-shell",
              ".local/share/fonts/aw-shell", ".local/lib/aw-shell/girepository-1.0",
              ".config/hypr"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / ".local/src/aw-shell/main.py").write_text("# shell")
    (tmp_path / ".config/aw-shell/marker").write_text("settings")
    (tmp_path / ".config/hypr/hyprland.lua").write_text(
        f'hl.monitor("x")\n{DOFILE.format(home=tmp_path)}\nhl.bind("SUPER + Q")\n')
    return tmp_path


def _uninstall(home: Path, answers: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)], input=answers, capture_output=True, text=True,
        env={"HOME": str(home), "PATH": f"{home / 'bin'}:/usr/bin:/bin"},
    )


def test_keeps_user_data_unless_asked(home):
    result = _uninstall(home, "y\nn\nn\nn\n")
    assert result.returncode == 0, result.stderr
    assert not (home / ".local/src/aw-shell").exists()
    assert not (home / ".cache/aw-shell").exists()
    assert not (home / ".local/share/fonts/aw-shell").exists()
    assert not (home / ".local/lib/aw-shell").exists()  # Gray built by install.sh
    assert (home / ".config/aw-shell/marker").exists()
    assert (home / ".local/share/aw-shell").exists()
    assert (home / ".local/state/aw-shell").exists()


def test_removes_everything_when_confirmed(home):
    assert _uninstall(home, "y\ny\ny\ny\n").returncode == 0
    for d in (".config/aw-shell", ".local/share/aw-shell", ".local/state/aw-shell"):
        assert not (home / d).exists(), d


def test_aborts_without_confirmation(home):
    result = _uninstall(home, "n\n")
    assert result.returncode == 1
    assert (home / ".local/src/aw-shell/main.py").exists()
    assert (home / ".cache/aw-shell").exists()


def test_no_terminal_answers_count_as_no(home):
    assert _uninstall(home, "").returncode == 1


def test_removes_only_aw_shells_hyprland_line(home):
    _uninstall(home, "y\nn\nn\nn\n")
    assert (home / ".config/hypr/hyprland.lua").read_text() == \
        'hl.monitor("x")\nhl.bind("SUPER + Q")\n'


def test_symlinked_hyprland_config_stays_a_symlink(home):
    dotfiles = home / "dotfiles"
    dotfiles.mkdir()
    real = dotfiles / "hyprland.lua"
    real.write_text(DOFILE.format(home=home) + "\n")
    link = home / ".config/hypr/hyprland.lua"
    link.unlink()
    link.symlink_to(real)
    _uninstall(home, "y\nn\nn\nn\n")
    assert link.is_symlink()
    assert real.read_text() == ""  # its only line was aw-shell's


def test_legacy_hyprland_conf_block(home):
    conf = home / ".config/hypr/hyprland.conf"
    conf.write_text("a = 1\n\n# Aw-Shell\nsource = ~/.config/aw-shell/config/hypr/aw-shell.conf\n"
                    "# Aw-Shell is great\nb = 2\n")
    _uninstall(home, "y\nn\nn\nn\n")
    assert conf.read_text() == "a = 1\n\n# Aw-Shell is great\nb = 2\n"


def test_settings_symlink_removes_the_link_not_the_repo(home):
    repo = home / "projects" / "Aw-Shell"
    repo.mkdir(parents=True)
    (repo / "main.py").write_text("# dev repo")
    user_dir = home / ".config/aw-shell"
    (user_dir / "marker").unlink()
    user_dir.rmdir()
    user_dir.symlink_to(repo)
    _uninstall(home, "y\ny\nn\nn\n")
    assert not user_dir.exists() and not user_dir.is_symlink()
    assert (repo / "main.py").exists()


def test_install_dir_without_main_py_is_not_deleted(home):
    (home / ".local/src/aw-shell/main.py").unlink()  # not an install.sh clone
    _uninstall(home, "y\nn\nn\nn\n")
    assert (home / ".local/src/aw-shell").exists()
