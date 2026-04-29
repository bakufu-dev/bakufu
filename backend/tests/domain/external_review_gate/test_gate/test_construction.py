"""ExternalReviewGate construction tests (TC-UT-GT-001 / 002 / 012).

Per ``docs/features/external-review-gate/test-design.md`` §Gate 構築.
構築デフォルト値、4つの ReviewDecision 再構成ケース、frozen + 構造
的等価性、extra='forbid' をカバーする。
"""

from __future__ import annotations

import unicodedata
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.external_review_gate import ExternalReviewGate
from bakufu.domain.value_objects import ReviewDecision
from pydantic import ValidationError

from tests.factories.external_review_gate import (
    is_synthetic,
    make_approved_gate,
    make_cancelled_gate,
    make_gate,
    make_rejected_gate,
)


# ---------------------------------------------------------------------------
# TC-UT-GT-001: デフォルト値での構築
# ---------------------------------------------------------------------------
class TestGateDefaults:
    """TC-UT-GT-001: ファクトリーデフォルト Gate は構造的に PENDING + 空."""

    def test_default_gate_is_pending_with_empty_state(self) -> None:
        """デフォルト値: decision=PENDING, audit_trail=[],
        feedback_text='', decided_at=None."""
        gate = make_gate()
        assert gate.decision == ReviewDecision.PENDING
        assert gate.audit_trail == []
        assert gate.feedback_text == ""
        assert gate.decided_at is None

    def test_factory_marks_instance_synthetic(self) -> None:
        """ファクトリー出力は is_synthetic() に登録される."""
        gate = make_gate()
        assert is_synthetic(gate)


# ---------------------------------------------------------------------------
# TC-UT-GT-002: 4つの ReviewDecision 値全てへの再構成
# ---------------------------------------------------------------------------
class TestRehydrateAllDecisions:
    """TC-UT-GT-002: 4つの ReviewDecision 値それぞれが正常に構築される.

    リポジトリ再構成は永続化された判定値を全て復元できなければならない。
    終了状態（APPROVED / REJECTED / CANCELLED）は一貫性不変量に従い
    non-None decided_at が必要。PENDING は decided_at is None が必要。
    """

    def test_pending_constructs(self) -> None:
        assert make_gate().decision == ReviewDecision.PENDING

    def test_approved_constructs_with_decided_at(self) -> None:
        gate = make_approved_gate()
        assert gate.decision == ReviewDecision.APPROVED
        assert gate.decided_at is not None

    def test_rejected_constructs_with_decided_at(self) -> None:
        gate = make_rejected_gate()
        assert gate.decision == ReviewDecision.REJECTED
        assert gate.decided_at is not None

    def test_cancelled_constructs_with_decided_at(self) -> None:
        gate = make_cancelled_gate()
        assert gate.decision == ReviewDecision.CANCELLED
        assert gate.decided_at is not None


# ---------------------------------------------------------------------------
# TC-UT-GT-012: frozen + 構造的等価性 + ハッシュ可能
# ---------------------------------------------------------------------------
class TestFrozenStructuralEquality:
    """TC-UT-GT-012: 同じ属性を持つ Gate は ``==`` である."""

    def test_same_attributes_compare_equal(self) -> None:
        """同じ属性を持つ 2 つの Gate インスタンスは ``==`` である."""
        common_id = uuid4()
        common_task = uuid4()
        common_stage = uuid4()
        common_reviewer = uuid4()
        ts = datetime(9999, 1, 1, 0, 0, 0, tzinfo=UTC)
        # 同じ Deliverable を再利用して、両 Gate が同じスナップショットを共有
        # 　等価性はスナップショットの等価性が必須
        from tests.factories.task import make_deliverable

        snapshot = make_deliverable()
        a = make_gate(
            gate_id=common_id,
            task_id=common_task,
            stage_id=common_stage,
            reviewer_id=common_reviewer,
            deliverable_snapshot=snapshot,
            created_at=ts,
        )
        b = make_gate(
            gate_id=common_id,
            task_id=common_task,
            stage_id=common_stage,
            reviewer_id=common_reviewer,
            deliverable_snapshot=snapshot,
            created_at=ts,
        )
        assert a == b


# ---------------------------------------------------------------------------
# extra='forbid' は未知フィールドを拒否
# ---------------------------------------------------------------------------
class TestExtraForbid:
    """構築時の未知フィールドは拒否される."""

    def test_unknown_field_rejected_via_model_validate(self) -> None:
        """ExternalReviewGate.model_validate({..., 'unknown': 'x'})
        は例外を発生させる."""
        from tests.factories.task import make_deliverable

        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            ExternalReviewGate.model_validate(
                {
                    "id": uuid4(),
                    "task_id": uuid4(),
                    "stage_id": uuid4(),
                    "deliverable_snapshot": make_deliverable(),
                    "reviewer_id": uuid4(),
                    "created_at": now,
                    "unknown_field": "should-be-rejected",
                }
            )


# ---------------------------------------------------------------------------
# Frozen インスタンス — 直接属性割り当ては拒否
# ---------------------------------------------------------------------------
class TestFrozenInstance:
    """Frozen Pydantic モデルの gate.<attr> = value は例外を発生させる."""

    def test_decision_assignment_rejected(self) -> None:
        gate = make_gate()
        with pytest.raises(ValidationError):
            gate.decision = ReviewDecision.APPROVED  # pyright: ignore[reportAttributeAccessIssue]

    def test_audit_trail_assignment_rejected(self) -> None:
        gate = make_gate()
        with pytest.raises(ValidationError):
            gate.audit_trail = []  # pyright: ignore[reportAttributeAccessIssue]

    def test_deliverable_snapshot_assignment_rejected(self) -> None:
        """§確定 D スナップショット frozen レイヤー（三重防御の一部）."""
        from tests.factories.task import make_deliverable

        gate = make_gate()
        with pytest.raises(ValidationError):
            gate.deliverable_snapshot = make_deliverable()  # pyright: ignore[reportAttributeAccessIssue]


# ---------------------------------------------------------------------------
# 型エラーは pydantic.ValidationError として発生（§確定 I）
# ---------------------------------------------------------------------------
class TestTypeErrorsRaisePydanticValidationError:
    """型関連の失敗は pydantic.ValidationError を使用（kind 概念なし）.

    §確定 I 契約: 構造的/フィールド型エラーは純粋な Pydantic
    検証エラー。5つの ExternalReviewGateInvariantViolation
    の種別のみがアグリゲートの不変量によって発行される。
    """

    def test_naive_created_at_rejected(self) -> None:
        """タイムゾーンなし created_at は拒否される."""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            make_gate(created_at=naive)

    def test_naive_decided_at_rejected(self) -> None:
        """タイムゾーンなし decided_at は設定時に拒否される."""
        naive = datetime.now()
        with pytest.raises(ValidationError):
            make_gate(decision=ReviewDecision.APPROVED, decided_at=naive)


# ---------------------------------------------------------------------------
# feedback_text NFC 正規化（§確定 F）
# ---------------------------------------------------------------------------
class TestFeedbackTextNormalization:
    """feedback_text は NFC 正規化されるが、ストリップは行われない."""

    def test_leading_whitespace_preserved(self) -> None:
        """CEO インデント スタイルは正規化で保持される（ストリップなし）."""
        raw = "> 引用文\n  続き行\n"
        gate = make_gate(feedback_text=raw)
        assert gate.feedback_text == unicodedata.normalize("NFC", raw)
        assert gate.feedback_text.startswith(">")
        assert gate.feedback_text.endswith("\n")
