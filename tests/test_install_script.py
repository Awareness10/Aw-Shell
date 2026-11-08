"""install.sh: moving an old ~/.config/aw-shell clone, being sourceable
without running the installer, and its steps on a fresh system. Sourced with
a temporary HOME and stub commands."""

import shlex
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


def test_installs_python_gobject_for_powerprofilesctl(home):
    """Only optional for power-profiles-daemon, but powerprofilesctl fails
    without it and the bar then finds no power profiles."""
    result = _run(home, 'printf "%s\\n" "${PACKAGES[@]}"')
    assert "python-gobject" in result.stdout.split()


def test_installs_a_font_for_the_player_kaomoji(home):
    """The idle player shows ¯\\_(ツ)_/¯, and noto-fonts has no katakana."""
    result = _run(home, 'printf "%s\\n" "${PACKAGES[@]}"')
    assert "adobe-source-han-sans-jp-fonts" in result.stdout.split()


def test_readme_lists_every_package(home):
    """The README's manual installation lists what install.sh installs."""
    import re

    readme = (SCRIPT.parent / "README.md").read_text()
    section = readme[readme.index("2. Install system dependencies"):readme.index("3. Clone")]
    listed = {re.sub(r"-(git|bin)$", "", name.lower())
              for name in re.findall(r"`([\w.+-]+)`|\[([\w-]+)\]\(http", section) for name in name if name}
    result = _run(home, 'printf "%s\\n" "${PACKAGES[@]}"')
    packages = {re.sub(r"-(git|bin)$", "", p) for p in result.stdout.split()} - {"uv"}  # its own step
    assert packages - listed == set()


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
    for _ in range(50):  # the shell runs in the background (its own session)
        if "CvcImportError" in log.read_text():
            break
        time.sleep(0.05)
    assert "CvcImportError" in log.read_text()


def test_shell_starts_in_its_own_session(home):
    """The updater runs install.sh in a terminal; closing it hangs up the
    terminal's session, which would kill a shell started in it."""
    install = home / "inst"
    (install / ".venv" / "bin").mkdir(parents=True)
    (install / ".venv" / "bin" / "python").write_text("#!/bin/bash\nexit 0\n")
    (install / ".venv" / "bin" / "python").chmod(0o755)
    session = home / "session"
    path = _fake_bin(
        home, hyprctl="exit 0", killall="exit 1",
        uwsm=f'echo "$$ $(ps -o sid= -p $$)" > "{session}"',
    )
    result = _run(home, "start_shell", PATH=path, AW_SHELL_DIR=str(install))
    assert result.returncode == 0, result.stderr
    for _ in range(50):
        if session.exists() and session.read_text().strip():
            break
        time.sleep(0.05)
    pid, sid = session.read_text().split()
    assert pid == sid  # a session leader: no controlling terminal to lose


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


@pytest.mark.parametrize("ok", [True, False])
def test_warns_when_the_aur_helper_fails(home, ok):
    """A failed run (e.g. a wrong sudo password) can leave every package
    installed but none upgraded, which check_packages can't see. Warned at
    once and again at the end, as later steps scroll the first one away."""
    _fake_bin(home, yay=f"exit {0 if ok else 3}", pacman="exit 0", foot="exit 0")
    (home / "bin" / "bash").symlink_to("/bin/bash")
    result = _run(home, "aur_helper=yay; install_packages; echo later steps; warn_if_packages_failed",
                  PATH=str(home / "bin"))
    assert result.returncode == 0, result.stderr  # the rest still installs
    if ok:
        assert result.stderr == ""
    else:
        assert "yay failed (exit code 3)" in result.stderr
        assert result.stderr.count("WARNING") == 2


def test_packages_install_as_part_of_a_full_upgrade(home):
    """-Syy alone (no -u) is a partial upgrade, which can break shared
    libraries; --devel with -u would rebuild every -git package."""
    calls = home / "calls"
    _fake_bin(home, yay=f'echo "$*" >> "{calls}"', pacman="exit 0", foot="exit 0")
    (home / "bin" / "bash").symlink_to("/bin/bash")
    result = _run(home, "aur_helper=yay; install_packages", PATH=str(home / "bin"))
    assert result.returncode == 0, result.stderr
    assert calls.read_text().split()[:3] == ["-Syu", "--needed", "--noconfirm"]


