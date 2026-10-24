#!/bin/bash

# Shows the picked color as the notification icon. The icon is a private temp
# file in $XDG_RUNTIME_DIR, not a fixed name in the shared /tmp.
notify_color() {  # $1 = color for magick, $2 = title, $3 = text
    local icon
    icon="$(mktemp --suffix=.png -p "${XDG_RUNTIME_DIR:-/tmp}")" || exit 1
    magick -size 64x64 xc:"$1" "$icon"
    notify-send "$2" "$3" -i "$icon" -a "Hyprpicker"
    rm -f "$icon"
}


pick_rgb(){
    # Pick in RGB format; hyprpicker copies it to the clipboard (-a)
    hyprpicker -a -n -f rgb && sleep 0.1
    notify_color "rgb($(wl-paste))" "RGB color picked" "rgb($(wl-paste))"
    exit 0
}


pick_hex(){
    hyprpicker -a -n -f hex && sleep 0.1
    notify_color "$(wl-paste)" "HEX color picked" "$(wl-paste)"
    exit 0
}


pick_hsv(){
    # Copy the color to the clipboard
    echo -n "$(hyprpicker -n -f hsv)" | wl-copy -n
    notify_color "hsv($(wl-paste))" "HSV color picked" "hsv($(wl-paste))"
    exit 0
}



case "$1" in
-rgb)
    pick_rgb
    ;;
-hsv)
    pick_hsv
    ;;
-hex)
    pick_hex
    ;;

*)
    echo "Usage: $0 [-rgb|-hex|-hsv]"
    exit 1
    ;;
esac
