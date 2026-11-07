"""The default terminal_command: the user's own terminal, or kitty.

The shell runs `<terminal_command> <program> <args...>`, so each command ends
in whatever makes its terminal run the rest of the line. Checked against each
terminal's --help, man page or docs:
- kitty, foot: run trailing arguments and ignore -e (kept for kitty, the
  long-standing default)
- alacritty, ghostty, konsole: -e takes the rest of the line
- gnome-terminal, ptyxis: `--` (gnome-terminal's -e/-x are deprecated)
- wezterm: `start --`
- xfce4-terminal: -x (its -e takes the command as one string)
- xdg-terminal-exec: trailing arguments, run in the terminal chosen in
  xdg-terminals.list (or the first one it finds)

install.sh lists the same terminals: it installs kitty when none is there.
"""

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

FALLBACK = "kitty -e"

# Tried in this order when neither $TERMINAL nor xdg-terminal-exec gives one
TERMINALS = {
    "kitty": "kitty -e",
    "foot": "foot",
    "alacritty": "alacritty -e",
    "ghostty": "ghostty -e",
    "wezterm": "wezterm start --",
    "konsole": "konsole -e",
    "gnome-terminal": "gnome-terminal --",
    "ptyxis": "ptyxis --",
    "xfce4-terminal": "xfce4-terminal -x",
}


def _xdg_terminal_exec_works(which: Callable[[str], str | None]) -> bool:
    """xdg-terminal-exec is installed and finds a terminal to run."""
    if not which("xdg-terminal-exec"):
        return False
    try:
        return subprocess.run(
            ["xdg-terminal-exec", "--print-id"], capture_output=True, timeout=5,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def detect_terminal_command(
    environ: Mapping[str, str] = os.environ,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    """The user's terminal, in this order: $TERMINAL (an explicit choice),
    xdg-terminal-exec (the freedesktop default terminal), the first installed
    of TERMINALS, and FALLBACK when there is none."""
    terminal = environ.get("TERMINAL", "").strip()
    if terminal and which(terminal):
        known = TERMINALS.get(Path(terminal).name)
        if known:  # keep the user's spelling, e.g. a full path
            return " ".join([terminal, *known.split()[1:]])
        return f"{terminal} -e"  # xterm's convention, which most terminals follow
    if _xdg_terminal_exec_works(which):
        return "xdg-terminal-exec"
    for name, command in TERMINALS.items():
        if which(name):
            return command
    return FALLBACK


@cache
def default_terminal_command() -> str:
    """detect_terminal_command(), once per process."""
    return detect_terminal_command()
