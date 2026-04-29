"""Deliverable / Attachment VO + enum テスト.

TC-UT-TS-012 / 013 / 036 / 037 ── Task が積み上げる値オブジェクト群と、
ライフサイクルとエラー分類を駆動する 2 つの ``StrEnum``。

Attachment の 6 段階サニタイズパイプラインはセル単位で網羅する ──
任意の 1 ルールへのリグレッションが「filename validation broken」のような
汎用一括失敗ではなく名前付きの単独失敗として顕在化するように。

``docs/features/task/test-design.md`` 準拠。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.value_objects import (
    Deliverable,
    LLMErrorKind,
    TaskStatus,
)
from pydantic import ValidationError

from tests.factories.task import make_attachment, make_deliverable

# 複数のケースで使い回す canonical な妥当 sha256。
_VALID_SHA = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


# ---------------------------------------------------------------------------
# TC-UT-TS-012: Deliverable 構築 + frozen + body_markdown キャップ
# ---------------------------------------------------------------------------
class TestDeliverableConstruction:
    """TC-UT-TS-012: Deliverable VO は妥当値で構築でき、過大 body は拒絶する。"""

    def test_default_deliverable_constructs(self) -> None:
        """ファクトリ既定の Deliverable は空の attachments と aware な committed_at を持つ。"""
        d = make_deliverable()
        assert d.attachments == []
        assert d.committed_at.tzinfo is not None

    def test_deliverable_is_frozen(self) -> None:
        """Deliverable への直接の属性代入は拒絶される。"""
        d = make_deliverable()
        with pytest.raises(ValidationError):
            d.body_markdown = "mutated"  # pyright: ignore[reportAttributeAccessIssue]

    def test_body_markdown_at_max_length_accepted(self) -> None:
        """1,000,000 文字の body_markdown はキャップ上限で受理される。"""
        body = "x" * 1_000_000
        d = make_deliverable(body_markdown=body)
        assert len(d.body_markdown) == 1_000_000

    def test_body_markdown_over_max_length_rejected(self) -> None:
        """1,000,001 文字の body_markdown はキャップ超過で例外発火。"""
        body = "x" * 1_000_001
        with pytest.raises(ValidationError):
            make_deliverable(body_markdown=body)

    def test_naive_committed_at_rejected(self) -> None:
        """tz 情報なしの ``committed_at`` は拒絶される。"""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            Deliverable(
                stage_id=uuid4(),
                body_markdown="",
                attachments=[],
                committed_by=uuid4(),
                committed_at=naive,
            )


# ---------------------------------------------------------------------------
# TC-UT-TS-013: Attachment 6 段階 sanitize + sha256 + mime + size
# ---------------------------------------------------------------------------
class TestAttachmentSha256:
    """TC-UT-TS-013 step 0: sha256 = 64 桁の小文字 hex。"""

    def test_64_hex_lowercase_accepted(self) -> None:
        """正常系の canonical な sha256。"""
        a = make_attachment(sha256=_VALID_SHA)
        assert a.sha256 == _VALID_SHA

    def test_63_chars_rejected(self) -> None:
        """63 文字 (1 文字足りない) digest は拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(sha256=_VALID_SHA[:-1])

    def test_uppercase_rejected(self) -> None:
        """大小混在 hex は拒絶される (正規表現は小文字のみ)。"""
        mixed = "0123456789ABCDEF" + _VALID_SHA[16:]
        with pytest.raises(ValidationError):
            make_attachment(sha256=mixed)

    def test_non_hex_rejected(self) -> None:
        """正しい長さでも非 hex 文字はパターンに失敗する。"""
        bogus = "z" * 64
        with pytest.raises(ValidationError):
            make_attachment(sha256=bogus)


