"""DataDirResolver 単体テスト（TC-UT-PF-001 / 002 / 033 / 038 / 039 / 040）。

REQ-PF-001（環境変数が不正な場合の resolve + Fail Fast）と OS 既定の分岐ツリー
をカバーする。Schneier 申し送り #1 物理保証: 相対パス・NUL バイト・``..``
セグメントは起動時に拒否されなければならない。これにより cwd を制御できる
攻撃者であっても bakufu を別ディレクトリへ向けることはできない。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from bakufu.infrastructure.config import data_dir
from bakufu.infrastructure.exceptions import BakufuConfigError


@pytest.fixture(autouse=True)
def _reset_singleton() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """各テストの前にモジュール単位のシングルトンをクリアする。"""
    data_dir.reset()
    yield
    data_dir.reset()


class TestDefaultsForOs:
    """TC-UT-PF-001: BAKUFU_DATA_DIR 未設定時は OS ごとの既定値にフォールバックする。"""

    def test_linux_xdg_data_home_takes_precedence(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-001: Linux で XDG_DATA_HOME が設定されていれば優先される。"""
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        resolved = data_dir.resolve()
        assert resolved == (tmp_path / "bakufu").resolve()

    def test_linux_falls_back_to_home_local_share(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-001: XDG が未設定なら HOME/.local/share/bakufu を使用する。"""
        monkeypatch.setattr("platform.system", lambda: "Linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        resolved = data_dir.resolve()
        assert resolved == (tmp_path / ".local" / "share" / "bakufu").resolve()

    def test_macos_uses_home_local_share(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-001: macOS は POSIX と同じパスを共用する。"""
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        resolved = data_dir.resolve()
        assert resolved == (tmp_path / ".local" / "share" / "bakufu").resolve()

    def test_windows_uses_localappdata(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-001: Windows は %LOCALAPPDATA%\\bakufu を使用する。"""
        monkeypatch.setattr("platform.system", lambda: "Windows")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        resolved = data_dir.resolve()
        assert resolved == (tmp_path / "bakufu").resolve()


class TestRelativePathRejected:
    """TC-UT-PF-002 / 033: 相対パスは MSG-PF-001 で拒否される。"""

    def test_relative_path_raises_bakufu_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-PF-002: ./relative/path は拒否される。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", "./relative/path")
        with pytest.raises(BakufuConfigError) as excinfo:
            data_dir.resolve()
        assert excinfo.value.msg_id == "MSG-PF-001"

    def test_msg_pf_001_wording_starts_with_fail_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TC-UT-PF-033: 文言は '[FAIL] BAKUFU_DATA_DIR must be an absolute path' で始まる。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", "./relative")
        with pytest.raises(BakufuConfigError) as excinfo:
            data_dir.resolve()
        assert excinfo.value.message.startswith("[FAIL] BAKUFU_DATA_DIR must be an absolute path")


class TestNulByteRejected:
    """TC-UT-PF-038: 環境変数中の NUL バイトは拒否される（Schneier #1 パストラバーサル攻撃ベクタ）。

    ``os.environ`` 自体が OS レイヤで NUL バイトを拒否するため、内部バリ
    データを直接呼び出して、悪意のある値が環境変数に到達する *前* に
    bakufu の防御が発火することを確認する。これは文書化された Fail-Fast
    契約に合致する。
    """

    def test_nul_byte_raises(self) -> None:
        """TC-UT-PF-038: '/abs/with\\x00null' は _validate_absolute によって拒否される。"""
        # os.environ が env-var フォールバックパスより先に NUL バイトを
        # 拒否してしまうため、バリデータヘルパーを直接呼び出す。
        with pytest.raises(BakufuConfigError) as excinfo:
            data_dir._validate_absolute("/abs/with\x00null")  # pyright: ignore[reportPrivateUsage]
        assert excinfo.value.msg_id == "MSG-PF-001"
        assert "NUL byte" in excinfo.value.message


class TestDotDotSegmentRejected:
    """TC-UT-PF-039: '..' パス成分は拒否される（パストラバーサル攻撃ベクタ）。"""

    def test_dot_dot_in_path_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-UT-PF-039: '/abs/../escape' は拒否される。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", "/abs/../escape")
        with pytest.raises(BakufuConfigError) as excinfo:
            data_dir.resolve()
        assert excinfo.value.msg_id == "MSG-PF-001"
        assert "'..' segment" in excinfo.value.message


class TestSingletonCache:
    """TC-UT-PF-040: 2 回目以降の resolve() は O(1)。"""

    def test_second_call_returns_cached_value(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """TC-UT-PF-040: 初回呼び出し後の env 変更は reset() するまで無視される。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        first = data_dir.resolve()
        # キャッシュ充填後に env を変更しても、2 回目の呼び出しは同じ
        # Path オブジェクトを返すべき。
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path / "different"))
        second = data_dir.resolve()
        assert first == second

    def test_reset_clears_cache(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """TC-UT-PF-040: data_dir.reset() で再解決を強制できる。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        first = data_dir.resolve()
        data_dir.reset()
        new_path = tmp_path / "after-reset"
        new_path.mkdir()
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(new_path))
        second = data_dir.resolve()
        assert first != second
        assert second == new_path.resolve()
