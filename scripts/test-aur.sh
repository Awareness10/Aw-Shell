#!/usr/bin/env bash
# Build, install and start the aw-shell package on Arch, in Docker. Uses the
# working tree (uncommitted changes included) as the source; nothing is
# published. See packaging/aur/test/run.sh for the steps.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
image="aw-shell-aur-test"

echo "==> Building the Arch test image ($image)"
docker build -t "$image" "$repo/packaging/aur" -f "$repo/packaging/aur/test/Dockerfile"

echo "==> Running in container"
docker run --rm -v "$repo:/src:ro" "$image" bash /src/packaging/aur/test/run.sh
