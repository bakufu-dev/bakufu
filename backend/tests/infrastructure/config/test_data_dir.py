"""DataDirResolver unit tests (TC-UT-PF-001 / 002 / 033 / 038 / 039 / 040).

Covers REQ-PF-001 (resolve + Fail Fast on invalid env) and the OS-default
branch tree. Schneier 申し送り #1 物理保証: relative paths, NUL bytes, and
``..`` segments must be rejected at startup time so a cwd-controlling
attacker cannot point bakufu at a different directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from bakufu.infrastructure.config import data_dir
from bakufu.infrastructure.exceptions import BakufuConfigError


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Clear the module-level singleton before every test."""
    data_dir.reset()
    yield
    data_dir.reset()


class TestDefaultsForOs:
    """TC-UT-PF-001: BAKUFU_DATA_DIR unset falls back per OS."""

    def test_linux_xdg_data_home_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-001: XDG_DATA_HOME wins on Linux when set."""
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        resolved = data_dir.resolve()
        assert resolved == (tmp_path / "bakufu").resolve()

    def test_linux_falls_back_to_home_local_share(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-001: HOME/.local/share/bakufu when XDG unset."""
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        resolved = data_dir.resolve()
        assert resolved == (tmp_path / ".local" / "share" / "bakufu").resolve()

    def test_macos_uses_home_local_share(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-001: macOS shares the POSIX path."""
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        resolved = data_dir.resolve()
        assert resolved == (tmp_path / ".local" / "share" / "bakufu").resolve()

    def test_windows_uses_localappdata(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-001: Windows uses %LOCALAPPDATA%\\bakufu."""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        resolved = data_dir.resolve()
        assert resolved == (tmp_path / "bakufu").resolve()


class TestRelativePathRejected:
    """TC-UT-PF-002 / 033: relative path raises with MSG-PF-001."""

    def test_relative_path_raises_bakufu_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-PF-002: ./relative/path is rejected."""
        monkeypatch.setenv("BAKUFU_DATA_DIR", "./relative/path")
        with pytest.raises(BakufuConfigError) as excinfo:
            data_dir.resolve()
        assert excinfo.value.msg_id == "MSG-PF-001"

    def test_msg_pf_001_wording_starts_with_fail_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-PF-033: '[FAIL] BAKUFU_DATA_DIR must be an absolute path' prefix."""
        monkeypatch.setenv("BAKUFU_DATA_DIR", "./relative")
        with pytest.raises(BakufuConfigError) as excinfo:
            data_dir.resolve()
        assert excinfo.value.message.startswith("[FAIL] BAKUFU_DATA_DIR must be an absolute path")


class TestNulByteRejected:
    """TC-UT-PF-038: NUL byte in env raises (Schneier #1 path-traversal vector).

    ``os.environ`` itself rejects NUL bytes at the OS layer, so we
    invoke the internal validator directly to confirm bakufu's defense
    fires *before* a malicious value could ever reach the env. This
    matches the documented Fail-Fast contract.
    """

    def test_nul_byte_raises(self) -> None:
        """TC-UT-PF-038: '/abs/with\\x00null' is rejected by _validate_absolute."""
        # Reach into the validator helper directly because os.environ
        # rejects NUL bytes before the env-var fallback path runs.
        with pytest.raises(BakufuConfigError) as excinfo:
            data_dir._validate_absolute("/abs/with\x00null")  # pyright: ignore[reportPrivateUsage]
        assert excinfo.value.msg_id == "MSG-PF-001"
        assert "NUL byte" in excinfo.value.message


class TestDotDotSegmentRejected:
    """TC-UT-PF-039: '..' path component raises (path-traversal vector)."""

    def test_dot_dot_in_path_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-PF-039: '/abs/../escape' is rejected."""
        monkeypatch.setenv("BAKUFU_DATA_DIR", "/abs/../escape")
        with pytest.raises(BakufuConfigError) as excinfo:
            data_dir.resolve()
        assert excinfo.value.msg_id == "MSG-PF-001"
        assert "'..' segment" in excinfo.value.message


class TestSingletonCache:
    """TC-UT-PF-040: resolve() is O(1) on subsequent calls."""

    def test_second_call_returns_cached_value(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-040: env-var change after first call is ignored until reset."""
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        first = data_dir.resolve()
        # Mutate env after the cache is filled — second call should still
        # return the same Path object.
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path / "different"))
        second = data_dir.resolve()
        assert first == second

    def test_reset_clears_cache(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """TC-UT-PF-040: data_dir.reset() forces a fresh resolution."""
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        first = data_dir.resolve()
        data_dir.reset()
        new_path = tmp_path / "after-reset"
        new_path.mkdir()
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(new_path))
        second = data_dir.resolve()
        assert first != second
        assert second == new_path.resolve()
