"""scripts/screenrecord.sh records the monitor it was started from: `-w screen`
is "the first monitor found", which recorded the other screen."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "screenrecord.sh"

# Fake recorder: lists $CAPTURE_OPTIONS, otherwise logs its arguments and
# writes the -o file, like a recording that starts and is then stopped
RECORDER = """#!/bin/bash
if [ "$1" = "--list-capture-options" ]; then printf '%b' "$CAPTURE_OPTIONS"; exit 0; fi
echo "$@" > "$LOG/recorder"
while [ $# -gt 0 ]; do [ "$1" = "-o" ] && echo video > "$2"; shift; done
"""

HYPRCTL = """#!/bin/bash
echo '[{"name": "HDMI-A-1", "focused": false}, {"name": "DP-3", "focused": true}]'
"""

STUBS = {
    "gpu-screen-recorder": RECORDER,
    "hyprctl": HYPRCTL,
    "pgrep": "#!/bin/sh\nexit 1\n",  # not recording yet (never sees the real recorder)
    "pkill": "#!/bin/sh\nexit 1\n",
    "notify-send": "#!/bin/sh\n",
}


@pytest.fixture
def env(tmp_path):
    bin_dir, log = tmp_path / "bin", tmp_path / "log"
    bin_dir.mkdir()
    log.mkdir()
    for name, body in STUBS.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    return {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "LOG": str(log),
        "HOME": str(tmp_path),
        "XDG_VIDEOS_DIR": str(tmp_path / "Videos"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "CAPTURE_OPTIONS": "HDMI-A-1|1920x1080\\nDP-3|3440x1440\\nregion\\nportal\\n",
    }


def recorded_target(env, *args):
    result = subprocess.run(["bash", str(SCRIPT), *args], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    recorder_args = (Path(env["LOG"]) / "recorder").read_text().split()
    return recorder_args[recorder_args.index("-w") + 1]


def test_records_the_monitor_it_was_started_from(env):
    assert recorded_target(env, "HDMI-A-1") == "HDMI-A-1"


def test_defaults_to_the_focused_monitor(env):
    assert recorded_target(env) == "DP-3"


def test_unknown_monitor_falls_back_to_the_focused_one(env):
    assert recorded_target(env, "DP-9") == "DP-3"


def test_portal_only_setups_still_use_the_portal(env):
    env["CAPTURE_OPTIONS"] = "portal\\n"
    assert recorded_target(env, "DP-3") == "portal"
