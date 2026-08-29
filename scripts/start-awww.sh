#!/usr/bin/env sh

# awww-daemon can be spawned before Hyprland's own Wayland socket is
# ready to accept new client connections during early boot, which makes
# it panic with "failed to connect to socket: ConnectionRefused" and
# abort instead of retrying. That leaves no wallpaper daemon running,
# so wire in a retry loop here and apply ~/.current.wall (the file the
# rest of Aw-Shell treats as the selected wallpaper) once it's up.
# `awww restore` is not used here since its own cache can be stale
# relative to ~/.current.wall.

for _ in $(seq 1 15); do
    if awww query >/dev/null 2>&1; then
        break
    fi
    awww-daemon >/dev/null 2>&1 &
    sleep 0.5
done

awww query >/dev/null 2>&1 && awww img "$HOME/.current.wall" >/dev/null 2>&1
