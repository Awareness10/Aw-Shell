# Arch environment for scripts/test-aur.sh: builds, installs and starts the
# aw-shell package with Arch's real packages. The dependency layer is cached
# and rebuilt only when the PKGBUILD changes.
FROM archlinux:base-devel

RUN pacman -Syu --noconfirm --needed git pacman-contrib namcap sway dbus python-pytest \
    && useradd -m builder \
    && echo 'builder ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/builder

USER builder
WORKDIR /home/builder

RUN git clone --depth=1 https://aur.archlinux.org/yay-bin.git \
    && (cd yay-bin && makepkg -si --noconfirm) \
    && rm -rf yay-bin

# The package's dependencies (repo, and fabric-cli-git from the AUR)
COPY PKGBUILD /tmp/deps/PKGBUILD
RUN bash -c 'source /tmp/deps/PKGBUILD && depends=("${depends[@]/fabric-cli/fabric-cli-git}") \
    && yay -S --noconfirm --needed --removemake "${depends[@]}" "${makedepends[@]}"'
RUN yay -Scc --noconfirm >/dev/null 2>&1 || true

# Arch's sway has cap_sys_nice (for raising its priority); binaries with file
# capabilities can't run in a rootless container, and headless sway needs none
USER root
RUN setcap -r /usr/bin/sway
USER builder