def test_terminal_list_matches_the_shell():
    from config.terminal import TERMINALS
    result = _run(Path("/nonexistent"), 'printf "%s\\n" "${TERMINALS[@]}"')
    assert result.stdout.split() == list(TERMINALS)


@pytest.mark.parametrize("stubs, env, kitty", [
    ({}, {}, True),  # no terminal at all
    ({"foot": "exit 0"}, {}, False),
    ({"wezterm": "exit 0"}, {"TERMINAL": "wezterm"}, False),
    ({"st": "exit 0"}, {"TERMINAL": "st"}, False),  # $TERMINAL needn't be one we know
    ({}, {"TERMINAL": "st"}, True),  # $TERMINAL that isn't installed
    ({"xdg-terminal-exec": "exit 0"}, {}, False),
    ({"xdg-terminal-exec": "exit 1"}, {}, True),  # installed, but finds no terminal
])
def test_installs_kitty_only_without_a_terminal(home, stubs, env, kitty):
    calls = home / "calls"
    _fake_bin(home, yay=f'echo "$*" >> "{calls}"', pacman="exit 0", **stubs)
    (home / "bin" / "bash").symlink_to("/bin/bash")
    # Only the stubs: this machine's own terminals must not count
    result = _run(home, "aur_helper=yay; install_packages", PATH=str(home / "bin"), **env)
    assert result.returncode == 0, result.stderr
    packages = calls.read_text().split()
    assert ("kitty" in packages) is kitty
    assert "cinnamon-desktop" in packages


# ── Shell colors (matuwrap), opt-in ──

def _shell_colors_stubs(home: Path, cargo=False, wrp=False, fail="") -> Path:
    """Stubs that log their calls, on an isolated PATH. `uv tool install`
    makes wrp available in the folder `uv tool dir --bin` names."""
    calls = home / "calls"
    tool_bin = home / "tool-bin"
    tool_bin.mkdir()
    log = f'echo "${{0##*/}} $*" >> "{calls}"'
    wrp_stub = f"#!/bin/bash\n{log}\n" + ("exit 1\n" if fail == "wrp" else "")
    (tool_bin / "wrp").write_text(wrp_stub)
    (tool_bin / "wrp").chmod(0o755)
    stubs = {
        "sudo": log + ("; exit 1" if fail == "sudo" else ""),
        "uv": log + f'; [[ "$*" == "tool dir --bin" ]] && echo "{tool_bin}"; true',
    }
    if cargo:
        stubs["cargo"] = "exit 0"
    if wrp:
        stubs["wrp"] = wrp_stub.removeprefix("#!/bin/bash\n")
    _fake_bin(home, **stubs)
    (home / "bin" / "bash").symlink_to("/bin/bash")
    return calls


def _calls(calls: Path) -> list[str]:
    return calls.read_text().splitlines() if calls.exists() else []


def _no_tty(home: Path, snippet: str, **env) -> subprocess.CompletedProcess:
    """Like _run, also without a controlling terminal (like the in-app updater)."""
    return subprocess.run(
        ["/bin/bash", "-c", f'source "{SCRIPT}"; {snippet}'],
        env={"HOME": str(home), "PATH": str(home / "bin"), **env},
        capture_output=True, text=True, stdin=subprocess.DEVNULL, start_new_session=True,
    )


STEPS = "parse_args {args}; ask_shell_colors; setup_shell_colors; echo SHELL_COLORS=$SHELL_COLORS"


def test_no_shell_colors_without_the_flag_or_a_terminal(home):
    calls = _shell_colors_stubs(home)
    result = _no_tty(home, STEPS.format(args=""))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SHELL_COLORS=no"  # never asked
    assert "[y/N]" not in result.stdout + result.stderr
    assert _calls(calls) == []


