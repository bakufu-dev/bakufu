"""Workflow mutators (REQ-WF-002 / 003 / 004) + pre-validate ロールバック。

add_stage / add_transition / remove_stage と Confirmation A の契約を
カバー: 失敗した mutators は元 Workflow を変更なしで残す。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import Role, StageKind, TransitionCondition
from bakufu.domain.workflow import MAX_STAGES, MAX_TRANSITIONS, Workflow

from tests.factories.workflow import make_stage, make_transition, make_workflow


class TestAddStage:
    """REQ-WF-002 / TC-UT-WF-014 / 044。

    TC-UT-WF-013 の注記: ``add_stage`` は単独では成功できない
    (新規追加 Stage は incoming Transition なしでは orphan で
    aggregate レベル ``_validate_dag_reachability`` は拒否)。
    "appends" 成功パスは ``from_dict`` (TC-IT-WF-001) で実行 —
    粒度 mutators は **constrained** 変更用に設計。
    """

    def test_duplicate_stage_id_raises_stage_duplicate(self) -> None:
        """TC-UT-WF-014: 既存 id の add_stage は stage_duplicate を発火。"""
        wf = make_workflow()
        existing = wf.stages[0]
        duplicate = make_stage(stage_id=existing.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.add_stage(duplicate)
        assert excinfo.value.kind == "stage_duplicate"

    def test_msg_wf_008_for_duplicate_includes_stage_id(self) -> None:
        """TC-UT-WF-044: MSG-WF-008 wording は重複 stage_id を含む。"""
        wf = make_workflow()
        existing = wf.stages[0]
        duplicate = make_stage(stage_id=existing.id)
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.add_stage(duplicate)
        assert excinfo.value.message == f"[FAIL] Stage id duplicate: {existing.id}"


class TestAddStageCapacity:
    """REQ-WF-002 capacity / TC-UT-WF-015。"""

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-WF-015: from_dict 経由 >MAX_STAGES 一括インポートは capacity_exceeded を発火。"""
        stages: list[dict[str, object]] = []
        first_id: str | None = None
        for _ in range(MAX_STAGES + 1):
            sid = str(uuid4())
            stages.append(
                {
                    "id": sid,
                    "name": "S",
                    "kind": StageKind.WORK.value,
                    "required_role": [Role.DEVELOPER.value],
                    "required_deliverables": [],
                    "completion_policy": {"kind": "manual", "description": ""},
                    "notify_channels": [],
                }
            )
            if first_id is None:
                first_id = sid
        # 少なくとも有効なトポロジを持つよう前方 APPROVED チェーンを構築。
        transitions: list[dict[str, object]] = []
        previous: str | None = None
        for stage in stages:
            current = stage["id"]
            if previous is not None:
                transitions.append(
                    {
                        "id": str(uuid4()),
                        "from_stage_id": previous,
                        "to_stage_id": current,
                        "condition": TransitionCondition.APPROVED.value,
                        "label": "",
                    }
                )
            previous = str(current)
        payload = {
            "id": str(uuid4()),
            "name": "overflow",
            "stages": stages,
            "transitions": transitions,
            "entry_stage_id": first_id,
        }
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            Workflow.from_dict(payload)
        assert excinfo.value.kind == "capacity_exceeded"


class TestAddTransition:
    """REQ-WF-003 / TC-UT-WF-016 / 017。"""

    def test_appends_transition_to_list(self) -> None:
        """TC-UT-WF-016: add_transition はエッジが追加された新 Workflow を返す。

        事前状態: 2 つの前方 APPROVED エッジを持つ 3 ステージ チェーン s0→s1→s2。
        REJECTED バックエッジ s1→s0 を追加するとシングル sink として s2 を残す。
        """
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        e1 = make_transition(
            from_stage_id=s1.id, to_stage_id=s2.id, condition=TransitionCondition.APPROVED
        )
        wf = make_workflow(stages=[s0, s1, s2], transitions=[e0, e1], entry_stage_id=s0.id)
        e_back = make_transition(
            from_stage_id=s1.id, to_stage_id=s0.id, condition=TransitionCondition.REJECTED
        )
        updated = wf.add_transition(e_back)
        assert len(updated.transitions) == 3

    def test_does_not_mutate_original(self) -> None:
        """TC-UT-WF-016: 呼び出し元の Workflow は add パス後も 2 遷移で留まる。"""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e1 = make_transition(from_stage_id=s1.id, to_stage_id=s2.id)
        wf = make_workflow(stages=[s0, s1, s2], transitions=[e0, e1], entry_stage_id=s0.id)
        e_back = make_transition(
            from_stage_id=s1.id, to_stage_id=s0.id, condition=TransitionCondition.REJECTED
        )
        wf.add_transition(e_back)
        assert len(wf.transitions) == 2

    def test_dangling_ref_raises_transition_ref_invalid(self) -> None:
        """TC-UT-WF-017: 未知 from/to の add_transition は transition_ref_invalid を発火。"""
        wf = make_workflow()
        bad_edge = make_transition(from_stage_id=wf.stages[0].id, to_stage_id=uuid4())
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.add_transition(bad_edge)
        assert excinfo.value.kind == "transition_ref_invalid"


