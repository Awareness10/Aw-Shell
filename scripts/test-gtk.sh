#!/usr/bin/env bash
# Run tests in Docker (Ubuntu 24.04 + headless sway), the same way CI does.
#
# Usage:
#   scripts/test-gtk.sh [pytest args...]        real-GTK tests (tests_gtk/) only
#   scripts/test-gtk.sh --all [pytest args...]  unit tests + GTK tests, merged
#                                               coverage written to coverage.json
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
image="aw-shell-gtk-tests"

all=false
if [[ "${1:-}" == "--all" ]]; then
    all=true
    shift
fi

# Minimal build context: the image only needs the dependency files
context="$(mktemp -d)"
trap 'rm -rf "$context"' EXIT
cp "$repo"/{pyproject.toml,uv.lock,.python-version} "$repo/tests_gtk/Dockerfile" "$context/"
echo "==> Building test image ($image)"
docker build -t "$image" "$context"

# Give the caller's UID an account (see Dockerfile) and a writable HOME
setup='mkdir -p "$HOME" && { id -un >/dev/null 2>&1 || echo "tester:x:$(id -u):$(id -g)::$HOME:/bin/sh" >> /etc/passwd; }'
pytest="uv run --frozen --no-sync pytest -p no:cacheprovider"
if $all; then
    # Separate processes: tests/ mocks gi, tests_gtk/ needs the real one
    cmd="$setup && echo '==> Unit tests (tests/)' && $pytest tests --cov-report= $*"
    cmd="$cmd && echo '==> GTK tests (tests_gtk/), merging coverage'"
    cmd="$cmd && $pytest tests_gtk --cov-append --cov-report=term --cov-report=json:coverage.json $*"
else
    cmd="$setup && echo '==> GTK tests (tests_gtk/)' && $pytest tests_gtk $*"
fi
echo "==> Running in container"

tty=()
[[ -t 1 ]] && tty=(-t)

# The code is mounted read-only, as in a package install (/usr/share/aw-shell):
# a test that writes next to the code fails. coverage.json, the only file the
# tests write to the repo, gets its own writable mount.
mounts=(-v "$repo:/src:ro")
if $all; then
    touch "$repo/coverage.json"
    mounts+=(-v "$repo/coverage.json:/src/coverage.json")
fi

# Rootless Docker maps container UIDs 1.. onto the user's /etc/subuid range,
# so our UID in the container can't write to coverage.json; let that sub-UID.
if $all && docker info --format '{{.SecurityOptions}}' | grep -q 'name=rootless'; then
    subuid_start=$(awk -F: -v name="$(id -un)" -v uid="$(id -u)" \
        '$1 == name || $1 == uid { print $2; exit }' /etc/subuid)
    if [[ -z "$subuid_start" ]]; then
        echo "error: rootless Docker but no /etc/subuid entry for $(id -un)" >&2
        exit 1
    fi
    if ! command -v setfacl >/dev/null; then
        echo "error: rootless Docker needs setfacl (package: acl) to write coverage.json" >&2
        exit 1
    fi
    setfacl -m "u:$((subuid_start + $(id -u) - 1)):rw" "$repo/coverage.json"
fi

# Run as the invoking user so nothing root-owned lands in the mounted repo
docker run --rm "${tty[@]}" \
    --user "$(id -u):$(id -g)" \
    "${mounts[@]}" \
    -e HOME=/tmp/home \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e UV_CACHE_DIR=/tmp/uv-cache \
    -e COVERAGE_FILE=/tmp/.coverage \
    "$image" \
    sh -c "$cmd"