def test_no_shell_colors_flag_never_asks(home):
    """The in-app updater runs install.sh in a terminal, where it would ask."""
    result = _run(home, "parse_args --no-shell-colors; can_prompt() { return 0; }; "
                        "ask_shell_colors; echo SHELL_COLORS=$SHELL_COLORS")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SHELL_COLORS=no"
    assert "[y/N]" not in result.stdout + result.stderr


def test_shell_colors_flag_runs_the_steps_in_order(home):
    calls = _shell_colors_stubs(home)
    result = _no_tty(home, STEPS.format(args="--shell-colors"))
    assert result.returncode == 0, result.stderr
    assert _calls(calls) == [
        "sudo pacman -S --needed --noconfirm fastfetch rust",
        "uv tool install git+https://github.com/Awareness10/matuwrap",
        "uv tool dir --bin",
        "wrp install bash",
    ]
    assert "source ~/.bashrc" in result.stdout
    assert all(hint in result.stdout for hint in ("MW_FF_LOGO", "MW_FF_IMAGE", "ff-toggle"))


def test_shell_colors_keep_an_existing_wrp(home):
    calls = _shell_colors_stubs(home, wrp=True)
    assert _no_tty(home, STEPS.format(args="--shell-colors")).returncode == 0
    assert not any(call.startswith("uv ") for call in _calls(calls))
    assert _calls(calls)[-1] == "wrp install bash"


def test_shell_colors_use_an_existing_cargo(home):
    calls = _shell_colors_stubs(home, cargo=True)
    assert _no_tty(home, STEPS.format(args="--shell-colors")).returncode == 0
    assert _calls(calls)[0] == "sudo pacman -S --needed --noconfirm fastfetch"


@pytest.mark.parametrize("fail", ["sudo", "wrp"])
def test_failed_shell_colors_only_warn(home, fail):
    calls = _shell_colors_stubs(home, fail=fail)
    result = _no_tty(home, STEPS.format(args="--shell-colors") + "; echo STILL-RUNNING")
    assert result.returncode == 0
    assert "STILL-RUNNING" in result.stdout
    assert "shell colors weren't set up" in result.stderr
    if fail == "sudo":
        assert _calls(calls) == ["sudo pacman -S --needed --noconfirm fastfetch rust"]


def _with_tty(home: Path, answer: str, snippet: str) -> str:
    """Runs snippet with a terminal (script(1) makes one) answering on it;
    the snippet's stdin is /dev/null, like the script piped into bash."""
    inner = f'source "{SCRIPT}"; {snippet}'
    result = subprocess.run(
        ["script", "-qec", f"bash -c {shlex.quote(inner)} </dev/null", "/dev/null"],
        input=answer + "\n", capture_output=True, text=True,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    return result.stdout.replace("\r", "")


@pytest.mark.parametrize("answer, choice", [("y", "yes"), ("yes", "yes"), ("n", "no"), ("", "no")])
def test_asks_on_the_terminal_defaulting_to_no(home, answer, choice):
    out = _with_tty(home, answer, "ask_shell_colors; echo SHELL_COLORS=$SHELL_COLORS")
    assert "[y/N]" in out
    assert f"SHELL_COLORS={choice}" in out


def test_not_asked_once_set_up(home):
    script = home / ".config" / "matuwrap" / "scripts" / "matuwrap"
    script.parent.mkdir(parents=True)
    script.write_text("# matuwrap")
    out = _with_tty(home, "y", "ask_shell_colors; echo SHELL_COLORS=$SHELL_COLORS")
    assert "[y/N]" not in out
    assert "SHELL_COLORS=no" in out


@pytest.mark.parametrize("args", [["--dev", "--shell-colors"], ["--shell-colors", "--dev"]])
def test_options_combine(home, args):
    result = _run(home, f"parse_args {' '.join(args)}; echo $DEV_MODE $SHELL_COLORS")
    assert result.stdout.split() == ["true", "yes"]


def test_unknown_option(home):
    result = _run(home, "parse_args --colors")
    assert result.returncode == 1
    assert "Unknown option: --colors" in result.stderr
