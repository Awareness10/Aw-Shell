#!/bin/bash
# Removes an Aw-Shell installed by install.sh (AUR users: pacman -R aw-shell).
# Always removes the code, the cache and the line in your Hyprland config;
# asks before deleting your settings, kanban board, pins and history.

set -uo pipefail

INSTALL_DIR="${AW_SHELL_DIR:-$HOME/.local/src/aw-shell}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
USER_DIR="$CONFIG_HOME/aw-shell"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/aw-shell"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/aw-shell"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/aw-shell"
FONT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/aw-shell"
HYPR_LUA="$CONFIG_HOME/hypr/hyprland.lua"
HYPR_CONF="$CONFIG_HOME/hypr/hyprland.conf"

# No answer (e.g. no terminal) counts as no
ask() {
  local reply=""
  read -r -p "$1 [y/N] " reply || true
  [[ "$reply" == [yY] ]]
}

# Removes a folder, or only the link if it is a symlink (never its target)
remove_path() {
  local path="${1:?}"
  if [[ -L "$path" ]]; then
    rm -f "$path"
  elif [[ -e "$path" ]]; then
    rm -rf "${path:?}"
  else
    return 0
  fi
  echo "Removed $path"
}

# Edits in place (through a symlink, keeping it a symlink)
_filter_file() {
  local file="$1" tmp
  tmp="$(mktemp)"
  if "${@:2}" "$file" > "$tmp"; then
    cat "$tmp" > "$file"
  fi
  rm -f "$tmp"
}

remove_hyprland_lines() {
  if [[ -f "$HYPR_LUA" ]]; then
    _filter_file "$HYPR_LUA" awk '!/^[[:space:]]*dofile\(".*\/aw-shell\/config\/hypr\/aw-shell\.lua"\)[[:space:]]*$/'
  fi
  # hyprland.conf from before Hyprland's Lua config: "# Aw-Shell" + source line
  if [[ -f "$HYPR_CONF" ]]; then
    _filter_file "$HYPR_CONF" awk '
      /^# Aw-Shell$/ { pending = $0; next }
      pending != "" && /source[[:space:]]*=.*\/aw-shell\/config\/hypr\/aw-shell\.conf/ { pending = ""; next }
      pending != "" { print pending; pending = "" }
      { print }
      END { if (pending != "") print pending }'
  fi
}

main() {
  echo "This removes Aw-Shell's code ($INSTALL_DIR), cache and Hyprland config line."
  if ! ask "Continue?"; then
    echo "Aborted."
    exit 1
  fi

  killall aw-shell 2>/dev/null || true
  # Only an install made by install.sh; a dev repo elsewhere is left alone
  if [[ -f "$INSTALL_DIR/main.py" ]]; then
    remove_path "$INSTALL_DIR"
  fi
  remove_path "$CACHE_DIR"
  remove_path "$FONT_DIR"
  fc-cache -f &>/dev/null || true
  remove_hyprland_lines

  if ask "Also delete your settings in $USER_DIR?"; then
    remove_path "$USER_DIR"
  fi
  if ask "Also delete your kanban board and pins in $DATA_DIR?"; then
    remove_path "$DATA_DIR"
  fi
  if ask "Also delete your calculator history in $STATE_DIR?"; then
    remove_path "$STATE_DIR"
  fi
  echo "Aw-Shell removed."
}

# Run unless sourced (tests source it)
if ! (return 0 2>/dev/null); then
  main "$@"
fi
