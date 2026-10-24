"""scripts/aur-release.sh: publishes only a pushed release from main, and sets
the PKGBUILD's versions from pyproject and uv.lock. Sourced, never pushes."""

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "aur-release.sh"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"HOME": str(cwd), "PATH": "/usr/bin:/bin",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def _source(snippet, repo, home):
    return subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}"; {snippet}'],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin", "AW_SHELL_REPO": str(repo)},
        capture_output=True, text=True,
    )


@pytest.fixture
def release_repo(tmp_path):
    """A clone of a bare 'origin' whose main is at a release version."""
    origin, repo = tmp_path / "origin.git", tmp_path / "repo"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "clone", "-q", str(origin), str(repo))
    _git(repo, "checkout", "-q", "-b", "main")
    (repo / "pyproject.toml").write_text('[project]\nversion = "1.2.15"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "v1.2.15")
    _git(repo, "push", "-q", "origin", "main")
    return repo


def test_accepts_a_pushed_release(release_repo, tmp_path):
    result = _source('check_release && echo "$version $commit"', release_repo, tmp_path)
    assert result.returncode == 0, result.stderr
    version, commit = result.stdout.split()
    assert version == "1.2.15" and len(commit) == 40


@pytest.mark.parametrize("change, message", [
    ("branch", "run this on main"),
    ("dirty", "isn't clean"),
    ("unpushed", "isn't pushed"),
    ("dev", "not a release"),
])
def test_refuses_anything_else(release_repo, tmp_path, change, message):
    if change == "branch":
        _git(release_repo, "checkout", "-q", "-b", "dev")
    elif change == "dirty":
        (release_repo / "new-file").write_text("x")
    elif change == "unpushed":
        (release_repo / "a").write_text("x")
        _git(release_repo, "add", "a")
        _git(release_repo, "commit", "-q", "-m", "local only")
    elif change == "dev":
        (release_repo / "pyproject.toml").write_text('[project]\nversion = "1.2.16.dev0"\n')
        _git(release_repo, "commit", "-q", "-am", "dev")
        _git(release_repo, "push", "-q", "origin", "main")
    result = _source("check_release", release_repo, tmp_path)
    assert result.returncode != 0
    assert message in result.stderr


def test_sets_versions_from_pyproject_and_uv_lock(tmp_path):
    pkgbuild = tmp_path / "PKGBUILD"
    pkgbuild.write_text((REPO / "packaging" / "aur" / "PKGBUILD").read_text())
    result = _source(f'version=9.9.9 commit=abc123 set_pkgbuild_versions "{pkgbuild}"',
                     REPO, tmp_path)
    assert result.returncode == 0, result.stderr
    text = pkgbuild.read_text()
    assert "\npkgver=9.9.9\n" in text and "\npkgrel=1\n" in text
    assert "\n_commit=abc123\n" in text
    lock = (REPO / "uv.lock").read_text()
    for name in ("fabric", "glaze"):
        pinned = next(line for line in text.splitlines() if line.startswith(f"_{name}_commit="))
        assert pinned.split("=", 1)[1] in lock
