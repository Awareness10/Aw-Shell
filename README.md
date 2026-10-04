<p align="center">
<a href="https://github.com/awareness10/Aw-Shell">
  <img src="assets/banner.png">
  </a>
</p>

<p align="center">
  <sub><sup><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Telegram-Animated-Emojis/main/Activity/Sparkles.webp" alt="Sparkles" width="25" height="25"/></sup></sub>
  <a href="https://github.com/hyprwm/Hyprland"><img src="https://img.shields.io/badge/A%20hackable%20shell%20for-Hyprland-0092CD?style=for-the-badge&logo=linux&color=0092CD&logoColor=D9E0EE&labelColor=000000" alt="A hackable shell for Hyprland"></a>
  <a href="https://github.com/Fabric-Development/fabric/"><img src="https://img.shields.io/badge/Powered%20by-Fabric-FAFAFA?style=for-the-badge&logo=python&color=FAFAFA&logoColor=D9E0EE&labelColor=000000" alt="Powered by Fabric"></a>
  <sub><sup><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Telegram-Animated-Emojis/main/Activity/Sparkles.webp" alt="Sparkles" width="25" height="25"/></sup></sub>
</p>

<p align="center">
  <a href="https://github.com/awareness10/Aw-Shell/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/awareness10/Aw-Shell/test.yml?style=for-the-badge&logo=github-actions&logoColor=D9E0EE&labelColor=000000&label=tests" alt="Tests"></a>
  <a href="https://github.com/awareness10/Aw-Shell/actions/workflows/test.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Awareness10/Aw-Shell/badges/coverage.json&style=for-the-badge&logo=pytest&logoColor=D9E0EE&labelColor=000000" alt="Coverage"></a>
</p>

