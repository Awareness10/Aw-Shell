#!/bin/sh
# /usr/bin/aw-shell: runs the packaged shell with the system Python and the
# bundled fabric, glaze and Gray (system tray library). AW_SHELL_LAUNCH tells the shell how it was started,
# for restarts and the generated Hyprland config (see config/paths.py).
export AW_SHELL_LAUNCH=/usr/bin/aw-shell
export PYTHONPATH="/usr/share/aw-shell/vendor${PYTHONPATH:+:$PYTHONPATH}"
export GI_TYPELIB_PATH="/usr/lib/aw-shell/lib/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
exec python /usr/share/aw-shell/main.py "$@"
