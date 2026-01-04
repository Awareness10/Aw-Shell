<p align="center">
<a href="https://github.com/awareness10/Aw-Shell">
  <img src="assets/cover.png">
  </a>
</p>

<p align="center">
  <sub><sup><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Telegram-Animated-Emojis/main/Activity/Sparkles.webp" alt="Sparkles" width="25" height="25"/></sup></sub>
  <a href="https://github.com/hyprwm/Hyprland">
    <img src="https://img.shields.io/badge/A%20hackable%20shell%20for-Hyprland-0092CD?style=for-the-badge&logo=linux&color=0092CD&logoColor=D9E0EE&labelColor=000000" alt="A hackable shell for Hyprland">
  </a>
  <a href="https://github.com/Fabric-Development/fabric/">
    <img src="https://img.shields.io/badge/Powered%20by-Fabric-FAFAFA?style=for-the-badge&logo=python&color=FAFAFA&logoColor=D9E0EE&labelColor=000000" alt="Powered by Fabric">
  <sub><sup><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Telegram-Animated-Emojis/main/Activity/Sparkles.webp" alt="Sparkles" width="25" height="25"/></sup></sub>
  </a>
  </p>

  <p align="center">
  <a href="https://github.com/awareness10/Aw-Shell/stargazers">
    <img src="https://img.shields.io/github/stars/awareness10/Aw-Shell?style=for-the-badge&logo=github&color=E3B341&logoColor=D9E0EE&labelColor=000000" alt="GitHub stars">
  </a>
</p>

> Forked from [Axenide/Ax-Shell](https://github.com/Axenide/Ax-Shell) - A hackable shell for Hyprland

---

<h2><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Camera%20with%20Flash.png" alt="Camera with Flash" width="25" height="25" /></sub> Screenshots</h2>
<table align="center">
  <tr>
    <td colspan="4"><img src="assets/screenshots/1.png"></td>
  </tr>
  <tr>
    <td colspan="1"><img src="assets/screenshots/2.png"></td>
    <td colspan="1"><img src="assets/screenshots/3.png"></td>
    <td colspan="1" align="center"><img src="assets/screenshots/4.png"></td>
    <td colspan="1" align="center"><img src="assets/screenshots/5.png"></td>
  </tr>
</table>

<h2><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Package.png" alt="Package" width="25" height="25" /></sub> Installation</h2>

> [!NOTE]
> You need a functioning Hyprland installation.
> This will also enable NetworkManager if it is not already enabled.

### Arch Linux

> [!TIP]
> This command also works for updating an existing installation!

**Run the following command in your terminal once logged into Hyprland:**
```bash
curl -fsSL https://raw.githubusercontent.com/awareness10/Aw-Shell/main/install.sh | bash
```

### Manual Installation
1. Install dependencies:
    - [Fabric](https://github.com/Fabric-Development/fabric)
    - [fabric-cli](https://github.com/Fabric-Development/fabric-cli)
    - [Gray](https://github.com/Fabric-Development/gray)
    - [Matugen](https://github.com/InioX/matugen)
    - `awww`
    - `brightnessctl`
    - `cava`
    - `cliphist`
    - `ddcutil`
    - `gnome-bluetooth-3.0`
    - `gobject-introspection`
    - `gpu-screen-recorder`
    - `grimblast`
    - `hypridle`
    - `hyprlock`
    - `hyprpicker`
    - `hyprshot`
    - `hyprsunset`
    - `imagemagick`
    - `libnotify`
    - `networkmanager`
    - `network-manager-applet`
    - `nm-connection-editor`
    - `noto-fonts-emoji`
    - `nvtop`
    - `playerctl`
    - `swappy`
    - `tesseract`
    - `tesseract-data-eng`
    - `tesseract-data-spa`
    - `tmux`
    - `unzip`
    - `upower`
    - `uwsm`
    - `vte3`
    - `webp-pixbuf-loader`
    - `wl-clipboard`
    - Python dependencies:
        - PyGObject
        - ijson
        - numpy
        - pillow
        - psutil
        - pywayland
        - requests
        - setproctitle
        - toml
        - watchdog
    - Fonts (automated on first run):
        - Zed Sans
        - Tabler Icons

2. Download and run Aw-Shell:
    ```bash
    git clone https://github.com/awareness10/Aw-Shell.git ~/.config/Aw-Shell
    uwsm -- app python ~/.config/Aw-Shell/main.py > /dev/null 2>&1 & disown
    ```

<h2><sub><img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Travel%20and%20places/Rocket.png" alt="Rocket" width="25" height="25" /></sub> Features</h2>

- App Launcher
- Bluetooth Manager
- Calculator
- Calendar
- Clipboard Manager
- Color Picker
- Customizable UI
- Dashboard
- Dock
- Emoji Picker
- Kanban Board
- Network Manager
- Notifications
- OCR
- Pins
- Power Manager
- Power Menu
- Screen Recorder
- Screenshot
- Settings
- System Tray
- Terminal
- Tmux Session Manager
- Update checker
- Vertical Layout
- Wallpaper Selector
- Workspaces Overview
- Multi-monitor support

---

> Original project by [Axenide](https://github.com/Axenide). Consider supporting the original author on [Ko-fi](https://ko-fi.com/Axenide)!