class TestAttachmentFilenameSanitization:
    """TC-UT-TS-013: filename 6 段階サニタイズパイプライン。

    各ステップの拒絶ルールに専用テストを置く ── リグレッションが
    汎用 "filename validation broken" 一括失敗ではなく、明確なラベル付き
    単独失敗として表面化するように。
    """

    # Step 1-2: NFC + 長さ [1, 255]
    def test_empty_filename_rejected(self) -> None:
        """長さ 0 は [1, 255] バンドに失敗する。"""
        with pytest.raises(ValidationError):
            make_attachment(filename="")

    def test_256_char_filename_rejected(self) -> None:
        """長さ 256 はキャップ超過。"""
        with pytest.raises(ValidationError):
            make_attachment(filename="a" * 256)

    def test_255_char_filename_accepted(self) -> None:
        """長さ 255 はキャップ上限で受理される。"""
        a = make_attachment(filename="a" * 255)
        assert len(a.filename) == 255

    # Step 3: 拒絶文字 (パス区切り、NUL、制御文字)
    @pytest.mark.parametrize(
        "bad",
        ["a/b.txt", "a\\b.txt", "name\x00.png", "name\x01.png", "name\x7f.png"],
        ids=["forward_slash", "back_slash", "null_byte", "control_char", "del_char"],
    )
    def test_rejected_characters(self, bad: str) -> None:
        """パス区切り / NUL / ASCII 制御文字は拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(filename=bad)

    # Step 4: 拒絶シーケンス
    def test_dot_dot_path_traversal_rejected(self) -> None:
        """name 中の任意箇所にある ``..`` は拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(filename="..hidden.png")

    def test_leading_dot_rejected(self) -> None:
        """先頭が ``.`` の隠しファイルは拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(filename=".hidden.png")

    def test_trailing_dot_rejected(self) -> None:
        """末尾の ``.`` (Windows 拡張子トリック) は拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(filename="file.png.")

    def test_leading_whitespace_rejected(self) -> None:
        """先頭空白は拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(filename=" file.png")

    def test_colon_rejected(self) -> None:
        """``:`` (Windows ADS / ドライブレター) は拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(filename="file:stream.png")

    # Step 5: Windows 予約デバイス名
    @pytest.mark.parametrize(
        "reserved",
        ["CON", "PRN", "AUX", "NUL", "COM1.txt", "LPT9.bin", "con.png", "Com2.bin"],
        ids=[
            "CON_bare",
            "PRN_bare",
            "AUX_bare",
            "NUL_bare",
            "COM1_ext",
            "LPT9_ext",
            "lower_con_ext",
            "mixed_com_ext",
        ],
    )
    def test_windows_reserved_names_rejected(self, reserved: str) -> None:
        """Windows 予約デバイス名は拡張子の有無を問わず拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(filename=reserved)

    # Step 6: basename ラウンドトリップ
    def test_path_component_rejected_via_basename_check(self) -> None:
        """パス形状の name は basename ラウンドトリップに失敗する。"""
        # ``a/b.txt`` は step 3 で既に検出されるが、各種区切りを埋め込んだ
        # ``foo/bar`` 形のパスは step 6 で失敗する。
        # 実用上はあらゆるパス形状が step 3 で拾われ、step 6 は防御的な
        # ダブルチェック ── したがってアサート形は ValidationError が
        # 発火しさえすれば任意の段階で拒絶されたとみなして良い。
        with pytest.raises(ValidationError):
            make_attachment(filename="dir/file.png")


class TestAttachmentMimeWhitelist:
    """TC-UT-TS-013: mime_type ホワイトリストは text/html と text/csv を拒絶。"""

    @pytest.mark.parametrize(
        "mime",
        [
            "text/markdown",
            "text/plain",
            "application/json",
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/webp",
            "application/octet-stream",
        ],
    )
    def test_whitelisted_mime_accepted(self, mime: str) -> None:
        """ホワイトリスト 8 種の MIME 全てで構築に成功する。"""
        a = make_attachment(mime_type=mime)
        assert a.mime_type == mime

    @pytest.mark.parametrize(
        "mime",
        ["text/html", "text/csv", "application/x-shellscript", ""],
        ids=["text_html", "text_csv", "shell_script", "empty"],
    )
    def test_non_whitelisted_mime_rejected(self, mime: str) -> None:
        """ホワイトリスト外の MIME は拒絶される ── XSS / CSV-injection 防御。"""
        with pytest.raises(ValidationError):
            make_attachment(mime_type=mime)


class TestAttachmentSizeBytes:
    """TC-UT-TS-013: size_bytes ∈ [0, 10 MiB]。"""

    def test_zero_bytes_accepted(self) -> None:
        """空の attachment (0 byte) は受理される。"""
        a = make_attachment(size_bytes=0)
        assert a.size_bytes == 0

    def test_at_max_accepted(self) -> None:
        """ちょうど 10 MiB はキャップ上限で受理される。"""
        a = make_attachment(size_bytes=10 * 1024 * 1024)
        assert a.size_bytes == 10 * 1024 * 1024

    def test_over_max_rejected(self) -> None:
        """10 MiB + 1 byte はキャップ超過。"""
        with pytest.raises(ValidationError):
            make_attachment(size_bytes=10 * 1024 * 1024 + 1)

    def test_negative_rejected(self) -> None:
        """負のサイズは拒絶される。"""
        with pytest.raises(ValidationError):
            make_attachment(size_bytes=-1)


class TestAttachmentFrozen:
    """Attachment は frozen ── 直接の属性代入は拒絶される。"""

    def test_size_bytes_assignment_rejected(self) -> None:
        a = make_attachment()
        with pytest.raises(ValidationError):
            a.size_bytes = 0  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# TC-UT-TS-036: TaskStatus enum 値
# ---------------------------------------------------------------------------
class TestTaskStatusEnum:
    """TC-UT-TS-036: StrEnum 6 値、生文字列との等価性。"""

    def test_six_values(self) -> None:
        """TaskStatus メンバはちょうど 6 個。"""
        members = list(TaskStatus)
        assert len(members) == 6

    def test_str_enum_equality(self) -> None:
        """StrEnum メンバはその文字列値と等価比較される。"""
        assert TaskStatus.PENDING == "PENDING"
        assert TaskStatus.IN_PROGRESS == "IN_PROGRESS"
        assert TaskStatus.AWAITING_EXTERNAL_REVIEW == "AWAITING_EXTERNAL_REVIEW"
        assert TaskStatus.BLOCKED == "BLOCKED"
        assert TaskStatus.DONE == "DONE"
        assert TaskStatus.CANCELLED == "CANCELLED"


# ---------------------------------------------------------------------------
# TC-UT-TS-037: LLMErrorKind enum 値
# ---------------------------------------------------------------------------
class TestLLMErrorKindEnum:
    """TC-UT-TS-037: LLM-Adapter 分類のための StrEnum 5 値。"""

    def test_five_values(self) -> None:
        """LLMErrorKind メンバはちょうど 5 個。"""
        members = list(LLMErrorKind)
        assert len(members) == 5

    def test_str_enum_equality(self) -> None:
        """StrEnum メンバはその文字列値と等価比較される。"""
        assert LLMErrorKind.SESSION_LOST == "SESSION_LOST"
        assert LLMErrorKind.RATE_LIMITED == "RATE_LIMITED"
        assert LLMErrorKind.AUTH_EXPIRED == "AUTH_EXPIRED"
        assert LLMErrorKind.TIMEOUT == "TIMEOUT"
        assert LLMErrorKind.UNKNOWN == "UNKNOWN"


# ---------------------------------------------------------------------------
# サニティ: Deliverable は Attachment を運び、ラウンドトリップに耐える
# ---------------------------------------------------------------------------
class TestDeliverableWithAttachments:
    """attachments を持つ Deliverable はそのままモデルに伝搬する。"""

    def test_attachments_preserved(self) -> None:
        """attachments リストは Deliverable で逐字保持される。"""
        a = make_attachment()
        d = Deliverable(
            stage_id=uuid4(),
            body_markdown="# notes",
            attachments=[a],
            committed_by=uuid4(),
            committed_at=datetime.now(UTC),
        )
        assert d.attachments == [a]

    def test_make_attachment_synthetic(self) -> None:
        """ファクトリの :func:`is_synthetic` フラグは新規構築 attachment で発火する。"""
        from tests.factories.task import is_synthetic

        a = make_attachment()
        assert is_synthetic(a)
