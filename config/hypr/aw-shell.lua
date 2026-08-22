-- Converted from aw-shell.conf

local colors = require("aw_shell.config.hypr.colors")

local fabricSend = "fabric-cli exec aw-shell"

local emoji_bangbang = "‼️"
local emoji_speak = "🗣️"
local emoji_fire = "🔥"
local emoji_hole = "🕳️"

local axMessage = "notify-send \"denzh\" \"Ya boi be cooking" .. emoji_bangbang .. emoji_speak .. emoji_fire .. emoji_hole
    .. "\" -i \"/home/denzh/.config/aw-shell/assets/tanjiro-kamado-red.png\""
    .. " -A \"" .. emoji_speak .. "\" -A \"" .. emoji_fire .. "\" -A \"" .. emoji_hole .. "\""
    .. " -a \"Source Code\""

hl.bind("SUPER" .. " + " .. "ALT" .. " + " .. "B", hl.dsp.exec_cmd("killall aw-shell; uwsm-app $(/home/denzh/.config/aw-shell/.venv/bin/python /home/denzh/.config/aw-shell/main.py)")) -- Reload Aw-Shell
hl.bind("SUPER" .. " + " .. "A", hl.dsp.exec_cmd(axMessage)) -- Message
hl.bind("SUPER" .. " + " .. "D", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"dashboard\")'")) -- Dashboard
hl.bind("SUPER" .. " + " .. "", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"bluetooth\")'")) -- Bluetooth (no key bound yet)
hl.bind("SUPER" .. " + " .. "", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"pins\")'")) -- Pins (no key bound yet)
hl.bind("SUPER" .. " + " .. "N", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"kanban\")'")) -- Kanban
hl.bind("SUPER" .. " + " .. "W", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"launcher\")'")) -- App Launcher
hl.bind("SUPER" .. " + " .. "T", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"tmux\")'")) -- Tmux
hl.bind("SUPER" .. " + " .. "V", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"cliphist\")'")) -- Clipboard History
hl.bind("SUPER" .. " + " .. "S", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"tools\")'")) -- Toolbox
hl.bind("SUPER" .. " + " .. "TAB", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"overview\")'")) -- Overview
hl.bind("SUPER" .. " + " .. "COMMA", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"wallpapers\")'")) -- Wallpapers
hl.bind("SUPER" .. " + " .. "SHIFT" .. " + " .. "COMMA", hl.dsp.exec_cmd(fabricSend .. " 'notch.dashboard.wallpapers.set_random_wallpaper(None, external=True)'")) -- Random Wallpaper
hl.bind("SUPER" .. " + " .. "M", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"mixer\")'")) -- Audio Mixer
hl.bind("SUPER" .. " + " .. "PERIOD", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"emoji\")'")) -- Emoji Picker
hl.bind("SUPER" .. " + " .. "ESCAPE", hl.dsp.exec_cmd(fabricSend .. " 'notch.open_notch(\"power\")'")) -- Power Menu
hl.bind("SUPER" .. " + " .. "SHIFT" .. " + " .. "M", hl.dsp.exec_cmd(fabricSend .. " 'notch.dashboard.widgets.buttons.caffeine_button.toggle_inhibit(external=True)'")) -- Toggle Caffeine
hl.bind("SUPER" .. " + " .. "CTRL" .. " + " .. "B", hl.dsp.exec_cmd(fabricSend .. " 'from utils.global_keybinds import get_global_keybind_handler; get_global_keybind_handler().toggle_bar()'")) -- Toggle Bar
hl.bind("SUPER" .. " + " .. "SHIFT" .. " + " .. "B", hl.dsp.exec_cmd(fabricSend .. " 'app.set_css()'")) -- Reload CSS
hl.bind("SUPER" .. " + " .. "CTRL" .. " + " .. "ALT" .. " + " .. "B", hl.dsp.exec_cmd("killall aw-shell; uwsm-app $(GTK_DEBUG=interactive /home/denzh/.config/aw-shell/.venv/bin/python /home/denzh/.config/aw-shell/main.py)")) -- Restart with inspector

-- Wallpapers directory: /home/denzh/Pictures/Wallpapers

-- layerrulev3 = animation 0, namespace:fabric
-- TODO: manual review — layerrulev3 has no known hl.* equivalent yet, check the Hyprland wiki

hl.config({
    general = {
        gaps_in = 2,
        gaps_out = 4,
        border_size = 2,
        layout = "dwindle",
        col = {
            active_border = "rgb(" .. colors.primary .. ")",
            inactive_border = "rgb(" .. colors.surface .. ")",
        },
    },
})

hl.config({
    cursor = {
        no_warps = true,
    },
})

hl.config({
    decoration = {
        blur = {
            enabled = true,
            size = 1,
            passes = 3,
            new_optimizations = true,
            contrast = 1,
            brightness = 1,
        },
        rounding = 14,
        shadow = {
            enabled = true,
            range = 10,
            render_power = 2,
            -- Hyprland colors are hex only: rgba(RRGGBBAA) or 0xAARRGGBB — no CSS-style rgba(r, g, b, a.f)
            color = "rgba(00000040)",
        },
    },
})

hl.config({
    animations = {
        enabled = true,
    },
})

hl.curve("myBezier", {
    type = "bezier",
    points = { { 0.4, 0.0 }, { 0.2, 1.0 } },
})

hl.animation({ leaf = "windows", enabled = true, speed = 2.5, bezier = "myBezier", style = "popin 80%" })
hl.animation({ leaf = "border", enabled = true, speed = 2.5, bezier = "myBezier" })
hl.animation({ leaf = "fade", enabled = true, speed = 2.5, bezier = "myBezier" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 2.5, bezier = "myBezier", style = "slidefade 20%" })

-- Autostart
hl.on("hyprland.start", function()
    hl.exec_cmd("uwsm-app $(/home/denzh/.config/aw-shell/.venv/bin/python /home/denzh/.config/aw-shell/main.py)")
    hl.exec_cmd("wl-paste --type text --watch cliphist store")
    hl.exec_cmd("wl-paste --type image --watch cliphist store")
end)

-- Exec (run every reload)
hl.on("config.reloaded", function()
    hl.exec_cmd("pgrep -x \"hypridle\" > /dev/null || uwsm app -- hypridle")
    hl.exec_cmd("uwsm app -- awww-daemon")
    hl.exec_cmd("cp " .. colors.wallpaper .. " ~/.current.wall")
end)

return {
    fabricSend = fabricSend,
    axMessage = axMessage,
}
