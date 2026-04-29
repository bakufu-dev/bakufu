"""SkillRef.path traversal 防御 H1〜H10 (Confirmation H / TC-UT-AG-038〜044)。

各 ``Test*`` クラスは Hx ルール 1 つをターゲット。
失敗は違反ルールでクラスタリング、Norman / Schneier が
SSRF G1〜G10 に承認した workflow ``test_notify_channel_ssrf.py``
構造をミラーリング。

Aggregate 側パスは ``SkillRef.field_validator`` を通り、
:func:`_validate_skill_path` にデリゲート。
公開サーフェス (コンストラクタ + ``model_validate``) を実行して
オーケストレーター内部の将来のリファクタリングがカバレッジを
静かにドロップしないようにする。オーケストレーター関数は
先頭アンダースコアを持つ (Steve PR #17 命名対称ルール):
実際のクロス機能コンシューマーが到着するまで全パス / Aggregate
ヘルパはモジュールプライベート。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.agent import SkillRef
from bakufu.domain.exceptions import AgentInvariantViolation


def _ref(path: str) -> SkillRef:
    """任意の id/name と与えられた path で SkillRef を構築。"""
    return SkillRef(skill_id=uuid4(), name="test-skill", path=path)


class TestH1NFCNormalization:
    """H1 / TC-UT-AG-038 — path 文字列の NFC 正規化。"""

    def test_decomposed_kana_in_path_is_normalized(self) -> None:
        """H1: path に分解した 'がが' は合成形で保存。"""
        import unicodedata

        composed_filename = "がが.md"
        decomposed_filename = unicodedata.normalize("NFD", composed_filename)
        path = f"bakufu-data/skills/{decomposed_filename}"
        ref = _ref(path)
        assert ref.path == f"bakufu-data/skills/{composed_filename}"


class TestH3ForbiddenChars:
    """H3 / TC-UT-AG-039 — path に禁止: NUL / 制御 / バックスラッシュ。"""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "bakufu-data/skills/foo\\bar.md",  # バックスラッシュ
            "bakufu-data/skills/foo\x00.md",  # NUL
            "bakufu-data/skills/foo\x01.md",  # ASCII 制御
            "bakufu-data/skills/foo\x7f.md",  # DEL
        ],
    )
    def test_forbidden_chars_rejected(self, bad_path: str) -> None:
        """H3: バックスラッシュ / NUL / 制御 / DEL すべて skill_path_invalid を発火。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H3"


class TestH4LeadingChar:
    """H4 / TC-UT-AG-039 — POSIX 絶対 / Windows 絶対 / チルダ 拒否。"""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "/etc/passwd",  # POSIX 絶対
            "~/secret",  # チルダ ホーム展開
            "C:\\Windows\\system32",  # Windows 絶対バックスラッシュ
            "D:/foo/bar",  # Windows 絶対フォワードスラッシュ
        ],
    )
    def test_leading_char_rejected(self, bad_path: str) -> None:
        """H4: 先頭スラッシュ / チルダ / Windows ドライブプレフィックスを発火。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        # path 内のバックスラッシュも H3 をトリップ; H3+H4 ペアから
        # 安定した check 識別子に対する拒否を検証するだけ。
        assert excinfo.value.detail.get("check") in {"H3", "H4"}


class TestH5TraversalSequences:
    """H5 / TC-UT-AG-040 — '..' traversal と周囲空白を拒否。"""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "bakufu-data/skills/../../../etc/passwd",  # 古典的 traversal
            "bakufu-data/skills/sub/../escape",  # 中間パス traversal
            "bakufu-data/skills/legitimate/../../../escape",  # 複数上
            "..",  # 裸の親
            "./relative",  # カレントディレクトリ プレフィックス
            "../escape",  # 親プレフィックス
        ],
    )
    def test_traversal_or_dot_prefix_rejected(self, bad_path: str) -> None:
        """H5: path 内の任意の '..' セグメント は skill_path_invalid を発火。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"

    @pytest.mark.parametrize(
        "bad_path",
        [
            " bakufu-data/skills/file.md",  # 先頭空白
            "bakufu-data/skills/file.md ",  # 末尾空白
        ],
    )
    def test_surrounding_whitespace_rejected(self, bad_path: str) -> None:
        """H5: 先頭または末尾空白は skill_path_invalid を発火。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H5"


class TestH7PrefixEnforcement:
    """H7 / TC-UT-AG-041 — path は 'bakufu-data/skills/<rest>' で開始必須。"""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "other/path/file.md",  # 不正ルート
            "bakufu-data/other/file.md",  # 2 番目セグメント不正
            "skills/file.md",  # 'bakufu-data' 欠落
            "bakufu-data/skills",  # 短すぎ (<rest> なし)
        ],
    )
    def test_wrong_prefix_rejected(self, bad_path: str) -> None:
        """H7: プレフィックスが ('bakufu-data', 'skills') に一致しない場合発火。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H7"


