"""Workflow ライフサイクル統合シナリオ (TC-IT-WF-001 / 002 / 003)。

Aggregate 内部ラウンドトリップと V-model プリセット。
これらテストは公開エントリポイントなしドメイン層の
"E2E by stand-in" として機能 — ``from_dict`` と
mutator チェーンを通し公開 Workflow API をエンドツーエンド実行。
"""

from __future__ import annotations

from typing import cast
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import StageKind, TransitionCondition
from bakufu.domain.workflow import Workflow
from pydantic import ValidationError

from tests.factories.workflow import (
    build_v_model_payload,
    make_stage,
    make_transition,
    make_workflow,
)


class TestWorkflowLifecycleIntegration:
    """Aggregate 内部ラウンドトリップ + V-model プリセット + 不良ペイロード亜種。"""

    def test_v_model_preset_constructs_via_from_dict(self) -> None:
        """TC-IT-WF-001: 13 ステージ / 15 遷移 V-model ペイロード は構築。"""
        wf = Workflow.from_dict(build_v_model_payload())
        assert len(wf.stages) == 13 and len(wf.transitions) == 15

    def test_v_model_preset_has_external_review_notify_channels(self) -> None:
        """TC-IT-WF-001: すべての EXTERNAL_REVIEW Stage は最低 1 つの notify_channel。"""
        wf = Workflow.from_dict(build_v_model_payload())
        review_stages = [s for s in wf.stages if s.kind is StageKind.EXTERNAL_REVIEW]
        assert all(len(s.notify_channels) >= 1 for s in review_stages)

    def test_round_trip_failed_then_recover(self) -> None:
        """TC-IT-WF-002: 失敗した add_transition はロールバック; 正当な追加は成功。

        事前状態: 3 ステージ チェーン s0→s1→s2 (s2 sink)。
        重複 APPROVED エッジ s0→s1 を追加試行、
        ``transition_duplicate`` をトリップ。
        元 Workflow は変更なし。次に REJECTED バックエッジ s1→s0 を追加、
        (s1, REJECTED) で一意で s2 をシングル sink として保持。
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

        bad_dup = make_transition(
            from_stage_id=s0.id, to_stage_id=s1.id, condition=TransitionCondition.APPROVED
        )
        with pytest.raises(WorkflowInvariantViolation):
            wf.add_transition(bad_dup)
        assert len(wf.transitions) == 2  # 元は変更なし

        e_back = make_transition(
            from_stage_id=s1.id, to_stage_id=s0.id, condition=TransitionCondition.REJECTED
        )
        updated = wf.add_transition(e_back)
        assert len(updated.transitions) == 3

        # 失敗 remove_stage(unknown) は updated を変更なしで残す。
        with pytest.raises(WorkflowInvariantViolation):
            updated.remove_stage(uuid4())
        assert len(updated.stages) == 3

    def test_t1_payload_variants_all_rejected(self) -> None:
        """TC-IT-WF-003: 不良ペイロード亜種 (role / uuid / 欠落 entry / 重複 stage) は拒否。"""
        # 亜種 1: 不良 role。
        v1 = build_v_model_payload()
        stages_v1 = cast("list[dict[str, object]]", v1["stages"])
        stages_v1[0]["required_role"] = ["UNKNOWN_ROLE"]
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(v1)

        # 亜種 2: 不良 UUID。
        v2 = build_v_model_payload()
        v2["id"] = "not-a-uuid"
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(v2)

        # 亜種 3: 欠落 entry_stage_id。
        v3 = build_v_model_payload()
        del v3["entry_stage_id"]
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(v3)

        # 亜種 4: 重複 stage_id。
        v4 = build_v_model_payload()
        stages_v4 = cast("list[dict[str, object]]", v4["stages"])
        stages_v4[1]["id"] = stages_v4[0]["id"]
        with pytest.raises((ValidationError, WorkflowInvariantViolation)):
            Workflow.from_dict(v4)
