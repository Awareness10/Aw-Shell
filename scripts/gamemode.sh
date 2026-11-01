#!/usr/bin/env sh

# Game mode is active when animations are disabled. Older Hyprland prints
# "int: 1", newer prints "bool: true"
animations_enabled() {
    case "$(hyprctl getoption animations:enabled | awk 'NR==1{print $2}')" in
        1|true) return 0 ;;
        *) return 1 ;;
    esac
}

check_gamemode() {
    if animations_enabled; then
        echo "f"
        return 1
    else
        echo "t"
        return 0
    fi
}

# Legacy hyprland.conf setups take `keyword`. Lua configs reject it, and the
# wording changed between releases ("can't work with non-legacy parsers",
# later "unknown request"), so any reply other than all "ok" means: use
# `eval hl.config(...)` instead
enable_gamemode() {
    result=$(hyprctl --batch "\
        keyword animations:enabled 0;\
        keyword decoration:shadow:enabled 0;\
        keyword decoration:blur:enabled 0;\
        keyword general:gaps_in 0;\
        keyword general:gaps_out 0;\
        keyword general:border_size 1;\
        keyword decoration:rounding 0")
    if [ -n "$result" ] && [ -z "$(printf '%s\n' "$result" | tr -s '[:space:]' '\n' | grep -vxE 'ok|')" ]; then
        return 0
    fi
    result=$(hyprctl eval 'hl.config({
        animations = { enabled = false },
        decoration = { rounding = 0, shadow = { enabled = false }, blur = { enabled = false } },
        general = { gaps_in = 0, gaps_out = 0, border_size = 1 },
    })')
    if [ "$result" != "ok" ]; then
        echo "gamemode: could not apply game mode: $result" >&2
        return 1
    fi
}

# Toggle game mode state; reloading the config restores the normal look
toggle_gamemode() {
    if animations_enabled; then
        enable_gamemode
    else
        hyprctl reload
    fi
}

# Main script logic
case "$1" in
    check)
        check_gamemode
        ;;
    *)
        toggle_gamemode
        ;;
esac
