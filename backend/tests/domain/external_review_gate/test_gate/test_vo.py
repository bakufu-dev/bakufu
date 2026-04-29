"""ExternalReviewGate VO + enum テスト.

カバー範囲:

* AuditEntry VO — frozen, コメント NFC のみノーストリップ,
  occurred_at はタイムゾーン対応。
* ReviewDecision enum — 4 つの StrEnum 値。
* AuditAction enum — VIEWED / APPROVED / REJECTED / CANCELLED
  + 予約済みの Phase-2 管理値が存在。
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.value_objects import (
    AuditAction,
    AuditEntry,
    ReviewDecision,
)
from pydantic import ValidationError

from tests.factories.external_review_gate import (
    is_synthetic,
    make_audit_entry,
)


# ---------------------------------------------------------------------------
# AuditEntry VO
# ---------------------------------------------------------------------------
class TestAuditEntryConstruction:
    """AuditEntry は有効に構築でき、オーバーサイズコメントは拒否."""

    def test_default_audit_entry_constructs(self) -> None:
        """ファクトリーデフォルト AuditEntry は VIEWED アクション +
        タイムゾーン対応 occurred_at を持つ."""
        entry = make_audit_entry()
        assert entry.action == AuditAction.VIEWED
        assert entry.occurred_at.tzinfo is not None

    def test_audit_entry_factory_marks_synthetic(self) -> None:
        """ファクトリー出力は is_synthetic() に登録される."""
        entry = make_audit_entry()
        assert is_synthetic(entry)

    def test_audit_entry_is_frozen(self) -> None:
        """AuditEntry への直接属性割り当ては拒否される."""
        entry = make_audit_entry()
        with pytest.raises(ValidationError):
            entry.comment = "mutated"  # pyright: ignore[reportAttributeAccessIssue]

    def test_comment_at_max_length_accepted(self) -> None:
        """2000 文字コメントは上限であり受け入れられる."""
        comment = "x" * 2000
        entry = make_audit_entry(comment=comment)
        assert len(entry.comment) == 2000

    def test_comment_over_max_length_rejected(self) -> None:
        """2001 文字コメントは上限を超過し例外を発生させる."""
        with pytest.raises(ValidationError):
            make_audit_entry(comment="x" * 2001)

    def test_naive_occurred_at_rejected(self) -> None:
        """タイムゾーンなし occurred_at は拒否される."""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            AuditEntry(
                id=uuid4(),
                actor_id=uuid4(),
                action=AuditAction.VIEWED,
                comment="",
                occurred_at=naive,
            )

    def test_comment_nfc_normalization_no_strip(self) -> None:
        """コメントは NFC 正規化されるが、ストリップは行われない."""
        raw = "  indented quote\n"
        entry = make_audit_entry(comment=raw)
        # NFC 正規化、ストリップなし
        assert entry.comment == unicodedata.normalize("NFC", raw)
        assert entry.comment.startswith("  ")  # 先頭の空白は保持
        assert entry.comment.endswith("\n")  # 末尾の改行は保持


class TestAuditEntryStructuralEquality:
    """同じ属性を持つ AuditEntry インスタンスは ``==`` である."""

    def test_same_attributes_compare_equal(self) -> None:
        """同じ属性を持つ 2 つの AuditEntry は ``==`` である."""
        common_id = uuid4()
        actor = uuid4()
        ts = datetime(9999, 1, 1, 0, 0, 0, tzinfo=UTC)
        a = make_audit_entry(
            entry_id=common_id,
            actor_id=actor,
            action=AuditAction.APPROVED,
            comment="同意します",
            occurred_at=ts,
        )
        b = make_audit_entry(
            entry_id=common_id,
            actor_id=actor,
            action=AuditAction.APPROVED,
            comment="同意します",
            occurred_at=ts,
        )
        assert a == b


# ---------------------------------------------------------------------------
# ReviewDecision enum（4 値）
# ---------------------------------------------------------------------------
class TestReviewDecisionEnum:
    """ReviewDecision は正確に 4 つの StrEnum 値を持つ."""

    def test_four_values(self) -> None:
        """PENDING / APPROVED / REJECTED / CANCELLED — 正確に 4 つ."""
        members = list(ReviewDecision)
        assert len(members) == 4

    def test_str_enum_equality(self) -> None:
        """StrEnum メンバーは文字列値と等しいと比較される."""
        assert ReviewDecision.PENDING == "PENDING"
        assert ReviewDecision.APPROVED == "APPROVED"
        assert ReviewDecision.REJECTED == "REJECTED"
        assert ReviewDecision.CANCELLED == "CANCELLED"


# ---------------------------------------------------------------------------
# AuditAction enum（4 コア + 予約済み Phase-2 値）
# ---------------------------------------------------------------------------
class TestAuditActionEnum:
    """AuditAction は Gate アグリゲートが発行する 4 つのコア状態を持つ."""

    def test_core_actions_present(self) -> None:
        """4 つのコアアクションが存在（VIEWED / APPROVED / REJECTED /
        CANCELLED）."""
        # Gate アグリゲートはちょうどこれら 4 つを発行。Phase 2
        # 管理アクションで enum が拡張される場合もある。
        # 特定の数は固定しないため、テストは enum 追加でも安定。
        assert AuditAction.VIEWED == "VIEWED"
        assert AuditAction.APPROVED == "APPROVED"
        assert AuditAction.REJECTED == "REJECTED"
        assert AuditAction.CANCELLED == "CANCELLED"

    def test_str_enum_equality(self) -> None:
        """StrEnum メンバーは文字列値と等しいと比較される."""
        for member in AuditAction:
            assert member.value == str(member)
