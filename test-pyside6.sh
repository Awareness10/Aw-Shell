#!/usr/bin/env bash
#
# Test the PySide6 shell — kills the running Fabric shell, runs the
# PySide6 version, and restores the original on exit.
#
# Usage:  ./test-pyside6.sh          (runs until you press Ctrl+C or Escape)
#         ./test-pyside6.sh 10       (runs for 10 seconds then restores)
#

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
STABLE_MAIN="$HOME/.config/aw-shell/main.py"
STABLE_PROC="aw-shell"
STABLE_CONF="$HOME/.config/aw-shell/config/hypr/aw-shell.conf"
MSG="$PROJECT_DIR/aw-shell-msg"
TIMEOUT="${1:-0}"

swap_keybinds() {
    echo "==> Swapping keybinds to PySide6 IPC..."
    hyprctl --batch "\
keyword unbind SUPER,D;\
keyword unbind SUPER,W;\
keyword unbind SUPER,S;\
keyword unbind SUPER,TAB;\
keyword unbind SUPER,ESCAPE;\
keyword unbind SUPER,PERIOD;\
keyword unbind SUPER,V;\
keyword unbind SUPER,T;\
keyword unbind SUPER,N;\
keyword unbind SUPER,COMMA;\
keyword unbind SUPER,M;\
keyword unbind SUPER CTRL,B;\
keyword unbind SUPER SHIFT,B;\
keyword bind SUPER,D,exec,$MSG open_notch dashboard;\
keyword bind SUPER,W,exec,$MSG open_notch launcher;\
keyword bind SUPER,S,exec,$MSG open_notch tools;\
keyword bind SUPER,TAB,exec,$MSG open_notch overview;\
keyword bind SUPER,ESCAPE,exec,$MSG open_notch power;\
keyword bind SUPER,PERIOD,exec,$MSG open_notch emoji;\
keyword bind SUPER,V,exec,$MSG open_notch cliphist;\
keyword bind SUPER,T,exec,$MSG open_notch tmux;\
keyword bind SUPER,N,exec,$MSG open_notch kanban;\
keyword bind SUPER,COMMA,exec,$MSG open_notch wallpapers;\
keyword bind SUPER,M,exec,$MSG open_notch mixer;\
keyword bind SUPER CTRL,B,exec,$MSG toggle_bar;\
keyword bind SUPER SHIFT,B,exec,$MSG reload_css" > /dev/null 2>&1
    echo "    Done."
}

restore_keybinds() {
    echo "==> Restoring original keybinds..."
    hyprctl keyword source "$STABLE_CONF" > /dev/null 2>&1
    echo "    Done."
}

restore_shell() {
    echo ""
    echo "==> Restoring stable shell..."
    # Kill any leftover PySide6 test processes we spawned
    kill "$PYSIDE_PID" 2>/dev/null && wait "$PYSIDE_PID" 2>/dev/null || true

    # Restore keybinds to fabric-cli
    restore_keybinds

    # Restart the stable Fabric shell
    cd "$HOME/.config/aw-shell"
    nohup python "$STABLE_MAIN" > /tmp/aw-shell-restore.log 2>&1 &
    RESTORED_PID=$!
    echo "==> Stable shell restarted (PID $RESTORED_PID)"
    echo "    Log: /tmp/aw-shell-restore.log"
}

# Trap all exits — Ctrl+C, errors, normal exit
trap restore_shell EXIT

# --- 1. Kill the running stable shell ---
echo "==> Stopping stable shell ($STABLE_PROC)..."
if pkill -x "$STABLE_PROC" 2>/dev/null; then
    # Wait for it to actually die
    sleep 0.5
    # Force kill if still alive
    pkill -9 -x "$STABLE_PROC" 2>/dev/null || true
    sleep 0.3
    echo "    Stopped."
else
    echo "    No running $STABLE_PROC found (continuing anyway)."
fi

# --- 2. Launch PySide6 shell ---
echo "==> Starting PySide6 test shell from $PROJECT_DIR..."
echo "    Ctrl+C to stop and restore."

cd "$PROJECT_DIR"
export QT_WAYLAND_SHELL_INTEGRATION=layer-shell
python main_pyside6.py &
PYSIDE_PID=$!

echo "    PySide6 shell PID: $PYSIDE_PID"

# --- 3. Swap keybinds ---
sleep 0.5  # let PySide6 shell start and bind IPC socket
swap_keybinds

# --- 4. Wait ---
if [ "$TIMEOUT" -gt 0 ] 2>/dev/null; then
    echo "    Auto-restoring in ${TIMEOUT}s..."
    sleep "$TIMEOUT"
else
    # Wait for the PySide6 process to exit (Ctrl+C triggers the trap)
    wait "$PYSIDE_PID" 2>/dev/null || true
fi
