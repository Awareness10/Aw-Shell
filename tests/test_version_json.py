"""The repo's version.json: grouped releases and the legacy flat changelog."""

import json
from pathlib import Path

VERSION_JSON = json.loads((Path(__file__).parent.parent / "version.json").read_text())


def _key(version):
    return tuple(int(x) for x in version.split("."))


def test_latest_release_matches_version():
    assert VERSION_JSON["releases"][0]["version"] == VERSION_JSON["version"]


def test_legacy_changelog_mirrors_latest_release():
    # Updaters up to 1.2.6 only read the flat `changelog`
    assert VERSION_JSON["changelog"] == VERSION_JSON["releases"][0]["changes"]


def test_releases_are_newest_first_and_unique():
    versions = [r["version"] for r in VERSION_JSON["releases"]]
    assert versions == sorted(versions, key=_key, reverse=True)
    assert len(versions) == len(set(versions))


def test_every_release_lists_changes():
    for release in VERSION_JSON["releases"]:
        assert release["changes"], release["version"]
        assert all(isinstance(c, str) and c for c in release["changes"])
