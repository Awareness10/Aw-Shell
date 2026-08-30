#!/usr/bin/env sh

# awww-daemon can be spawned before Hyprland's own Wayland socket is ready,
# which makes it panic and abort instead of retrying - so we retry the spawn
# here. That alone isn't enough though: this script itself is forked once,
# early, straight off Hyprland's own process at boot, and at that point
# WAYLAND_DISPLAY is present in the inherited environment but set to an
# EMPTY string (not merely unset) - confirmed via coredumpctl on the actual
# crashing process. An empty (present) value skips Rust's "var absent ->
# default to wayland-0" fallback entirely, so every retry inherited via
# fork keeps reusing that same broken empty value forever, no matter how
# many times we loop - looping alone never fixes it since the env is
# captured once at this script's own launch. So each attempt below derives
# WAYLAND_DISPLAY itself from the live socket file in XDG_RUNTIME_DIR
# instead of trusting the inherited value, and applies ~/.current.wall
# (the file the rest of Aw-Shell treats as the selected wallpaper) once
# it's up. `awww restore` is not used since its own cache can be stale
# relative to ~/.current.wall.

runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
daemon_pid=""

# awww's own CLI derives its control-socket path from WAYLAND_DISPLAY too,
# so the readiness check below needs the corrected value exported into this
# script's own environment, not just passed to the daemon spawn. Also only
# spawn a new attempt once the previous one has actually died - firing a
# fresh awww-daemon every iteration regardless of whether the last one is
# still alive lets two instances race for the same compositor resource,
# which gets one of them killed with "Connection reset by peer" instead of
# the ConnectionRefused this loop is meant to survive.
for _ in $(seq 1 15); do
    # -name 'wayland-[0-9]*' would also match awww-daemon's own control
    # socket (wayland-1-awww-daemon.sock), so match the basename exactly.
    display_socket=$(find "$runtime_dir" -maxdepth 1 -regextype posix-extended -regex '.*/wayland-[0-9]+' -type s 2>/dev/null | head -n1)
    if [ -n "$display_socket" ]; then
        export WAYLAND_DISPLAY=$(basename "$display_socket")
    fi
    if awww query >/dev/null 2>&1; then
        break
    fi
    if [ -z "$daemon_pid" ] || ! kill -0 "$daemon_pid" 2>/dev/null; then
        awww-daemon >/dev/null 2>&1 &
        daemon_pid=$!
    fi
    sleep 0.5
done

awww query >/dev/null 2>&1 && awww img "$HOME/.current.wall" >/dev/null 2>&1
