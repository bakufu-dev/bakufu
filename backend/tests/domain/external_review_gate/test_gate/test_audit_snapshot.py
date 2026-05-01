"""ExternalReviewGate criteria 不変条件テスト.

TC-UT-GT-026 / 027 / 028 — §確定 D' criteria_immutable /
``required_deliverable_criteria`` 正常系・異常系 / 状態遷移後の criteria 引き継ぎ。

test_invariants.py の §確定 D (snapshot_immutable) と完全対称の構造。

Covers:
  TC-UT-GT-026  required_deliverable_criteria 正常系（空・非空タプル）
  TC-UT-GT-027  _validate_criteria_immutable 異常系（MSG-GT-008 + Next: ヒント）
  TC-UT-GT-028  criteria が approve / reject / cancel / record_view 後も引き継がれる

外部 I/O なし。factory および ``_validate_criteria_immutable`` を直接呼び出す。

Issue: #121
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.aggregate_validators import (
    _validate_criteria_immutable,  # pyright: ignore[reportPrivateUsage]
)
from bakufu.domain.value_objects import AcceptanceCriterion

from tests.factories.external_review_gate import make_gate


# ---------------------------------------------------------------------------
# TC-UT-GT-026: required_deliverable_criteria 正常系
# ---------------------------------------------------------------------------
class TestCriteriaConstruction:
    """TC-UT-GT-026: 空・非空タプルの正常系構築（受入基準 16）."""

    def test_empty_criteria_accepted(self) -> None:
        """TC-UT-GT-026a: required_deliverable_criteria=() の Gate が構築できる."""
        gate = make_gate()
        assert gate.required_deliverable_criteria == ()

    def test_single_criterion_accepted(self) -> None:
        """TC-UT-GT-026b: AcceptanceCriterion 1 件 → 構築成功、criterion が保持される."""
        criterion = AcceptanceCriterion(
            id=uuid4(),
            description="成果物が設計書の受入基準を満たすこと",
            required=True,
        )
        gate = make_gate(required_deliverable_criteria=(criterion,))
        assert len(gate.required_deliverable_criteria) == 1
        assert gate.required_deliverable_criteria[0] == criterion

    def test_multiple_criteria_with_mixed_required_flag(self) -> None:
        """TC-UT-GT-026c: required=True / False 混在 3 件 → 全件保持."""
        c1 = AcceptanceCriterion(id=uuid4(), description="テスト通過", required=True)
        c2 = AcceptanceCriterion(id=uuid4(), description="レビュー承認", required=False)
        c3 = AcceptanceCriterion(id=uuid4(), description="CI 緑", required=True)
        gate = make_gate(required_deliverable_criteria=(c1, c2, c3))
        assert len(gate.required_deliverable_criteria) == 3
        assert gate.required_deliverable_criteria[0] == c1
        assert gate.required_deliverable_criteria[1] == c2
        assert gate.required_deliverable_criteria[2] == c3

    def test_criteria_is_tuple_type(self) -> None:
        """TC-UT-GT-026d: criteria フィールドは tuple 型として保持される."""
        c = AcceptanceCriterion(id=uuid4(), description="型確認", required=True)
        gate = make_gate(required_deliverable_criteria=(c,))
        assert isinstance(gate.required_deliverable_criteria, tuple)


# ---------------------------------------------------------------------------
# TC-UT-GT-027: _validate_criteria_immutable 異常系 (MSG-GT-008)
# ---------------------------------------------------------------------------
class TestCriteriaImmutableValidator:
    """TC-UT-GT-027: §確定 D' criteria 不変性バリデータセーフティネット.

    構造的ガードは ``_rebuild_with_state`` の引数集合に
    ``required_deliverable_criteria`` が無いこと。本バリデータはその契約が
    漏れた場合の失敗経路セーフティネット。test_invariants.py の §確定 D と
    完全対称。
    """

    def test_construction_with_no_previous_accepts_empty_criteria(self) -> None:
        """previous=None（構築時）は寛容 ── 空タプルを受理する."""
        _validate_criteria_immutable(None, ())

    def test_construction_with_no_previous_accepts_nonempty_criteria(self) -> None:
        """previous=None（構築時）は寛容 ── 非空タプルも受理する."""
        c = AcceptanceCriterion(id=uuid4(), description="desc", required=True)
        _validate_criteria_immutable(None, (c,))

    def test_same_criteria_passes(self) -> None:
        """同値 criteria はラウンドトリップに耐える（Pydantic frozen の ==）."""
        c = AcceptanceCriterion(id=uuid4(), description="desc", required=True)
        criteria = (c,)
        _validate_criteria_immutable(criteria, criteria)

    def test_different_criteria_raises_criteria_immutable(self) -> None:
        """TC-UT-GT-027: 別 criteria を渡すと kind=criteria_immutable を発火 (MSG-GT-008)."""
        original = (AcceptanceCriterion(id=uuid4(), description="original", required=True),)
        replaced = (AcceptanceCriterion(id=uuid4(), description="replaced", required=False),)
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_criteria_immutable(original, replaced)
        assert exc_info.value.kind == "criteria_immutable"

    def test_msg_gt_008_starts_with_fail(self) -> None:
        """TC-UT-GT-027: MSG-GT-008 の 1 行目が [FAIL] で始まる（§確定 I）."""
        original = (AcceptanceCriterion(id=uuid4(), description="a", required=True),)
        replaced = (AcceptanceCriterion(id=uuid4(), description="b", required=True),)
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_criteria_immutable(original, replaced)
        assert str(exc_info.value).startswith("[FAIL]")

    def test_msg_gt_008_contains_next_hint(self) -> None:
        """TC-UT-GT-027: MSG-GT-008 の 2 行目に Next: ヒントが含まれる（§確定 I）."""
        original = (AcceptanceCriterion(id=uuid4(), description="a", required=True),)
        replaced = (AcceptanceCriterion(id=uuid4(), description="b", required=True),)
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_criteria_immutable(original, replaced)
        assert "Next:" in str(exc_info.value)

    def test_msg_gt_008_contains_frozen_at_gate_creation(self) -> None:
        """TC-UT-GT-027: MSG-GT-008 が 'frozen at Gate creation' ヒントを含む."""
        original = (AcceptanceCriterion(id=uuid4(), description="a", required=True),)
        replaced = (AcceptanceCriterion(id=uuid4(), description="b", required=True),)
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _validate_criteria_immutable(original, replaced)
        assert "frozen at Gate creation" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TC-UT-GT-028: criteria が approve / reject / cancel / record_view 後も引き継がれる
# ---------------------------------------------------------------------------
class TestCriteriaPreservedAfterStateTransitions:
    """TC-UT-GT-028: §確定 D' — _rebuild_with_state が criteria を引数に含まない
    契約の動的確認.

    required=True / False 混在 3 件の criteria を持つ PENDING Gate に対して
    approve / reject / cancel / record_view を実施し、遷移後の Gate の
    ``required_deliverable_criteria`` が元と完全同一（値、順序、required フラグ）で
    あることを物理確認する。MSG-GT-008 が発火しないことも暗黙的に確認する。

    test_invariants.py の TestSnapshotImmutableViaBehaviors と完全対称の構造。
    """

    def _build_criteria(self) -> tuple[AcceptanceCriterion, ...]:
        return (
            AcceptanceCriterion(id=uuid4(), description="設計書の要件を満たす", required=True),
            AcceptanceCriterion(
                id=uuid4(), description="テストケースが全て通過する", required=False
            ),
            AcceptanceCriterion(id=uuid4(), description="レビュアーが承認する", required=True),
        )

    def test_approve_preserves_criteria(self) -> None:
        """TC-UT-GT-028a: approve 後の Gate が元と完全同一の criteria を持つ."""
        criteria = self._build_criteria()
        gate = make_gate(required_deliverable_criteria=criteria)
        approved = gate.approve(uuid4(), "ok", decided_at=datetime.now(UTC))
        assert approved.required_deliverable_criteria == criteria

    def test_reject_preserves_criteria(self) -> None:
        """TC-UT-GT-028b: reject 後の Gate が元と完全同一の criteria を持つ."""
        criteria = self._build_criteria()
        gate = make_gate(required_deliverable_criteria=criteria)
        rejected = gate.reject(uuid4(), "rework needed", decided_at=datetime.now(UTC))
        assert rejected.required_deliverable_criteria == criteria

    def test_cancel_preserves_criteria(self) -> None:
        """TC-UT-GT-028c: cancel 後の Gate が元と完全同一の criteria を持つ."""
        criteria = self._build_criteria()
        gate = make_gate(required_deliverable_criteria=criteria)
        cancelled = gate.cancel(uuid4(), "withdrawn", decided_at=datetime.now(UTC))
        assert cancelled.required_deliverable_criteria == criteria

    def test_record_view_preserves_criteria(self) -> None:
        """TC-UT-GT-028d: record_view 後の Gate が元と完全同一の criteria を持つ."""
        criteria = self._build_criteria()
        gate = make_gate(required_deliverable_criteria=criteria)
        viewed = gate.record_view(uuid4(), viewed_at=datetime.now(UTC))
        assert viewed.required_deliverable_criteria == criteria

    def test_criteria_order_preserved_after_approve(self) -> None:
        """TC-UT-GT-028e: criteria の順序が approve 後も変化しない."""
        criteria = self._build_criteria()
        gate = make_gate(required_deliverable_criteria=criteria)
        approved = gate.approve(uuid4(), "ok", decided_at=datetime.now(UTC))
        for i, (original, rebuilt) in enumerate(
            zip(criteria, approved.required_deliverable_criteria, strict=True)
        ):
            assert original == rebuilt, f"criterion at index {i} changed after approve"

    def test_criteria_required_flags_preserved_after_approve(self) -> None:
        """TC-UT-GT-028f: required フラグが approve 後も変化しない."""
        criteria = self._build_criteria()
        gate = make_gate(required_deliverable_criteria=criteria)
        approved = gate.approve(uuid4(), "ok", decided_at=datetime.now(UTC))
        for original, rebuilt in zip(criteria, approved.required_deliverable_criteria, strict=True):
            assert original.required == rebuilt.required