class TestAddTransitionCapacity:
    """REQ-WF-003 capacity / TC-UT-WF-018。"""

    def test_overflow_raises_capacity_exceeded(self) -> None:
        """TC-UT-WF-018: from_dict 経由 >MAX_TRANSITIONS 構築は capacity_exceeded を発火。"""
        stage_ids = [str(uuid4()) for _ in range(2)]
        stages_payload: list[dict[str, object]] = [
            {
                "id": sid,
                "name": "S",
                "kind": StageKind.WORK.value,
                "required_role": [Role.DEVELOPER.value],
                "required_deliverables": [],
                "completion_policy": {"kind": "manual", "description": ""},
                "notify_channels": [],
            }
            for sid in stage_ids
        ]
        transitions_payload: list[dict[str, object]] = [
            {
                "id": str(uuid4()),
                "from_stage_id": stage_ids[0],
                "to_stage_id": stage_ids[1],
                "condition": TransitionCondition.APPROVED.value,
                "label": "",
            }
        ]
        for _ in range(MAX_TRANSITIONS):
            transitions_payload.append(
                {
                    "id": str(uuid4()),
                    "from_stage_id": stage_ids[0],
                    "to_stage_id": stage_ids[1],
                    "condition": TransitionCondition.APPROVED.value,
                    "label": "",
                }
            )
        payload = {
            "id": str(uuid4()),
            "name": "overflow",
            "stages": stages_payload,
            "transitions": transitions_payload,
            "entry_stage_id": stage_ids[0],
        }
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            Workflow.from_dict(payload)
        # Capacity は determinism の前にチェック、capacity_exceeded が先に発火。
        assert excinfo.value.kind == "capacity_exceeded"


class TestRemoveStage:
    """REQ-WF-004 / TC-UT-WF-009 / 019 / 020 / 021 / 046。"""

    def test_remove_entry_stage_raises_cannot_remove_entry(self) -> None:
        """TC-UT-WF-009: remove_stage(entry_stage_id) は cannot_remove_entry を発火。"""
        wf = make_workflow()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.remove_stage(wf.entry_stage_id)
        assert excinfo.value.kind == "cannot_remove_entry"

    def test_msg_wf_010_includes_stage_id(self) -> None:
        """TC-UT-WF-046: MSG-WF-010 wording は entry stage_id を含む。"""
        wf = make_workflow()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.remove_stage(wf.entry_stage_id)
        assert excinfo.value.message == f"[FAIL] Cannot remove entry stage: {wf.entry_stage_id}"

    def test_unknown_stage_id_raises_stage_not_found(self) -> None:
        """TC-UT-WF-019: remove_stage(unknown) は MSG-WF-012 で stage_not_found を発火。"""
        wf = make_workflow()
        unknown = uuid4()
        with pytest.raises(WorkflowInvariantViolation) as excinfo:
            wf.remove_stage(unknown)
        assert excinfo.value.kind == "stage_not_found"
        assert excinfo.value.message == f"[FAIL] Stage not found in workflow: stage_id={unknown}"

    def test_cascades_incident_transitions(self) -> None:
        """TC-UT-WF-020: Stage を削除すると参照 Transitions も削除。"""
        s0 = make_stage()
        s1 = make_stage()
        s2 = make_stage()
        e0 = make_transition(from_stage_id=s0.id, to_stage_id=s1.id)
        e1 = make_transition(from_stage_id=s1.id, to_stage_id=s2.id)
        wf = make_workflow(stages=[s0, s1, s2], transitions=[e0, e1], entry_stage_id=s0.id)
        # 末尾ステージ s2 を削除すると s0→s1 は有効なまま (s1 が sink に)。
        updated = wf.remove_stage(s2.id)
        assert len(updated.stages) == 2 and len(updated.transitions) == 1


class TestPreValidateRollback:
    """Confirmation A — 失敗した mutators は元 Workflow を変更なしで残す。"""

    def test_failed_add_stage_keeps_original(self) -> None:
        """TC-UT-WF-008: 失敗した add_stage は呼び出し元 Workflow を変更しない。"""
        wf = make_workflow()
        existing = wf.stages[0]
        with pytest.raises(WorkflowInvariantViolation):
            wf.add_stage(make_stage(stage_id=existing.id))
        assert len(wf.stages) == 1

    def test_failed_add_transition_keeps_original(self) -> None:
        """TC-UT-WF-030: 失敗した add_transition は呼び出し元 Workflow を変更しない。"""
        wf = make_workflow()
        bad = make_transition(from_stage_id=wf.stages[0].id, to_stage_id=uuid4())
        with pytest.raises(WorkflowInvariantViolation):
            wf.add_transition(bad)
        assert wf.transitions == []

    def test_failed_remove_stage_keeps_original(self) -> None:
        """TC-UT-WF-031: 失敗した remove_stage は呼び出し元 Workflow を変更しない。"""
        wf = make_workflow()
        with pytest.raises(WorkflowInvariantViolation):
            wf.remove_stage(uuid4())
        assert len(wf.stages) == 1
