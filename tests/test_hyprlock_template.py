"""config/hypr/hyprlock.conf, the default lock screen copied to
~/.config/hypr/hyprlock.conf: it must load on current hyprlock and only run
commands a base Arch install has."""

from config.paths import HYPRLOCK_TEMPLATE

TEMPLATE = HYPRLOCK_TEMPLATE.read_text()


def test_no_options_hyprlock_removed():
    # hyprlock 0.9 refuses the whole config: "<general:grace> does not exist"
    assert "grace" not in TEMPLATE


def test_hostname_without_inetutils():
    # `hostname` is in inetutils, not in base; uname is coreutils
    assert "$(hostname)" not in TEMPLATE
    assert '$USER@$(uname -n)' in TEMPLATE
