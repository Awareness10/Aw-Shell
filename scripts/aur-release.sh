#!/usr/bin/env bash
# Publish the release on main to the AUR as aw-shell.
#
#   scripts/aur-release.sh          prepare and show the AUR diff, change nothing
#   scripts/aur-release.sh --push   push to the AUR and commit the PKGBUILD on main
#
# Run after the release is pushed (release flow). Needs an AUR account with
# your SSH key, and pacman-contrib (updpkgsums).
set -euo pipefail

AUR_URL="ssh://aur@aur.archlinux.org/aw-shell.git"
REPO="${AW_SHELL_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PKGBUILD="$REPO/packaging/aur/PKGBUILD"

die() { echo "error: $*" >&2; exit 1; }

# The version and commit to publish; refuses anything but a pushed release
check_release() {
  [[ "$(git -C "$REPO" branch --show-current)" == main ]] || die "run this on main"
  [[ -z "$(git -C "$REPO" status --porcelain)" ]] || die "the working tree isn't clean"
  git -C "$REPO" fetch -q origin main
  [[ "$(git -C "$REPO" rev-parse HEAD)" == "$(git -C "$REPO" rev-parse origin/main)" ]] \
    || die "main isn't pushed (HEAD differs from origin/main)"
  version="$(sed -n 's/^version = "\(.*\)"/\1/p' "$REPO/pyproject.toml" | head -1)"
  [[ -n "$version" && "$version" != *dev* ]] || die "pyproject.toml has version '$version', not a release"
  commit="$(git -C "$REPO" rev-parse HEAD)"
}

# Commit a git dependency is pinned to in uv.lock
locked_commit() {
  python3 - "$REPO/uv.lock" "$1" <<'EOF'
import sys, tomllib
lock = tomllib.load(open(sys.argv[1], "rb"))
package = next(p for p in lock["package"] if p["name"] == sys.argv[2])
print(package["source"]["git"].rsplit("#", 1)[1])
EOF
}

# Writes version, commits and pkgrel=1 into the PKGBUILD given as $1
set_pkgbuild_versions() {
  local file="$1"
  sed -i \
    -e "s/^pkgver=.*/pkgver=$version/" \
    -e "s/^pkgrel=.*/pkgrel=1/" \
    -e "s/^_commit=.*/_commit=$commit/" \
    -e "s/^_fabric_commit=.*/_fabric_commit=$(locked_commit fabric)/" \
    -e "s/^_glaze_commit=.*/_glaze_commit=$(locked_commit glaze)/" \
    "$file"
}

main() {
  local push=false
  [[ "${1:-}" == "--push" ]] && push=true
  command -v updpkgsums >/dev/null || die "updpkgsums missing (pacman -S pacman-contrib)"
  check_release
  echo "==> aw-shell $version from $commit"

  local work
  work="$(mktemp -d)"
  trap 'rm -rf "${work:?}"' EXIT
  cp "$PKGBUILD" "$REPO/packaging/aur/aw-shell.sh" "$REPO/packaging/aur/LICENSE" "$work/"
  set_pkgbuild_versions "$work/PKGBUILD"
  (cd "$work" && updpkgsums && makepkg --printsrcinfo > .SRCINFO)

  echo "==> AUR repository"
  if ! git -c init.defaultBranch=master clone -q "$AUR_URL" "$work/aur" 2>/dev/null; then
    $push && die "couldn't clone $AUR_URL (is your SSH key added to your AUR account?)"
    echo "Couldn't clone $AUR_URL (no AUR SSH key yet?). The files that would be published:"
    cat "$work/PKGBUILD"
    return 0
  fi
  cp "$work/PKGBUILD" "$work/.SRCINFO" "$work/aw-shell.sh" "$work/LICENSE" "$work/aur/"
  # Only the package files, never build output (AUR submission guidelines)
  printf '%s\n' '*' '!PKGBUILD' '!.SRCINFO' '!aw-shell.sh' '!LICENSE' '!.gitignore' \
    > "$work/aur/.gitignore"
  git -C "$work/aur" add PKGBUILD .SRCINFO aw-shell.sh LICENSE .gitignore
  if git -C "$work/aur" diff --cached --quiet; then
    echo "The AUR already has this version."
    return 0
  fi
  git -C "$work/aur" diff --cached --stat
  git -C "$work/aur" diff --cached -- PKGBUILD
  if ! $push; then
    echo "==> Dry run: nothing pushed. Run with --push to publish."
    return 0
  fi

  git -C "$work/aur" commit -q -m "Update to $version-1"
  git -C "$work/aur" push -q origin HEAD:master
  echo "==> Published aw-shell $version-1 to the AUR"

  cp "$work/PKGBUILD" "$PKGBUILD"
  git -C "$REPO" commit -q -m "aur: aw-shell $version" -- "$PKGBUILD"
  echo "==> Committed the PKGBUILD on main; push main (and merge it into dev)"
}

# Run unless sourced (tests source it)
if ! (return 0 2>/dev/null); then
  main "$@"
fi
