"""ExternalReviewGate ステートマシンテスト (TC-UT-GT-003〜006, 013〜015).

``docs/features/external-review-gate/test-design.md`` 準拠。
§確定 A の 4x4 = **16 セル分岐マトリクス** を 3 つの直交視点で検証する:

1. **7 ✓ セル**: 許可遷移ごとに正常系ケースを 1 件
   (PENDING approve / reject / cancel + record_view 経由の 4 self-loop)。
2. **9 ✗ セル**: APPROVED/REJECTED/CANCELLED x approve/reject/cancel の
   parametrize で全網羅 → ``decision_already_decided`` (MSG-GT-001)。
3. **§確定 G 冪等性なし**: 同一 owner + 同一時刻 = 監査エントリ 2 件
   (監査要件: 誰がいつ何度見たか)。

§確定 B (ステートマシンテーブルロック) は 7 件サイズチェック +
``MappingProxyType`` setitem 拒絶で検証。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate import ExternalReviewGate
from bakufu.domain.external_review_gate.state_machine import (
    TRANSITIONS,
    GateAction,
)
from bakufu.domain.value_objects import (
    AuditAction,
    ReviewDecision,
)

from tests.factories.external_review_gate import (
    make_approved_gate,
    make_cancelled_gate,
    make_gate,
    make_rejected_gate,
)

# 全 4 アクション名 ── ExternalReviewGate のメソッド名と 1:1 対応 (§確定 A)。
_ALL_ACTIONS: list[GateAction] = ["approve", "reject", "cancel", "record_view"]

# 16 セルマトリクスのための全 4 decision 値。
_ALL_DECISIONS: list[ReviewDecision] = list(ReviewDecision)

# PENDING 限定の 3 アクション (terminal で発火)。
_PENDING_ONLY_ACTIONS: list[GateAction] = ["approve", "reject", "cancel"]


def _next_ts(gate: ExternalReviewGate) -> datetime:
    """``decided_at`` / ``viewed_at`` 用に厳密に未来の UTC タイムスタンプを返す。"""
    base = gate.decided_at if gate.decided_at is not None else gate.created_at
    return base + timedelta(seconds=1)


def _invoke_action(gate: ExternalReviewGate, action: GateAction) -> ExternalReviewGate:
    """``gate`` 上に ``action`` をディスパッチする (使い捨ての妥当な引数を渡す)。"""
    ts = _next_ts(gate)
    if action == "approve":
        return gate.approve(uuid4(), "synthetic approve comment", decided_at=ts)
    if action == "reject":
        return gate.reject(uuid4(), "synthetic reject comment", decided_at=ts)
    if action == "cancel":
        return gate.cancel(uuid4(), "synthetic cancel reason", decided_at=ts)
    # record_view
    return gate.record_view(uuid4(), viewed_at=ts)


def _make_gate_in_decision(decision: ReviewDecision) -> ExternalReviewGate:
    """指定の decision 状態にある Gate を、対応するファクトリで構築する。"""
    if decision == ReviewDecision.PENDING:
        return make_gate()
    if decision == ReviewDecision.APPROVED:
        return make_approved_gate()
    if decision == ReviewDecision.REJECTED:
        return make_rejected_gate()
    return make_cancelled_gate()


# ---------------------------------------------------------------------------
# §確定 B: ステートマシン TABLE 形状 + 不変性 (TC-UT-GT-014)
# ---------------------------------------------------------------------------
class TestStateMachineTableLocked:
    """TC-UT-GT-014: TRANSITIONS は 7 件で変更不可."""

    def test_table_size_is_seven(self) -> None:
        """§確定 A の分岐テーブルは許可遷移 7 件を凍結する."""
        assert len(TRANSITIONS) == 7, (
            f"[FAIL] state machine table size drifted: got {len(TRANSITIONS)}, expected 7.\n"
            f"Next: docs/features/external-review-gate/detailed-design.md §確定 A "
            f"freezes 7 transitions; editing state_machine.py without updating "
            f"the design is a contract break."
        )

    def test_table_setitem_rejected_at_runtime(self) -> None:
        """TRANSITIONS[k] = v は TypeError を発する
        (MappingProxyType ロック)."""
        with pytest.raises(TypeError):
            TRANSITIONS[(ReviewDecision.APPROVED, "approve")] = ReviewDecision.PENDING  # pyright: ignore[reportIndexIssue]


# ---------------------------------------------------------------------------
# 許可遷移 7 件 ── ✓ セルごとの正常系ケース
# ---------------------------------------------------------------------------
class TestSevenAllowedTransitions:
    """TC-UT-GT-003 / 004 / 006 / 013 ── 分岐テーブルの ✓ セル 7 件。"""

    # PENDING → APPROVED via approve
    def test_approve_pending_to_approved(self) -> None:
        """TC-UT-GT-003: PENDING に対する approve は APPROVED へ遷移."""
        gate = make_gate()
        ts = _next_ts(gate)
        out = gate.approve(uuid4(), "looks good", decided_at=ts)
        assert out.decision == ReviewDecision.APPROVED
        assert out.decided_at == ts
        assert out.feedback_text == "looks good"
        # 監査証跡: APPROVED エントリが 1 件追加
        assert len(out.audit_trail) == len(gate.audit_trail) + 1
        assert out.audit_trail[-1].action == AuditAction.APPROVED
        # 元の Gate は不変（frozen + pre-validate）
        assert gate.decision == ReviewDecision.PENDING

    # PENDING → REJECTED via reject
    def test_reject_pending_to_rejected(self) -> None:
        """TC-UT-GT-004: PENDING に対する reject は REJECTED へ遷移."""
        gate = make_gate()
        ts = _next_ts(gate)
        out = gate.reject(uuid4(), "needs revision", decided_at=ts)
        assert out.decision == ReviewDecision.REJECTED
        assert out.decided_at == ts
        assert out.feedback_text == "needs revision"
        assert out.audit_trail[-1].action == AuditAction.REJECTED

    # PENDING → CANCELLED via cancel
    def test_cancel_pending_to_cancelled(self) -> None:
        """TC-UT-GT-013: PENDING に対する cancel は CANCELLED へ遷移."""
        gate = make_gate()
        ts = _next_ts(gate)
        out = gate.cancel(uuid4(), "directive withdrawn", decided_at=ts)
        assert out.decision == ReviewDecision.CANCELLED
        assert out.decided_at == ts
        assert out.feedback_text == "directive withdrawn"
        assert out.audit_trail[-1].action == AuditAction.CANCELLED

    # 4 record_view self-loop ── 各 decision ごとに 1 件
    @pytest.mark.parametrize(
        "decision",
        list(ReviewDecision),
        ids=lambda d: d.value,
    )
    def test_record_view_self_loop_in_each_state(self, decision: ReviewDecision) -> None:
        """TC-UT-GT-006: record_view は全状態で self-loop となる."""
        gate = _make_gate_in_decision(decision)
        ts = _next_ts(gate)
        out = gate.record_view(uuid4(), viewed_at=ts)
        assert out.decision == decision  # 状態は変化しない
        # decided_at は変化しない（record_view は純粋な監査操作）
        assert out.decided_at == gate.decided_at
        assert out.feedback_text == gate.feedback_text
        # 監査証跡: VIEWED エントリが 1 件追加
        assert len(out.audit_trail) == len(gate.audit_trail) + 1
        assert out.audit_trail[-1].action == AuditAction.VIEWED


# ---------------------------------------------------------------------------
# TC-UT-GT-005: 9 ✗ セル (decision_already_decided)
# ---------------------------------------------------------------------------
class TestDecisionAlreadyDecidedRejection:
    """9 ✗ セル: APPROVED/REJECTED/CANCELLED に対する approve/reject/cancel
    → MSG-GT-001。

    16 セルマトリクスは 7 ✓ + 9 ✗ に分かれる。✗ セルはいずれも PENDING
    限定アクションを非 PENDING な Gate に投げるケース。
    decision_already_decided が発火し（MSG-GT-001）、allowed_actions
    ヒントが record_view を指す。
    """

    @pytest.mark.parametrize(
        "decision",
        [ReviewDecision.APPROVED, ReviewDecision.REJECTED, ReviewDecision.CANCELLED],
        ids=lambda d: d.value,
    )
    @pytest.mark.parametrize(
        "action",
        _PENDING_ONLY_ACTIONS,
        ids=lambda a: a,
    )
    def test_pending_only_action_on_terminal_raises(
        self,
        decision: ReviewDecision,
        action: GateAction,
    ) -> None:
        """各 (terminal decision, PENDING 限定 action) で
        decision_already_decided が発火."""
        gate = _make_gate_in_decision(decision)
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            _invoke_action(gate, action)
        assert exc_info.value.kind == "decision_already_decided"
        # detail には allowed_actions リストが現れる。terminal decision
        # から正当な唯一のアクションは record_view。MSG-GT-001 自体は
        # "issue a new directive" ヒントで運用者を誘導。構造化された
        # allowed_actions は detail に置く（アプリケーション層の
        # エラーレポータが消費）。
        allowed = exc_info.value.detail.get("allowed_actions")
        assert allowed == ["record_view"], (
            f"[FAIL] terminal Gate must list ['record_view'] as the only "
            f"allowed action; got {allowed!r}"
        )


# ---------------------------------------------------------------------------
# TC-UT-GT-006 (補強): record_view 冪等性なし (§確定 G)
# ---------------------------------------------------------------------------
class TestRecordViewIsNotIdempotent:
    """§確定 G: 同一 owner + 同一 timestamp = 監査エントリ 2 件.

    監査要件は「誰がいつ何度見たか」。重複折りたたみは監査証跡が保持
    すべき頻度シグナル自体を捨ててしまう。
    """

    def test_same_owner_same_time_appends_twice(self) -> None:
        """同一 owner + 同一時刻の record_view 2 回 → 別エントリ 2 件."""
        gate = make_gate()
        owner = uuid4()
        ts = datetime(2026, 4, 28, 14, 0, 0, tzinfo=UTC)
        once = gate.record_view(owner, viewed_at=ts)
        twice = once.record_view(owner, viewed_at=ts)

        assert len(once.audit_trail) == 1
        assert len(twice.audit_trail) == 2
        # 両エントリは同一 actor + occurred_at を持つが、id は別
        # （_rebuild_with_state 内の uuid4 由来）
        e1, e2 = twice.audit_trail
        assert e1.actor_id == e2.actor_id == owner
        assert e1.occurred_at == e2.occurred_at == ts
        assert e1.id != e2.id

    def test_three_views_record_three_entries(self) -> None:
        """3 連続 view で監査エントリは 3 件積まれる."""
        gate = make_gate()
        viewer = uuid4()
        for _ in range(3):
            gate = gate.record_view(viewer, viewed_at=_next_ts(gate))
        assert len(gate.audit_trail) == 3
        assert all(e.action == AuditAction.VIEWED for e in gate.audit_trail)

    def test_record_view_preserves_decision_and_decided_at(self) -> None:
        """record_view は decision / decided_at / feedback_text
        を変更しない."""
        gate = make_approved_gate(feedback_text="approved!")
        before_decision = gate.decision
        before_decided_at = gate.decided_at
        before_feedback = gate.feedback_text

        out = gate.record_view(uuid4(), viewed_at=_next_ts(gate))

        assert out.decision == before_decision
        assert out.decided_at == before_decided_at
        assert out.feedback_text == before_feedback


# ---------------------------------------------------------------------------
# TC-UT-GT-015: pre-validate 失敗時に元 Gate は不変 (§確定 E)
# ---------------------------------------------------------------------------
class TestPreValidateLeavesSourceUnchanged:
    """TC-UT-GT-015: 失敗した behavior 呼び出しは元 Gate を変更しない.

    §確定 E の pre-validate rebuild 経路は、behavior が新 Gate を返す
    か例外を発するかのいずれかで、元インスタンスを部分的に変更しない。
    terminal Gate に decision_already_decided を仕掛けて、元 Gate の全
    属性集合を検査することで保証を確認。
    """

    def test_failed_approve_on_approved_keeps_source_unchanged(self) -> None:
        """APPROVED に対する approve は例外を発し、元 Gate に触れない."""
        gate = make_approved_gate()
        snapshot = gate.model_dump()

        with pytest.raises(ExternalReviewGateInvariantViolation):
            gate.approve(uuid4(), "double-approve", decided_at=_next_ts(gate))

        assert gate.model_dump() == snapshot


# ---------------------------------------------------------------------------
# ライフサイクル統合シナリオ
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """Aggregate 内部「統合」── 複数メソッドのラウンドトリップシナリオ."""

    def test_pending_approve_then_views_then_approve_again_rejected(self) -> None:
        """PENDING → APPROVED → record_view x 2 → 再 approve は例外発火."""
        gate = make_gate()
        viewer_a = uuid4()
        viewer_b = uuid4()

        # Approve
        gate = gate.approve(uuid4(), "all good", decided_at=_next_ts(gate))
        assert gate.decision == ReviewDecision.APPROVED

        # 別々の閲覧者 2 名が view を記録
        gate = gate.record_view(viewer_a, viewed_at=_next_ts(gate))
        gate = gate.record_view(viewer_b, viewed_at=_next_ts(gate))
        assert len(gate.audit_trail) == 3  # 1 APPROVED + 2 VIEWED

        # 再 approve は必ず例外発火。Gate は単一 decision
        with pytest.raises(ExternalReviewGateInvariantViolation) as exc_info:
            gate.approve(uuid4(), "re-approve", decided_at=_next_ts(gate))
        assert exc_info.value.kind == "decision_already_decided"

        # 監査証跡は 3 件のまま不変（失敗 approve はエントリを追加しない。
        # pre-validate が元を保ったため）
        assert len(gate.audit_trail) == 3

    def test_pending_reject_record_view_still_legal(self) -> None:
        """REJECTED の Gate も後続の record_view 監査を受理."""
        gate = make_gate()
        gate = gate.reject(uuid4(), "needs more work", decided_at=_next_ts(gate))
        assert gate.decision == ReviewDecision.REJECTED

        for _ in range(2):
            gate = gate.record_view(uuid4(), viewed_at=_next_ts(gate))
        # 1 REJECTED + 2 VIEWED = 3 件。
        assert len(gate.audit_trail) == 3
        assert gate.audit_trail[0].action == AuditAction.REJECTED
        assert gate.audit_trail[1].action == AuditAction.VIEWED
        assert gate.audit_trail[2].action == AuditAction.VIEWED

    def test_pending_cancel_then_record_view_still_legal(self) -> None:
        """CANCELLED の Gate も後続の record_view 監査を受理.

        §確定 G コンプライアンス観点: 「3 ヶ月前に CANCELLED した
        Gate を再確認した」ログ価値。record_view は全状態で許可。
        """
        gate = make_gate()
        gate = gate.cancel(uuid4(), "withdrawn", decided_at=_next_ts(gate))
        gate = gate.record_view(uuid4(), viewed_at=_next_ts(gate))
        assert gate.decision == ReviewDecision.CANCELLED
        assert len(gate.audit_trail) == 2


# ---------------------------------------------------------------------------
# 到達性確認 ── 各許可遷移は整合性あるフィールドを生成
# ---------------------------------------------------------------------------
class TestAuditTrailGrowsByOnePerCall:
    """全 behavior メソッドは監査エントリをちょうど 1 件追加."""

    @pytest.mark.parametrize(
        "decision",
        list(ReviewDecision),
        ids=lambda d: d.value,
    )
    def test_legal_action_grows_audit_by_one(self, decision: ReviewDecision) -> None:
        """合法 (decision, action) 全てで audit_trail 長は +1 となる."""
        legal_actions: list[GateAction] = [a for (d, a) in TRANSITIONS if d == decision]
        assert legal_actions, f"decision {decision} has zero legal actions"
        for action in legal_actions:
            gate = _make_gate_in_decision(decision)
            before_len = len(gate.audit_trail)
            out = _invoke_action(gate, action)
            assert len(out.audit_trail) == before_len + 1, (
                f"({decision.value}, {action}): audit_trail did not grow by exactly 1."
            )


# GateAction 型使用に対して pyright を満足させるサニティ import
_ = GateAction
