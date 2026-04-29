"""DAG invariants 7 種 (REQ-WF-005 / TC-UT-WF-002〜007 / 022 / 023 / 038〜045)。

各 invariant には専用の ``Test*`` クラスを設け、DAG のどの構造的性質が
違反されたかに応じて失敗が集約されるようにしている。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain import workflow as _workflow_module
from bakufu.domain.exceptions import (
    StageInvariantViolation,
    WorkflowInvariantViolation,
)
from bakufu.domain.value_objects import StageKind, TransitionCondition
from bakufu.domain.workflow import Stage

from tests.factories.workflow import make_stage, make_transition, make_workflow

# Workflow のモジュール内 invariant ヘルパは慣習上 private だが、Confirmation F の
# 二重防衛契約のもとでテストから意図的に import する。属性アクセス経由にすることで
# pyright strict を満足させる。
_validate_external_review_notify = _workflow_module._validate_external_review_notify  # pyright: ignore[reportPrivateUsage]
_validate_required_role_non_empty = _workflow_module._validate_required_role_non_empty  # pyright: ignore[reportPrivateUsage]
_validate_dag_reachability = _workflow_module._validate_dag_reachability  # pyright: ignore[reportPrivateUsage]


class TestEntryStageId:
    """REQ-WF-005-① / TC-UT-WF-002 / 038。"""

    def test_unknown_entry_raises_entry_not_in_stages(self) -> None:
        """TC-UT-WF-002: stages 外の entry_stage_id は entry_not_in_stages を起こす。"""
        stage = make_stage()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[stage], entry_stage_id=uuid4())
        assert excinfo.value.kind == "entry_not_in_stages"

    def test_msg_wf_002_includes_entry_stage_id(self) -> None:
        """TC-UT-WF-038: MSG-WF-002 文言が問題の entry_stage_id を含む。"""
        stage = make_stage()
        unknown = uuid4()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[stage], entry_stage_id=unknown)
        assert excinfo.value.message == f"[FAIL] entry_stage_id {unknown} not found in stages"


class TestUnreachableStage:
    """REQ-WF-005-④ / TC-UT-WF-003 / 039 ── BFS 到達可能性。"""

    def test_orphan_stage_raises_unreachable_stage(self) -> None:
        """TC-UT-WF-003: entry から到達不能な stage は unreachable_stage を起こす。"""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()  # orphan, no edges in
        edge = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[edge],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.kind == "unreachable_stage"

    def test_msg_wf_003_lists_unreachable_stage_ids(self) -> None:
        """TC-UT-WF-039: MSG-WF-003 が到達不能 stage の id を含む。"""
        s0 = make_stage()
        s1 = make_stage()
        orphan = make_stage()
        edge = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0, s1, orphan], transitions=[edge], entry_stage_id=s0.id)
        assert str(orphan.id) in excinfo.value.message


class TestSinkStage:
    """REQ-WF-005-⑤ / TC-UT-WF-004 / 040 ── 少なくとも 1 つの sink Stage が存在する。"""

    def test_pure_cycle_raises_no_sink_stage(self) -> None:
        """TC-UT-WF-004: 全ステージが外向辺を持つ（循環）→ no_sink_stage を起こす。"""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e1 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e2 = make_transition(from_stage_id=s1.id, to_stage_id=s2.id)
        e3 = make_transition(from_stage_id=s2.id, to_stage_id=s0.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[e1, e2, e3],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.kind == "no_sink_stage"

    def test_msg_wf_004_starts_with_no_sink_prefix(self) -> None:
        """TC-UT-WF-040: MSG-WF-004 文言が '[FAIL] No sink stage' で始まる。"""
        s0 = make_stage()
        s1 = make_stage()
        e1 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e2 = make_transition(from_stage_id=s1.id, to_stage_id=s0.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0, s1], transitions=[e1, e2], entry_stage_id=s0.id)
        assert excinfo.value.message.startswith("[FAIL] No sink stage")


class TestTransitionDeterminism:
    """REQ-WF-005-③ / TC-UT-WF-005 / 041 ── (from, condition) の一意性。"""

    def test_duplicate_from_condition_raises_transition_duplicate(self) -> None:
        """TC-UT-WF-005: 同じ (from_stage_id, APPROVED) 2 回 → transition_duplicate を起こす。"""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e1 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e2 = make_transition(
            from_stage_id=s0.id, to_stage_id=s2.id, condition=TransitionCondition.APPROVED
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[e1, e2],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.kind == "transition_duplicate"

    def test_msg_wf_005_includes_from_and_condition(self) -> None:
        """TC-UT-WF-041: MSG-WF-005 文言が from_stage と condition を含む。"""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e1 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e2 = make_transition(
            from_stage_id=s0.id, to_stage_id=s2.id, condition=TransitionCondition.APPROVED
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0, s1, s2], transitions=[e1, e2], entry_stage_id=s0.id)
        assert "APPROVED" in excinfo.value.message
        assert str(s0.id) in excinfo.value.message


class TestExternalReviewNotify:
    """REQ-WF-007-② / TC-UT-WF-006a / 006b / 042 ── 二重防衛。"""

    def test_006a_stage_self_path_rejects_empty_notify(self) -> None:
        """TC-UT-WF-006a: Stage 自己バリデータが空の notify_channels を拒否する。

        ``kind=EXTERNAL_REVIEW`` と ``notify_channels=[]`` での構築は、
        aggregate チェックが走る前に Stage 自身の ``model_validator(mode='after')``
        から :class:`StageInvariantViolation` を直接発火させる ──
        二重防衛の Stage 側経路を満たす。
        """
        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(kind=StageKind.EXTERNAL_REVIEW, notify_channels=[])
        assert excinfo.value.kind == "missing_notify"

    def test_006b_aggregate_helper_rejects_empty_notify_via_direct_call(self) -> None:
        """TC-UT-WF-006b: ``_validate_external_review_notify`` が aggregate 違反を直接起こす。

        notify_channels 付き EXTERNAL_REVIEW Stage を構築し（自己バリデータを通過）、
        その後 ``model_construct``（バリデータをスキップ）で再構築することで、
        Stage バリデータが拒否したであろう状態をヘルパに見せる。これにより、
        二系統のコード経路（Stage 自己 vs aggregate ヘルパ）がコードを共有していないことを示す。
        """
        good = make_stage(kind=StageKind.EXTERNAL_REVIEW)
        stage_without_notify = Stage.model_construct(
            id=good.id,
            name=good.name,
            kind=StageKind.EXTERNAL_REVIEW,
            required_role=good.required_role,
            deliverable_template=good.deliverable_template,
            completion_policy=good.completion_policy,
            notify_channels=[],
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_external_review_notify([stage_without_notify])
        assert excinfo.value.kind == "missing_notify_aggregate"

    def test_msg_wf_006_includes_stage_id(self) -> None:
        """TC-UT-WF-042: MSG-WF-006 文言が問題の stage_id を含む。"""
        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(kind=StageKind.EXTERNAL_REVIEW, notify_channels=[])
        assert "EXTERNAL_REVIEW stage" in excinfo.value.message
        assert "must have at least one notify_channel" in excinfo.value.message


class TestRequiredRoleNonEmpty:
    """REQ-WF-007-① / TC-UT-WF-007 / 043 ── required_role が非空。"""

    def test_stage_self_path_rejects_empty_required_role(self) -> None:
        """TC-UT-WF-007: Stage(required_role=frozenset()) は empty_required_role を起こす。"""
        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(required_role=frozenset())
        assert excinfo.value.kind == "empty_required_role"

    def test_msg_wf_007_includes_stage_id(self) -> None:
        """TC-UT-WF-043: MSG-WF-007 文言が問題の stage_id を含む。"""
        with pytest.raises(StageInvariantViolation) as excinfo:
            make_stage(required_role=frozenset())
        assert "required_role must not be empty" in excinfo.value.message

    def test_aggregate_helper_rejects_empty_required_role(self) -> None:
        """`_validate_required_role_non_empty` が空 role セットの迂回 stage を拒否する。"""
        good = make_stage()
        bad = Stage.model_construct(
            id=good.id,
            name=good.name,
            kind=StageKind.WORK,
            required_role=frozenset(),
            deliverable_template=good.deliverable_template,
            completion_policy=good.completion_policy,
            notify_channels=[],
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            _validate_required_role_non_empty([bad])
        assert excinfo.value.kind == "empty_required_role_aggregate"


class TestTransitionIdUnique:
    """REQ-WF-005-② の兄弟 ── 対称な transition_id 重複ガード。

    Steve の PR #16 レビューが、``_validate_stage_id_unique`` は stage id の重複を
    拒否するのに transition id はすり抜けていた非対称を捕捉した。Linus が
    :func:`_validate_transition_id_unique` を追加。これらのテストは aggregate 側の
    挙動を固定し、ギャップが再び開かないようにする。
    """

    def test_duplicate_transition_id_raises_through_aggregate(self) -> None:
        """Aggregate 経路: transition.id を共有する 2 辺は transition_id_duplicate を起こす。

        前提: s0→s1→s2 の 3 ステージ連鎖と APPROVED エッジ 1 本。最初のエッジと
        id を共有しつつ (from, to, condition) が異なる 2 本目を追加する。
        ((from, condition) でキーする) determinism チェックは通過させても、
        aggregate レベルのヘルパはこれを拒否しなければならない。
        """
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e_dup = make_transition(
            transition_id=e0.id,  # 意図的に transition.id を衝突させる
            from_stage_id=s1.id,
            to_stage_id=s2.id,
            condition=TransitionCondition.APPROVED,
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[e0, e_dup],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.kind == "transition_id_duplicate"

    def test_msg_for_duplicate_transition_id_includes_id(self) -> None:
        """メッセージ文言: '[FAIL] Transition id duplicate: <transition_id>'。"""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e_dup = make_transition(
            transition_id=e0.id,
            from_stage_id=s1.id,
            to_stage_id=s2.id,
            condition=TransitionCondition.REJECTED,
        )
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(
                stages=[s0, s1, s2],
                transitions=[e0, e_dup],
                entry_stage_id=s0.id,
            )
        assert excinfo.value.message == f"[FAIL] Transition id duplicate: {e0.id}"


class TestTransitionRefIntegrity:
    """REQ-WF-005-② / TC-UT-WF-022 / 045 ── Transition の参照が既知 Stage を指さねばならない。"""

    def test_transition_to_unknown_stage_raises(self) -> None:
        """TC-UT-WF-022: stages 外の Transition.to_stage_id は transition_ref_invalid を起こす。"""
        s0 = make_stage()
        bad_to = uuid4()
        edge = make_transition(from_stage_id=s0.id, to_stage_id=bad_to)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0], transitions=[edge], entry_stage_id=s0.id)
        assert excinfo.value.kind == "transition_ref_invalid"

    def test_msg_wf_009_includes_from_and_to(self) -> None:
        """TC-UT-WF-045: MSG-WF-009 文言が from / to の stage id を含む。"""
        s0 = make_stage()
        bad_to = uuid4()
        edge = make_transition(from_stage_id=s0.id, to_stage_id=bad_to)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            make_workflow(stages=[s0], transitions=[edge], entry_stage_id=s0.id)
        assert "Transition references unknown stage" in excinfo.value.message
        assert str(bad_to) in excinfo.value.message


class TestBFSCycleSafety:
    """TC-UT-WF-023 ── BFS が循環グラフでも無限ループせず終了する。"""

    def test_helper_terminates_on_cycle(self) -> None:
        """`_validate_dag_reachability` が 3 ステージ循環でハングせず戻る。"""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e1 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e2 = make_transition(from_stage_id=s1.id, to_stage_id=s2.id)
        e3 = make_transition(from_stage_id=s2.id, to_stage_id=s0.id)
        # 全ステージが到達可能。reachability チェックは raise しないはず。
        _validate_dag_reachability([s0, s1, s2], [e1, e2, e3], s0.id)