class TestH9WindowsReserved:
    """H9 / TC-UT-AG-043 — Windows 予約デバイス名 (CON / NUL / 等)。"""

    @pytest.mark.parametrize(
        "bad_path",
        [
            "bakufu-data/skills/CON.md",
            "bakufu-data/skills/prn.txt",  # 大文字小文字を区別しない
            "bakufu-data/skills/AUX",  # 拡張子なし
            "bakufu-data/skills/NUL.markdown",
            "bakufu-data/skills/COM1.md",
            "bakufu-data/skills/LPT9.md",
            "bakufu-data/skills/con",  # 裸の小文字
        ],
    )
    def test_windows_reserved_name_rejected(self, bad_path: str) -> None:
        """H9: あらゆる Windows 予約デバイス名 (大文字小文字を区別しない) を発火。"""
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(bad_path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H9"


class TestH10BaseEscape:
    """H10 / TC-UT-AG-042 — 解決パスは BAKUFU_DATA_DIR/skills/ 配下に留まる必須。"""

    def test_unset_bakufu_data_dir_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """H10: 欠落 BAKUFU_DATA_DIR は構造化失敗 (静かなスキップではない)。"""
        monkeypatch.delenv("BAKUFU_DATA_DIR", raising=False)
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref("bakufu-data/skills/sample.md")
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H10"


class TestPathLengthBoundary:
    """H2 / TC-UT-AG-044 — path 長 1〜500 (下限は H4 / 構造で強制)。"""

    def test_500_char_valid_path_succeeds(self) -> None:
        """H2: 構造的に有効な 500 文字 path は構築。"""
        # "bakufu-data/skills/" (19 文字) + (いくつかの余分プレフィックス)
        # + ファイル名を正確に 500 文字に合計。
        prefix = "bakufu-data/skills/"
        remaining = 500 - len(prefix)
        # 'a'*remaining の長いファイル名を使用; H9 stem は 'a'*remaining
        # マイナス拡張子で問題なし (予約名ではない)。
        path = prefix + "a" * remaining
        assert len(path) == 500
        ref = _ref(path)
        assert ref.path == path

    def test_501_char_path_rejected(self) -> None:
        """H2: 501 文字 path は skill_path_invalid (H2) を発火。"""
        prefix = "bakufu-data/skills/"
        remaining = 501 - len(prefix)
        path = prefix + "a" * remaining
        assert len(path) == 501
        with pytest.raises(AgentInvariantViolation) as excinfo:
            _ref(path)
        assert excinfo.value.kind == "skill_path_invalid"
        assert excinfo.value.detail.get("check") == "H2"


class TestValidPathHappyPath:
    """サニティ: 完全に有効な SkillRef.path は構築され正規化で保存。"""

    def test_canonical_path_constructs(self) -> None:
        """Happy path: 'bakufu-data/skills/reviewer.md' は H1〜H10 全部を通る。"""
        ref = _ref("bakufu-data/skills/reviewer.md")
        assert ref.path == "bakufu-data/skills/reviewer.md"

    def test_nested_subdir_constructs(self) -> None:
        """Happy path: skills/ 配下ネストサブディレクトリが許可。"""
        ref = _ref("bakufu-data/skills/sub/sub2/file.md")
        assert ref.path == "bakufu-data/skills/sub/sub2/file.md"