> Forked from [Axenide/Ax-Shell](https://github.com/Axenide/Ax-Shell) - A hackable shell for Hyprland

---

## Table of Contents

- [Screenshots](#screenshots)
- [Installation](#installation)
  - [Supported systems](#supported-systems)
  - [Install script](#install-script)
  - [Manual Installation](#manual-installation)
- [Features](#features)
- [Testing](#testing)
  - [Running](#running)
  - [The GTK sandbox](#the-gtk-sandbox)
  - [CI](#ci)
  - [Limitations](#limitations)
- [Changes from Ax-Shell](#changes-from-ax-shell)

---

<h2 id="screenshots"><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Camera%20with%20Flash.png" alt="Camera with Flash" width="25" height="25" /></sub> Screenshots</h2>
<table align="center">
  <tr>
    <td colspan="5"><img src="assets/screenshots/1.png"></td>
  </tr>
  <tr>
    <td colspan="2"><img src="assets/screenshots/2.png"></td>
    <td colspan="1"><img src="assets/screenshots/3.png"></td>
    <td colspan="1" align="center"><img src="assets/screenshots/4.png"></td>
    <td colspan="2" align="center"><img src="assets/screenshots/5.png"></td>
  </tr>
</table>

<h2 id="installation"><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Package.png" alt="Package" width="25" height="25" /></sub> Installation</h2>

### Supported systems

| System | Status |
|---|---|
| Arch Linux | Supported |
| CachyOS | Supported (used daily) |
| Other distros on Arch's own repositories (e.g. EndeavourOS) | Expected to work, not tested |
| Manjaro | Untested: its delayed repositories can clash with the AUR packages |
| Non-Arch distros (Debian, Ubuntu, Fedora, NixOS, ...) | Not supported |

Requirements:
- Hyprland 0.56.2 or newer
- [uwsm](https://github.com/Vladimir-csp/uwsm): the installer and the generated Hyprland config launch the shell with `uwsm app`
- `pacman` with access to the AUR; the installer uses `paru` or `yay` and installs `yay-bin` if neither is present. Several dependencies (fabric-cli, Gray, matugen) only exist in the AUR
- systemd

> [!NOTE]
> The installer enables NetworkManager if it is not already enabled, and disables `iwd` if it is running.

### Install script

> [!TIP]
> This command also works for updating an existing installation!

**Run the following command in your terminal once logged into Hyprland:**
```bash
curl -fsSL https://raw.githubusercontent.com/Awareness10/Aw-Shell/main/install.sh | bash
```

### Manual Installation

1. Install [uv](https://docs.astral.sh/uv/):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2. Install system dependencies (Arch Linux):
    - [fabric-cli](https://github.com/Fabric-Development/fabric-cli)
    - [Gray](https://github.com/Fabric-Development/gray)
    - [Matugen](https://github.com/InioX/matugen)
    - `awww` `brightnessctl` `cava` `cliphist` `ddcutil`
    - `bluez-utils` `gobject-introspection` `gpu-screen-recorder` `headsetcontrol`
    - `hypridle` `hyprlock` `hyprpicker` `hyprshot` `hyprsunset`
    - `imagemagick` `libnotify` `networkmanager` `network-manager-applet`
    - `nm-connection-editor` `noto-fonts-emoji` `nvtop` `playerctl`
    - `power-profiles-daemon` `swappy` `tesseract` `tesseract-data-eng`
    - `tesseract-data-spa` `tmux` `unzip` `upower` `uwsm` `vte3`
    - `webp-pixbuf-loader` `wl-clipboard`

3. Clone, install Python deps, and run:
    ```bash
    git clone https://github.com/Awareness10/Aw-Shell.git ~/.config/aw-shell
    cd ~/.config/aw-shell
    uv sync
    uwsm app -- .venv/bin/python main.py > /dev/null 2>&1 & disown
    ```

<h2 id="features"><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Travel%20and%20places/Rocket.png" alt="Rocket" width="25" height="25" /></sub> Features</h2>

- App Launcher
- Bluetooth Manager
- Caffeine / Idle Control
- Calculator
- Calendar
- Clipboard Manager
- Color Picker
- Customizable UI
- Dashboard
- Dock
- Headset & Mouse Battery
- Emoji Picker
- Kanban Board
- Network Manager
- Notifications
- OCR
- Pins
- Power Manager
- Power Menu
- Screen Recorder (with recording indicator)
- Screenshot
- Settings
- System Tray
- Terminal
- Tmux Session Manager
- Update checker
- Vertical Layout
- Wallpaper Selector
- Weather
- Workspaces Overview
- Multi-monitor support

<h2 id="testing"><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Test%20Tube.png" alt="Test Tube" width="25" height="25" /></sub> Testing</h2>

There are two test suites. They must run in separate processes: `tests/` replaces `gi` with mocks, `tests_gtk/` needs the real one.

| Suite | What it covers | How |
|---|---|---|
| `tests/` | Logic: settings, config generation, monitor mapping, layout, conversions, updater, weather | `gi`, GTK and parts of fabric are mocked in `tests/conftest.py`; PySide6 runs offscreen; runs in a temporary `HOME`, so your own config doesn't affect results |
| `tests_gtk/` | Widgets built against real GTK/fabric: build smoke tests for the bar, notch, dock and most panels, plus notifications, overview, metrics, system tray | Runs inside a sandbox (see below) |

### Running

```bash
uv sync                       # includes the dev group (pytest, pytest-cov, ruff)
uv run pytest                 # unit tests (tests/)
uv run pytest tests_gtk       # GTK tests, needs sway plus the shell's system deps (see below)
scripts/test-gtk.sh --all     # both suites in Docker, exactly like CI, merged coverage
scripts/test-gtk.sh           # GTK tests only, in Docker
uv run ruff check .           # lint
uv audit --preview-features audit-command   # known vulnerabilities in locked dependencies
```

Running `tests_gtk` locally needs `sway` (`pacman -S sway`) and the libraries the shell itself uses (e.g. gtk-layer-shell, Gray, NetworkManager and playerctl typelibs); with a working Aw-Shell install, only sway is missing. Without them, use the Docker script.

Coverage is on by default (`--cov` in `pyproject.toml`). Use the local runs while working, and the Docker run before pushing: it uses Ubuntu 24.04 like CI, so results can differ from Arch, which ships newer libraries.

### The GTK sandbox

`tests_gtk/conftest.py` sets everything up before anything imports `gi`, so the tests never touch your running session:

- a private **headless sway** as the Wayland compositor (it has the layer-shell protocol fabric needs). Nothing appears on screen, and sway doesn't need seatd/polkit setup for this
- a private **D-Bus** session/system bus with a fake UPower (`fake_upower.py`)
- fake **Hyprland** IPC sockets and a `hyprctl` stub (`fake_hyprland.py`)
- a temporary `HOME`/XDG dirs with a copy of `config/` and `styles/`, without your `config.json`
- stubs for commands with side effects (`systemctl`, `pkill`, `matugen`, `notify-send`, ...), which log their arguments instead of running (read them with `sandbox.commands()`)

`test_sandbox.py` checks the isolation itself. Everything is cleaned up when the run ends, including after a failed start.

### CI

`.github/workflows/test.yml` runs `scripts/test-gtk.sh --all` on pushes to `main`/`dev` and on pull requests to `main`. On push, the merged coverage is published to the `badges` branch for the coverage badge above.

`.github/workflows/audit.yml` runs `uv audit` on the same pushes and weekly on `main`, since advisories appear without any change here. Advisories that don't apply are listed under `[tool.uv.audit]` in `pyproject.toml`, with the reason.

### Limitations

- **Coverage is split by design.** Plain `uv run pytest` reports only what the unit tests reach, so it looks low; the real number is the merged one from `scripts/test-gtk.sh --all`, which is what the badge shows.
- **Smoke tests check that widgets build, not how they look or behave in depth.** Only a few modules have behaviour tests (`test_notification_popup`, `test_overview`, `test_metrics`, `test_systemtray`, `test_wallpapers`, `test_wayland`).
- **Some code is only reached by the smoke tests or not at all,** e.g. the UPower client and Bluetooth service are partly covered, global keybinds and the tooltip helper not at all.
- **Real hardware isn't exercised.** Monitors, audio, Bluetooth, NetworkManager and brightness are faked, stubbed or absent in the sandbox.
- **PyGObject is pinned to 3.50.0** by fabric; newer versions break its enum properties. A few deprecation warnings from fabric and PyGObject are filtered in `pyproject.toml` because they can't be fixed here.

<h2 id="changes-from-ax-shell"><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Wrench.png" alt="Wrench" width="25" height="25" /></sub> Changes from Ax-Shell</h2>

Aw-Shell started from Ax-Shell, which is now deprecated upstream, and has since grown into its own project:

**Hyprland compatibility**
- **Lua config** — keybinds and settings generate a native Hyprland Lua config, compatible with Hyprland 0.56.2+ (including the 0.57 module changes)
- **Live theme updates** — border colors apply over Hyprland IPC after a wallpaper change, no reload needed

**Performance**
- **No process polling** — toolbox status (screen recorder, pomodoro, gamemode) is checked in-process by one shared poller instead of spawning `pgrep` and scripts every 2 seconds on every monitor
- **Event-driven notch hiding** — the notch reacts to Hyprland events per monitor instead of polling the active window twice a second
- **Shared pollers** — tray watcher and headset battery run once and serve every bar

**Multi-monitor**
- Monitor ids match screens, and the main monitor is whichever holds workspace 1 — no hard-coded connector names
- Tray icons on every bar; dashboard, launcher, workspaces and notifications open on the focused monitor
- Rounded corners and notch hiding work per monitor

**Settings & theming**
- **PySide6 (Qt6) settings window** — the first step of the migration to Qt, styled with [Glaze](https://github.com/Awareness10/Glaze); sizes itself to the screen it opens on
- **Color schemes** — the selected Matugen scheme is remembered and applied immediately; the full palette is written to `config/colors.json` for other tools
- **Matugen 4** support
- **Idle** — "Suspend when idle" option, a working Caffeine toggle, and a single hypridle instance after Apply

**New & rewritten**
- **Bluetooth** — rewritten on BlueZ D-Bus and `bluetoothctl`
- **Updater** — fresh version checks via the GitHub API, changelog grouped by version with one row per change
- **Peripherals** — headset battery (via `headsetcontrol`) and Logitech mouse battery in the control panel
- **Screen recorder indicator**, weather widget, and tooltips throughout
- **Fixes** — Wi-Fi no longer creates duplicate profiles, wallpaper thumbnails refresh when files change, metrics work without UPower, overview handles close confirmations

**Development**
- **`uv`** — reproducible installs with `uv sync` instead of a manual pip/venv setup
- **Tests & CI** — unit tests plus real-GTK tests in a sandbox, with coverage on every push (see [Testing](#testing))
- **Code quality** — dead code removed, `pathlib` over `os.path`, cleaned imports and typings

---

> Originally based on [Ax-Shell](https://github.com/Axenide/Ax-Shell) by [Axenide](https://github.com/Axenide). Consider supporting the original author on [Ko-fi](https://ko-fi.com/Axenide).
