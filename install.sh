#!/bin/bash
# Installs or updates Aw-Shell from git into ~/.local/src/aw-shell (override
# with AW_SHELL_DIR), or with --dev runs it from the current repo. Settings
# live in ~/.config/aw-shell; older versions kept the code there too, and this
# moves such an install (see `main.py --migrate`).
#
# --shell-colors also colors bash's prompt and fastfetch with Aw-Shell's
# palette (matuwrap; edits ~/.bashrc). Run from a terminal without it, the
# script asks, defaulting to no; --no-shell-colors never asks (the in-app
# updater). Piped: curl ... | bash -s -- --shell-colors

set -euo pipefail

REPO_URL="https://github.com/awareness10/Aw-Shell.git"
OLD_DIR="$HOME/.config/aw-shell"
INSTALL_DIR="${AW_SHELL_DIR:-$HOME/.local/src/aw-shell}"
FONT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts"
# Gray, fabric's system tray library: the AUR package for it can't install, so it
# is built here, privately (utils/typelibs.py points GObject-Introspection at
# it). Same commit as packaging/aur/PKGBUILD and tests_gtk/Dockerfile.
GRAY_COMMIT=d5a8452c39b074ef6da25be95305a22203cf230e
GRAY_LIB_DIR="$HOME/.local/lib/aw-shell"
# The first start's output, to show why it failed
SHELL_LOG="${XDG_STATE_HOME:-$HOME/.local/state}/aw-shell/shell.log"
DEV_MODE=false
# yes, no, or ask (only with a terminal to answer on)
SHELL_COLORS=ask
# Why installing packages failed, for warn_if_packages_failed
PACKAGES_FAILED=""
MATUWRAP_URL="https://github.com/Awareness10/matuwrap"
MATUWRAP_SCRIPT="$HOME/.config/matuwrap/scripts/matuwrap"
# Terminals Aw-Shell knows how to run commands in (config/terminal.py); with
# none of them, nor $TERMINAL or xdg-terminal-exec, kitty is installed
TERMINALS=(kitty foot alacritty ghostty wezterm konsole gnome-terminal ptyxis xfce4-terminal)
PACKAGES=(
  adobe-source-han-sans-jp-fonts  # the player's ¯\_(ツ)_/¯: noto-fonts has no katakana
  awww-git
  brightnessctl
  cava
  cinnamon-desktop  # Cvc typelib for fabric.audio; the shell won't start without it
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
  jq
  libdbusmenu-gtk3
  libnotify
  matugen-bin
  meson
  network-manager-applet
  networkmanager
  nm-connection-editor
  noto-fonts-emoji
  nvtop
  playerctl
  power-profiles-daemon
  python-gobject  # powerprofilesctl (the power mode switcher) needs it; optional for the daemon
  swappy
  tesseract
  tesseract-data-eng
  tesseract-data-spa
  tmux
  ttf-nerd-fonts-symbols-mono
  upower
  uv
  vala
  uwsm
  webp-pixbuf-loader
  wl-clipboard
  xdg-desktop-portal-gtk  # file picker (Pins); GTK apps in the shell's colors
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

# A minimal Arch install has neither, but makepkg (yay-bin, AUR packages) and
# get_source need them
install_build_tools() {
  if pacman -T base-devel git >/dev/null; then
    return 0
  fi
  log "Installing base-devel and git..."
  sudo pacman -S --needed --noconfirm base-devel git
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

# The shell runs the user's terminal (config/terminal.py finds it the same way)
has_terminal() {
  if [[ -n "${TERMINAL:-}" ]] && command -v "$TERMINAL" &>/dev/null; then
    return 0
  fi
  if command -v xdg-terminal-exec &>/dev/null && xdg-terminal-exec --print-id &>/dev/null; then
    return 0
  fi
  local terminal
  for terminal in "${TERMINALS[@]}"; do
    command -v "$terminal" &>/dev/null && return 0
  done
  return 1
}

install_packages() {
  if ! has_terminal; then
    log "No terminal found; kitty will be installed"
    PACKAGES+=(kitty)
  fi
  log "Upgrading the system and installing required packages..."
  # -Syu: refreshing the package lists without upgrading (-Syy) is a partial
  # upgrade, which can break shared libraries. One failed package shouldn't stop the rest; check_packages lists missing
  # ones, but a failed run (e.g. a wrong sudo password) can also leave them
  # installed and just not upgraded
  local status=0
  $aur_helper -Syu --needed --noconfirm "${PACKAGES[@]}" || status=$?
  if (( status )); then
    PACKAGES_FAILED="$aur_helper failed (exit code $status)"
    echo "WARNING: $PACKAGES_FAILED: packages may be missing or not upgraded; see its output above." >&2
  fi
  check_packages
}

# Repeats install_packages' warning at the end, as later steps scroll it away
warn_if_packages_failed() {
  if [[ -n "$PACKAGES_FAILED" ]]; then
    echo "WARNING: $PACKAGES_FAILED earlier, so packages may be missing or not upgraded. Scroll up for why, then run the update again." >&2
  fi
}

# Warns instead of stopping: most packages are for a single feature, and a
# missing one the shell needs shows up when it starts. The plain package
# counts for an AUR -git/-bin one (e.g. matugen for matugen-bin)
check_packages() {
  local pkg missing=()
  for pkg in "${PACKAGES[@]}"; do
    local plain="${pkg%-git}"
    plain="${plain%-bin}"
    if ! pacman -Q "$pkg" &>/dev/null && ! pacman -Q "$plain" &>/dev/null; then
      missing+=("$pkg")
    fi
  done
  if (( ${#missing[@]} )); then
    echo "WARNING: these packages didn't install: ${missing[*]}" >&2
    echo "Install them by hand (e.g. $aur_helper -S ${missing[*]}); see the output above for why." >&2
  fi
}

build_gray() {
  local stamp="$GRAY_LIB_DIR/.gray-commit"
  if [[ -f "$GRAY_LIB_DIR/girepository-1.0/Gray-0.1.typelib" && "$(cat "$stamp" 2>/dev/null)" == "$GRAY_COMMIT" ]]; then
    log "Gray is up to date in $GRAY_LIB_DIR"
    return 0
  fi
  log "Building Gray into $GRAY_LIB_DIR..."
  local tmp
  tmp="$(mktemp -d)"
  curl -fsSL "https://github.com/Fabric-Development/gray/archive/$GRAY_COMMIT.tar.gz" | tar xz -C "$tmp"
  # The typelib records the library's full path, so no LD_LIBRARY_PATH is needed
  meson setup --prefix="$HOME/.local" --libdir=lib/aw-shell --buildtype=plain \
    "$tmp/gray-$GRAY_COMMIT" "$tmp/build" >/dev/null
  meson compile -C "$tmp/build" >/dev/null
  meson install -C "$tmp/build" --destdir "$tmp/root" >/dev/null
  # Only the library and its typelib, not headers or pkg-config files
  mkdir -p "$GRAY_LIB_DIR"
  cp -a "$tmp/root$GRAY_LIB_DIR/libgray.so"* "$GRAY_LIB_DIR/"
  rm -rf "${GRAY_LIB_DIR:?}/girepository-1.0"
  cp -a "$tmp/root$GRAY_LIB_DIR/girepository-1.0" "$GRAY_LIB_DIR/"
  echo "$GRAY_COMMIT" > "$stamp"
  rm -rf "${tmp:?}"
}

install_python_deps() {
  # uv comes with the packages; this is for when its install failed
  if ! command -v uv &>/dev/null; then
    log "Installing uv from astral.sh..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  log "Installing Python dependencies..."
  (cd "$INSTALL_DIR" && uv sync)
}

install_fonts() {
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
  mkdir -p "$(dirname "$SHELL_LOG")"
  # Opens the settings window on its own the first time (no config yet). In
  # its own session: run from a terminal (the updater opens one), the shell
  # would otherwise die when that terminal closes
  setsid -f uwsm app -- "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/main.py" \
    >"$SHELL_LOG" 2>&1 </dev/null
}

# Whether the shell is still up a few seconds after starting: it is called
# aw-shell once its imports have loaded, and runs main.py until then
shell_running() {
  sleep "${1:-5}"
  pgrep -x aw-shell >/dev/null || pgrep -f -- "$INSTALL_DIR/main.py" >/dev/null
}

parse_args() {
  local arg
  for arg in "$@"; do
    case "$arg" in
      --dev) DEV_MODE=true ;;
      --shell-colors) SHELL_COLORS=yes ;;
      --no-shell-colors) SHELL_COLORS=no ;;  # never ask (the in-app updater)
      *)
        echo "Unknown option: $arg (options: --dev, --shell-colors, --no-shell-colors)" >&2
        exit 1
        ;;
    esac
  done
}

# Someone is there to answer: output goes to a terminal and /dev/tty opens
# (the in-app updater passes --no-shell-colors). `curl ... | bash` reads the script from
# stdin, so the answer has to come from /dev/tty
can_prompt() {
  [[ -t 1 ]] && { : </dev/tty; } 2>/dev/null
}

# Asked once, up front, so the rest can run unattended. No answer means no;
# not asked again once matuwrap's shell script is installed
ask_shell_colors() {
  [[ "$SHELL_COLORS" == ask ]] || return 0
  SHELL_COLORS=no
  if [[ -e "$MATUWRAP_SCRIPT" ]] || ! can_prompt; then
    return 0
  fi
  local reply=""
  printf "Color bash's prompt and fastfetch with Aw-Shell's palette? This edits ~/.bashrc and builds matuwrap with Rust. [y/N] " >/dev/tty
  read -r reply </dev/tty || true
  if [[ "$reply" == [yY]* ]]; then
    SHELL_COLORS=yes
  fi
}

# Steps for setup_shell_colors; returns at the first that fails
install_shell_colors() {
  local packages=(fastfetch)
  # matuwrap has a Rust module; rustup users already have cargo
  command -v cargo &>/dev/null || packages+=(rust)
  sudo pacman -S --needed --noconfirm "${packages[@]}" || return 1
  # Never replace an existing install (e.g. a development one)
  if ! command -v wrp &>/dev/null; then
    log "Installing matuwrap..."
    uv tool install "git+$MATUWRAP_URL" || return 1
    local bin
    bin="$(uv tool dir --bin)" || return 1
    export PATH="$bin:$PATH"
  fi
  # Writes matuwrap's shell script and sources it from ~/.bashrc (backed up);
  # a second run changes nothing
  wrp install bash || return 1
}

setup_shell_colors() {
  [[ "$SHELL_COLORS" == yes ]] || return 0
  log "Setting up shell colors (matuwrap)..."
  if ! install_shell_colors; then
    echo "WARNING: shell colors weren't set up (see above); Aw-Shell itself is fine. Retry with --shell-colors" >&2
    return 0
  fi
  log "Shell colors are set up; reload with: source ~/.bashrc"
  log "Custom fastfetch logo: export MW_FF_LOGO=<file.txt> or MW_FF_IMAGE=<image> in ~/.bashrc,"
  log "  before matuwrap's source line; ff-toggle switches between text and image"
}

main() {
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "Please do not run this script as root."
    exit 1
  fi
  parse_args "$@"
  if $DEV_MODE; then
    INSTALL_DIR="$PWD"
    if [[ ! -d "$INSTALL_DIR/.git" || ! -f "$INSTALL_DIR/main.py" ]]; then
      echo "Dev mode must be run from inside the Aw-Shell repository."
      exit 1
    fi
  fi
  ask_shell_colors

  install_build_tools
  ensure_aur_helper
  move_old_clone
  get_source
  install_packages
  build_gray
  install_python_deps
  install_fonts
  setup_network
  setup_shell_colors
  start_shell
  warn_if_packages_failed
  if ! shell_running; then
    # Not an error exit: the code is installed, and the in-app updater would
    # call the whole update failed
    echo "WARNING: Aw-Shell stopped right after starting. The end of $SHELL_LOG:" >&2
    tail -n 20 "$SHELL_LOG" >&2 || true
    log "Installed, but Aw-Shell isn't running. Code: $INSTALL_DIR, settings: $OLD_DIR"
    return 0
  fi
  log "Installation complete. Code: $INSTALL_DIR, settings: $OLD_DIR"
}

# Run unless sourced (tests source it); `curl ... | bash` has no script file,
# so BASH_SOURCE can't tell, but `return` only works when sourced
if ! (return 0 2>/dev/null); then
  main "$@"
fi
