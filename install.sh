#!/bin/bash
# Installs or updates Aw-Shell from git into ~/.local/src/aw-shell (override
# with AW_SHELL_DIR), or with --dev runs it from the current repo. Settings
# live in ~/.config/aw-shell; older versions kept the code there too, and this
# moves such an install (see `main.py --migrate`).

set -euo pipefail

REPO_URL="https://github.com/awareness10/Aw-Shell.git"
OLD_DIR="$HOME/.config/aw-shell"
INSTALL_DIR="${AW_SHELL_DIR:-$HOME/.local/src/aw-shell}"
FONT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts"
ZED_FONT_URL="https://github.com/zed-industries/zed-fonts/releases/download/1.2.0/zed-sans-1.2.0.zip"
DEV_MODE=false
PACKAGES=(
  awww-git
  brightnessctl
  cava
  cliphist
  ddcutil
  fabric-cli-git
  bluez-utils
  gobject-introspection
  gpu-screen-recorder
  headsetcontrol
  hypridle
  hyprlock
  hyprpicker
  hyprshot
  hyprsunset
  imagemagick
  libnotify
  matugen-bin
  network-manager-applet
  networkmanager
  nm-connection-editor
  noto-fonts-emoji
  nvtop
  playerctl
  power-profiles-daemon
  swappy
  tesseract
  tesseract-data-eng
  tesseract-data-spa
  tmux
  ttf-nerd-fonts-symbols-mono
  unzip
  upower
  uwsm
  vte3
  webp-pixbuf-loader
  wl-clipboard
)

log() { echo "==> $*"; }

# Older versions kept the code in ~/.config/aw-shell. Move such a clone to
# INSTALL_DIR; --migrate then copies the settings back out. A dev-mode
# symlink is left to --migrate, which replaces just the link.
move_old_clone() {
  local old="${OLD_DIR:?}" new="${INSTALL_DIR:?}"
  if [[ -L "$old" || ! -f "$old/main.py" ]]; then
    return 0
  fi
  if [[ -e "$new" ]]; then
    log "Keeping the old install in $old ($new already exists); --migrate backs it up"
    return 0
  fi
  mkdir -p "$(dirname "$new")"
  mv "$old" "$new"
  log "Moved the old install from $old to $new"
}

ensure_aur_helper() {
  if command -v paru &>/dev/null; then
    aur_helper="paru"
  elif command -v yay &>/dev/null; then
    aur_helper="yay"
  else
    log "Installing yay-bin..."
    local tmpdir
    tmpdir="$(mktemp -d)"
    git clone --depth=1 https://aur.archlinux.org/yay-bin.git "$tmpdir/yay-bin"
    (cd "$tmpdir/yay-bin" && makepkg -si --noconfirm)
    rm -rf "${tmpdir:?}"
    aur_helper="yay"
  fi
}

get_source() {
  if $DEV_MODE; then
    log "Running Aw-Shell from this repository (dev mode): $INSTALL_DIR"
    return 0
  fi
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Updating Aw-Shell in $INSTALL_DIR..."
    git -C "$INSTALL_DIR" pull
  else
    log "Cloning Aw-Shell into $INSTALL_DIR..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
  fi
}

install_packages() {
  log "Installing required packages..."
  $aur_helper -Syy --needed --devel --noconfirm "${PACKAGES[@]}" || true
  log "Installing gray-git..."
  yes | $aur_helper -Syy --needed --devel --noconfirm gray-git || true
}

install_python_deps() {
  if ! command -v uv &>/dev/null; then
    log "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  log "Installing Python dependencies..."
  (cd "$INSTALL_DIR" && uv sync)
}

install_fonts() {
  local zed_dir="$FONT_DIR/zed-sans" zip
  if [[ ! -d "$zed_dir" ]]; then
    log "Installing Zed Sans into $zed_dir..."
    zip="$(mktemp --suffix=.zip)"
    curl -fL -o "$zip" "$ZED_FONT_URL"
    mkdir -p "$zed_dir"
    unzip -o -q "$zip" -d "$zed_dir"
    rm -f "$zip"
  fi
  log "Installing bundled fonts into $FONT_DIR/aw-shell..."
  mkdir -p "$FONT_DIR/aw-shell"
  cp -r "$INSTALL_DIR/assets/fonts/." "$FONT_DIR/aw-shell/"
  fc-cache -f "$FONT_DIR" &>/dev/null || true
}

setup_network() {
  if systemctl is-enabled --quiet iwd 2>/dev/null || systemctl is-active --quiet iwd 2>/dev/null; then
    log "Disabling iwd..."
    sudo systemctl disable --now iwd
  fi
  if ! systemctl is-enabled --quiet NetworkManager 2>/dev/null; then
    log "Enabling NetworkManager..."
    sudo systemctl enable NetworkManager
  fi
  if ! systemctl is-active --quiet NetworkManager 2>/dev/null; then
    log "Starting NetworkManager..."
    sudo systemctl start NetworkManager
  fi
}

start_shell() {
  log "Moving settings to the current layout..."
  "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/main.py" --migrate
  # Keybinds and autostart now point at INSTALL_DIR (aw-shell.lua was rewritten)
  hyprctl reload >/dev/null 2>&1 || true
  log "Starting Aw-Shell..."
  killall aw-shell 2>/dev/null || true
  # Opens the settings window on its own the first time (no config yet)
  uwsm app -- "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/main.py" >/dev/null 2>&1 &
  disown
}

main() {
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "Please do not run this script as root."
    exit 1
  fi
  if [[ "${1:-}" == "--dev" ]]; then
    DEV_MODE=true
    INSTALL_DIR="$PWD"
    if [[ ! -d "$INSTALL_DIR/.git" || ! -f "$INSTALL_DIR/main.py" ]]; then
      echo "Dev mode must be run from inside the Aw-Shell repository."
      exit 1
    fi
  fi

  ensure_aur_helper
  move_old_clone
  get_source
  install_packages
  install_python_deps
  install_fonts
  setup_network
  start_shell
  log "Installation complete. Code: $INSTALL_DIR, settings: $OLD_DIR"
}

# Run unless sourced (tests source it); `curl ... | bash` has no script file,
# so BASH_SOURCE can't tell, but `return` only works when sourced
if ! (return 0 2>/dev/null); then
  main "$@"
fi
