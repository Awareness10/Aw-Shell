"""scripts/hyprpicker.sh: the notification's preview icon is a private temp
file in $XDG_RUNTIME_DIR, not a fixed name in the shared /tmp."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "hyprpicker.sh"

FAKES = {
    "hyprpicker": '#!/bin/bash\necho "255 0 0"\n',
    "wl-paste": '#!/bin/bash\necho -n "$WL_PASTE"\n',
    "wl-copy": "#!/bin/bash\ncat >/dev/null\n",
    # Writes the icon file (last argument) and logs the color it was given
    "magick": '#!/bin/bash\nfor out; do :; done\necho PNG > "$out"\necho "$3" >> "$LOG/magick"\n',
    # Logs the -i argument and whether that file exists while notifying
    "notify-send": """#!/bin/bash
while [ $# -gt 0 ]; do
    if [ "$1" = -i ]; then icon="$2"; shift; fi
    shift
done
echo "$icon $([ -f "$icon" ] && echo exists)" >> "$LOG/notify"
""",
}


@pytest.fixture
def env(tmp_path):
    bin_dir, log, run = tmp_path / "bin", tmp_path / "log", tmp_path / "run"
    for d in (bin_dir, log, run):
        d.mkdir()
    for name, body in FAKES.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    return {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "XDG_RUNTIME_DIR": str(run),
        "LOG": str(log),
        "HOME": str(tmp_path),
    }


@pytest.mark.parametrize("mode, paste, color", [
    ("-rgb", "255, 0, 0", "xc:rgb(255, 0, 0)"),
    ("-hex", "#ff0000", "xc:#ff0000"),
    ("-hsv", "0, 100%, 100%", "xc:hsv(0, 100%, 100%)"),
])
def test_icon_is_a_private_temp_file(env, mode, paste, color):
    env["WL_PASTE"] = paste
    result = subprocess.run(["bash", str(SCRIPT), mode], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    icon, state = (Path(env["LOG"]) / "notify").read_text().split()
    assert Path(icon).parent == Path(env["XDG_RUNTIME_DIR"])
    assert icon.endswith(".png") and icon != "/tmp/color.png"
    assert state == "exists"  # still there while the notification is sent
    assert not Path(icon).exists()  # removed afterwards
    assert (Path(env["LOG"]) / "magick").read_text().strip() == color
