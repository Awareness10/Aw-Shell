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
docker build -q -t "$image" "$context" >/dev/null

# Give the caller's UID an account (see Dockerfile) and a writable HOME
setup='mkdir -p "$HOME" && { id -un >/dev/null 2>&1 || echo "tester:x:$(id -u):$(id -g)::$HOME:/bin/sh" >> /etc/passwd; }'
pytest="uv run --frozen --no-sync pytest -p no:cacheprovider"
if $all; then
    # Separate processes: tests/ mocks gi, tests_gtk/ needs the real one
    cmd="$setup && $pytest tests --cov-report= $* && $pytest tests_gtk --cov-append --cov-report=term --cov-report=json:coverage.json $*"
else
    cmd="$setup && $pytest tests_gtk $*"
fi

tty=()
[[ -t 1 ]] && tty=(-t)

# Run as the invoking user so nothing root-owned lands in the mounted repo
docker run --rm "${tty[@]}" \
    --user "$(id -u):$(id -g)" \
    -v "$repo:/src" \
    -e HOME=/tmp/home \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -e UV_CACHE_DIR=/tmp/uv-cache \
    -e COVERAGE_FILE=/tmp/.coverage \
    "$image" \
    sh -c "$cmd"
