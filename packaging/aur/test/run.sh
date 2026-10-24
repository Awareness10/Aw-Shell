#!/bin/bash
# Runs inside the Arch container (see scripts/test-aur.sh), as the builder
# user, with the repo mounted read-only at /src. Builds the package from the
# working tree, installs it, lints it and starts it.
set -euo pipefail

build=/tmp/build
mkdir -p "$build"
git config --global --add safe.directory '*'

echo "==> Packing the working tree"
# Tracked and new (not ignored) files, including uncommitted changes. The
# PKGBUILD finds this tarball by name instead of downloading a commit.
(
  cd /src
  git ls-files -z --cached --others --exclude-standard |
    while IFS= read -r -d '' f; do [[ -e "$f" ]] && printf '%s\0' "$f"; done |
    tar --null -T - -czf "$build/Aw-Shell-worktree.tar.gz" --transform 's|^|Aw-Shell-worktree/|'
)
cp /src/packaging/aur/PKGBUILD /src/packaging/aur/aw-shell.sh "$build/"
cd "$build"
sed -i 's/^_commit=.*/_commit=worktree/' PKGBUILD
updpkgsums

echo "==> Building and installing"
makepkg -si --noconfirm

echo "==> namcap"
lint="$(namcap PKGBUILD aw-shell-*.pkg.tar.zst 2>&1 || true)"
echo "$lint"
if grep -q ' E: ' <<<"$lint"; then
  echo "FAIL: namcap reported errors"
  exit 1
fi

echo "==> Bundled libraries load (with the launcher's paths)"
eval "$(grep '^export ' /usr/bin/aw-shell)"
python - <<'PY'
import gi
gi.require_version("Gray", "0.1")
from gi.repository import Gray  # bundled, built by the PKGBUILD
import fabric.widgets.wayland, glaze  # bundled, PyGObject 3.51+ fix included
print("OK: Gray", Gray.Watcher.__gtype__, "| glaze", glaze.__version__, "| fabric", fabric.__file__)
PY

echo "==> aw-shell --migrate on a fresh home"
out="$(HOME="$(mktemp -d)" aw-shell --migrate 2>&1)"
echo "$out"
grep -q "Nothing to migrate." <<<"$out"

echo "==> Starting aw-shell"
python /src/packaging/aur/test/smoke.py
