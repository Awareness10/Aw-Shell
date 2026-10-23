"""scripts/screenshot.sh against the real hyprshot, with slurp, grim, hyprctl,
hyprpicker, notify-send and wl-copy replaced by fakes on PATH.

hyprshot exits as soon as the selection closes and captures in the background,
and its exit code is pkill's. These tests pick slowly (over hyprshot's 1 s
check delay) so the script can't rely on hyprshot having finished.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "screenshot.sh"
IMAGE = b"PNGDATA"  # what fake grim writes, in two chunks
SLURP_DELAY = 1.3   # longer than hyprshot's `sleep 1` before it polls slurp

pytestmark = pytest.mark.skipif(
    not (shutil.which("hyprshot") and shutil.which("jq")),
    reason="needs hyprshot and jq",
)

# Fakes use #!/bin/bash, not #!/usr/bin/env bash: hyprshot finds them with
# pgrep slurp / pkill hyprpicker, which match the process name, and env
# would rename them to "bash"
FAKES = {
    "slurp": """#!/bin/bash
cat >/dev/null &  # window mode pipes window boxes on stdin
sleep "$SLURP_DELAY"
date +%s.%N > "$LOG_DIR/slurp_done"
[ -n "$SLURP_CANCEL" ] && { echo "selection cancelled" >&2; exit 1; }
echo "10,10 100x100"
""",
    # Writes the image in two chunks, so a reader that is too early sees a
    # missing or partial file
    "grim": """#!/bin/bash
for out; do :; done
[ "$2" = "10,10 100x100" ] || { echo "invalid geometry" >&2; exit 1; }
sleep 0.2
if [ "$out" = - ]; then exec 3>&1; else exec 3>"$out"; fi
printf 'PNG' >&3
sleep 0.3
printf 'DATA' >&3
""",
    "hyprctl": """#!/bin/bash
case "$*" in
    *monitors*) echo '[{"name":"X","x":0,"y":0,"width":1920,"height":1080,"scale":1,"transform":0,"activeWorkspace":{"id":1}}]' ;;
    *clients*) echo '[{"at":[10,10],"size":[100,100],"title":"t","workspace":{"id":1}}]' ;;
    *) echo '{"id":1}' ;;
esac
""",
    # Freeze overlay; hyprshot pkills it once the selection is done
    "hyprpicker": """#!/bin/bash
for _ in $(seq 300); do sleep 0.1; done
""",
    # Logs: summary, size of the icon file at send time, timestamp
    "notify-send": """#!/bin/bash
summary="" icon=""
while [ $# -gt 0 ]; do
    case "$1" in
        -i) icon=$2; shift ;;
        -a|-A|-t) shift ;;
        *) [ -z "$summary" ] && summary=$1 ;;
    esac
    shift
done
size=$([ -n "$icon" ] && stat -c%s "$icon" 2>/dev/null)
echo "$summary|$size|$(date +%s.%N)" >> "$LOG_DIR/notify"
""",
    "wl-copy": """#!/bin/bash
cat > "$LOG_DIR/clipboard"
""",
}


@pytest.fixture
def run(tmp_path):
    fakes = tmp_path / "bin"
    fakes.mkdir()
    for name, body in FAKES.items():
        (fakes / name).write_text(body)
        (fakes / name).chmod(0o755)
    logs = tmp_path / "logs"
    logs.mkdir()
    save_dir = tmp_path / "shots"

    def _run(mode, cancel=False):
        env = dict(os.environ,
                   PATH=f"{fakes}:{os.environ['PATH']}",
                   LOG_DIR=str(logs),
                   SLURP_DELAY=str(SLURP_DELAY),
                   SLURP_CANCEL="1" if cancel else "")
        subprocess.run(["bash", str(SCRIPT), mode, "", str(save_dir)],
                       env=env, stdin=subprocess.DEVNULL, timeout=30, check=False)
        summary, size, sent_at = (logs / "notify").read_text().strip().split("|")
        clipboard = logs / "clipboard"
        return {
            "summary": summary,
            "icon_size": int(size) if size else None,
            "notify_delay": float(sent_at) - float((logs / "slurp_done").read_text()),
            "files": sorted(save_dir.iterdir()),
            "clipboard": clipboard.read_bytes() if clipboard.exists() else None,
        }

    return _run


@pytest.mark.parametrize("mode", ["w", "s", "p"])
def test_slow_selection_is_saved(run, mode):
    result = run(mode)
    assert result["summary"] == "Screenshot saved"
    assert [f.read_bytes() for f in result["files"]] == [IMAGE]


@pytest.mark.parametrize("mode", ["w", "s", "p"])
def test_clipboard_and_notification_get_the_complete_image(run, mode):
    result = run(mode)
    assert result["clipboard"] == IMAGE
    assert result["icon_size"] == len(IMAGE)


@pytest.mark.parametrize("mode", ["w", "s", "p"])
def test_cancelled_selection_aborts_promptly(run, mode):
    result = run(mode, cancel=True)
    assert result["summary"] == "Screenshot Aborted"
    assert result["files"] == []
    assert result["clipboard"] is None
    # No fixed wait for a file that will never come
    assert result["notify_delay"] < 2.0
