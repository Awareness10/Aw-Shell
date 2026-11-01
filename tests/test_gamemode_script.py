"""scripts/gamemode.sh: game mode must turn on with both legacy (keyword) and
Lua (eval) configs, whatever wording Hyprland uses to reject `keyword`."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gamemode.sh"

# Fake hyprctl: animations are on, `--batch` prints $BATCH_REPLY, `eval`
# prints $EVAL_REPLY; every call is logged
HYPRCTL = """#!/bin/bash
echo "$1" >> "$LOG/hyprctl"
case "$1" in
    getoption) printf 'bool: true\\nset: true\\n' ;;
    --batch)   printf '%b' "$BATCH_REPLY" ;;
    eval)      printf '%s' "$EVAL_REPLY" ;;
esac
"""


@pytest.fixture
def env(tmp_path):
    bin_dir, log = tmp_path / "bin", tmp_path / "log"
    bin_dir.mkdir()
    log.mkdir()
    (bin_dir / "hyprctl").write_text(HYPRCTL)
    (bin_dir / "hyprctl").chmod(0o755)
    return {"PATH": f"{bin_dir}:/usr/bin:/bin", "LOG": str(log), "EVAL_REPLY": "ok"}


def run(env):
    result = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
    calls = (Path(env["LOG"]) / "hyprctl").read_text().split()
    return result, calls


@pytest.mark.parametrize("reply", [
    "unknown request\n\n\nunknown request\n",  # Hyprland 0.57 Lua config
    "can't work with non-legacy parsers\n",   # earlier Lua config releases
    "",                                       # no reply at all
])
def test_lua_config_falls_back_to_eval(env, reply):
    """Regression: only the "non-legacy" wording triggered the eval path, so on
    0.57 ("unknown request") the button silently did nothing."""
    env["BATCH_REPLY"] = reply
    result, calls = run(env)
    assert result.returncode == 0, result.stderr
    assert calls == ["getoption", "--batch", "eval"]


@pytest.mark.parametrize("reply", ["ok\n" * 7, "\nok\n\nok\nok\n", "ok\n"])
def test_legacy_config_stops_after_keyword(env, reply):
    env["BATCH_REPLY"] = reply
    result, calls = run(env)
    assert result.returncode == 0, result.stderr
    assert calls == ["getoption", "--batch"]


def test_eval_error_is_reported(env):
    env["BATCH_REPLY"] = "unknown request\n"
    env["EVAL_REPLY"] = "error: unknown config key 'nope'"
    result, _ = run(env)
    assert result.returncode == 1
    assert "unknown config key" in result.stderr
