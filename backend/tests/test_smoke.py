"""M1 ドメインスケルトン投入までの間 CI を緑に保つためのスモークテスト。"""

from bakufu import __version__


def test_version_matches_skeleton() -> None:
    assert __version__ == "0.0.0"
