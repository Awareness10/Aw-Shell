#!/bin/bash
# Toggle gpu-screen-recorder: stops a running recording, otherwise starts one

if [ -z "$XDG_VIDEOS_DIR" ]; then
  XDG_VIDEOS_DIR="$HOME/Videos"
fi

SAVE_DIR="$XDG_VIDEOS_DIR/Recordings"
LOG_FILE="${XDG_CACHE_HOME:-$HOME/.cache}/aw-shell/screenrecord.log"
mkdir -p "$SAVE_DIR" "$(dirname "$LOG_FILE")"

# Match the recorder as the command itself. `-x` can't: the kernel truncates
# process names to 15 chars. A bare `-f` would match any command line that
# merely mentions the recorder
RECORDER='^([^ ]*/)?gpu-screen-recorder( |$)'

if pgrep -f "$RECORDER" >/dev/null; then
  pkill -SIGINT -f "$RECORDER"

  # SIGINT makes the recorder finalize the file; wait for it to exit
  for _ in $(seq 50); do
    pgrep -f "$RECORDER" >/dev/null || break
    sleep 0.1
  done

  LAST_VIDEO=$(ls -t "$SAVE_DIR"/*.mp4 2>/dev/null | head -n 1)

  ACTION=$(notify-send -a "Aw-Shell" "⬜ Recording stopped" \
    -A "view=View" -A "open=Open folder")

  if [ "$ACTION" = "view" ] && [ -n "$LAST_VIDEO" ]; then
    xdg-open "$LAST_VIDEO"
  elif [ "$ACTION" = "open" ]; then
    xdg-open "$SAVE_DIR"
  fi
  exit 0
fi

# Direct capture needs gsr to find the monitor's DRM card, which fails on
# some multi-GPU setups; the desktop portal works everywhere
if gpu-screen-recorder --list-capture-options 2>/dev/null | grep -qvx "portal"; then
  CAPTURE=(-w screen)
else
  CAPTURE=(-w portal -restore-portal-session yes)
fi

OUTPUT_FILE="$SAVE_DIR/$(date +%Y-%m-%d-%H-%M-%S).mp4"

gpu-screen-recorder "${CAPTURE[@]}" -q ultra -a default_output -ac opus -cr full -f 60 \
  -o "$OUTPUT_FILE" >"$LOG_FILE" 2>&1 &
RECORDER_PID=$!

# Announce only once the file exists; the portal may first ask for a source
STARTED=0
while kill -0 "$RECORDER_PID" 2>/dev/null; do
  if [ -s "$OUTPUT_FILE" ]; then
    notify-send -a "Aw-Shell" "🔴 Recording started"
    STARTED=1
    break
  fi
  sleep 0.2
done

wait "$RECORDER_PID"
STATUS=$?

if [ "$STARTED" = 0 ]; then
  ERROR=$(grep -m1 "error" "$LOG_FILE")
  notify-send -a "Aw-Shell" -u critical "Recording failed" \
    "${ERROR:-gpu-screen-recorder exited with status $STATUS}"
  rm -f "$OUTPUT_FILE"
fi
