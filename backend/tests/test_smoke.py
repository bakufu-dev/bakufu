"""Smoke test to keep CI green until M1 domain skeleton lands."""

from bakufu import __version__


def test_version_matches_skeleton() -> None:
    assert __version__ == "0.0.0"
