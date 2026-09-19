# Environment for tests_gtk: Ubuntu 24.04 (same as CI) with headless sway.
# Built and run by scripts/test-gtk.sh; the repo is mounted at /src.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential pkg-config meson ninja-build \
        sway dbus-daemon \
        libgtk-3-dev libgirepository1.0-dev libcairo2-dev libdbus-1-dev \
        libwayland-dev libffi-dev \
        gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 gir1.2-nm-1.0 gir1.2-playerctl-2.0 \
        gir1.2-cvc-1.0 \
        valac gobject-introspection libdbusmenu-gtk3-dev libdbusmenu-glib-dev \
        adwaita-icon-theme fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Fabric's system tray library (not packaged by Ubuntu)
ARG GRAY_COMMIT=d5a8452c39b074ef6da25be95305a22203cf230e
RUN git clone https://github.com/Fabric-Development/gray /tmp/gray \
    && git -C /tmp/gray checkout "$GRAY_COMMIT" \
    && meson setup /tmp/gray/build /tmp/gray --prefix=/usr \
    && ninja -C /tmp/gray/build install \
    && rm -rf /tmp/gray

# scripts/test-gtk.sh runs as the caller's UID (so files in the mounted repo
# aren't root-owned) and adds that UID here; dbus-daemon won't start for a UID
# without a passwd entry
RUN chmod 666 /etc/passwd

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Keep the container's venv out of the mounted repo's .venv
ENV UV_PROJECT_ENVIRONMENT=/venv UV_LINK_MODE=copy UV_PYTHON_INSTALL_DIR=/python
WORKDIR /src
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --group dev --no-install-project
