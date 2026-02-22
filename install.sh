#!/bin/bash

set -e
set -u
set -o pipefail

REPO_URL="https://github.com/awareness10/Aw-Shell.git"
INSTALL_DIR="$HOME/.config/aw-shell"
PACKAGES=(
  awww-git
  brightnessctl
  cava
  cliphist
  ddcutil
  fabric-cli-git
  gnome-bluetooth-3.0
  gobject-introspection
  gpu-screen-recorder
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

if [ "$(id -u)" -eq 0 ]; then
  echo "Please do not run this script as root."
  exit 1
fi

DEV_MODE=false

if [[ "${1:-}" == "--dev" ]]; then
  DEV_MODE=true
fi

aur_helper="yay"

if command -v paru &>/dev/null; then
  aur_helper="paru"
elif ! command -v yay &>/dev/null; then
  echo "Installing yay-bin..."
  tmpdir=$(mktemp -d)
  git clone --depth=1 https://aur.archlinux.org/yay-bin.git "$tmpdir/yay-bin"
  (cd "$tmpdir/yay-bin" && makepkg -si --noconfirm)
  rm -rf "$tmpdir"
fi

# --- SOURCE ACQUISITION ----------------------------------------------

if $DEV_MODE; then
  echo "Installing Aw-Shell in DEV mode..."

  # ensure we're inside a git repo
  if [ ! -d ".git" ]; then
    echo "Dev mode must be run from inside the Aw-Shell repository."
    exit 1
  fi

  # replace existing install safely
  if [ -e "$INSTALL_DIR" ] || [ -L "$INSTALL_DIR" ]; then
    echo "Removing existing installation..."
    rm -rf "$INSTALL_DIR"
  fi

  echo "Linking project directory:"
  echo "  $INSTALL_DIR -> $PWD"

  ln -s "$PWD" "$INSTALL_DIR"

else
  if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating Aw-Shell..."
    git -C "$INSTALL_DIR" pull
  else
    echo "Cloning Aw-Shell..."
    rm -rf "$INSTALL_DIR"
    git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
  fi
fi

echo "Installing required packages..."
$aur_helper -Syy --needed --devel --noconfirm "${PACKAGES[@]}" || true

echo "Installing gray-git..."
yes | $aur_helper -Syy --needed --devel --noconfirm gray-git || true

echo "Installing uv..."
if ! command -v uv &>/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "Installing Python dependencies..."
(cd "$INSTALL_DIR" && uv sync)

echo "Installing required fonts..."

FONT_URL="https://github.com/zed-industries/zed-fonts/releases/download/1.2.0/zed-sans-1.2.0.zip"
FONT_DIR="$HOME/.fonts/zed-sans"
TEMP_ZIP="/tmp/zed-sans-1.2.0.zip"

if [ ! -d "$FONT_DIR" ]; then
  echo "Downloading fonts from $FONT_URL..."
  curl -L -o "$TEMP_ZIP" "$FONT_URL"

  echo "Extracting fonts to $FONT_DIR..."
  mkdir -p "$FONT_DIR"
  unzip -o "$TEMP_ZIP" -d "$FONT_DIR"

  echo "Cleaning up..."
  rm "$TEMP_ZIP"
else
  echo "Fonts are already installed. Skipping download and extraction."
fi

echo "Configuring network services..."

if systemctl is-enabled --quiet iwd 2>/dev/null || systemctl is-active --quiet iwd 2>/dev/null; then
  echo "Disabling iwd..."
  sudo systemctl disable --now iwd
else
  echo "iwd is already disabled."
fi

if ! systemctl is-enabled --quiet NetworkManager 2>/dev/null; then
  echo "Enabling NetworkManager..."
  sudo systemctl enable NetworkManager
else
  echo "NetworkManager is already enabled."
fi

if ! systemctl is-active --quiet NetworkManager 2>/dev/null; then
  echo "Starting NetworkManager..."
  sudo systemctl start NetworkManager
else
  echo "NetworkManager is already running."
fi

if [ ! -d "$HOME/.fonts/tabler-icons" ]; then
  echo "Copying local fonts to $HOME/.fonts/tabler-icons..."
  mkdir -p "$HOME/.fonts/tabler-icons"
  cp -r "$INSTALL_DIR/assets/fonts/"* "$HOME/.fonts"
else
  echo "Local fonts are already installed. Skipping copy."
fi

(cd "$INSTALL_DIR" && uv run python config/config.py)
echo "Starting Aw-Shell..."
killall aw-shell 2>/dev/null || true
uwsm app -- "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/main.py" >/dev/null 2>&1 &
disown

echo "Installation complete."
