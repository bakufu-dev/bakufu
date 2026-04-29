"""workflow / http-api ユニットテスト — スキーマ検証 (TC-UT-WFH-001~005).

Covers:
  TC-UT-WFH-001  StageCreate スキーマ検証
  TC-UT-WFH-002  TransitionCreate スキーマ検証
  TC-UT-WFH-003  WorkflowCreate スキーマ（排他バリデーション）
  TC-UT-WFH-004  WorkflowUpdate スキーマ（整合バリデーション）
  TC-UT-WFH-005  レスポンススキーマ群シリアライズ

Issue: #58
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError


class TestStageCreateSchema:
    """TC-UT-WFH-001: StageCreate スキーマ検証 (Q-3)。"""

    def test_valid_stage_passes(self) -> None:
        """(a) 有効な StageCreate → バリデーション通過。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate

        schema = StageCreate(
            id=uuid4(),
            name="ステージ",
            kind="WORK",
            required_role=["DEVELOPER"],
        )
        assert schema.kind == "WORK"

    def test_empty_name_raises(self) -> None:
        """(b) name='' → min_length 違反 → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate

        with pytest.raises(ValidationError):
            StageCreate(id=uuid4(), name="", kind="WORK", required_role=["DEVELOPER"])

    def test_name_too_long_raises(self) -> None:
        """(c) name='x'*81 → max_length 違反 → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate

        with pytest.raises(ValidationError):
            StageCreate(id=uuid4(), name="x" * 81, kind="WORK", required_role=["DEVELOPER"])

    def test_empty_required_role_raises(self) -> None:
        """(d) required_role=[] → min_length 違反（空リスト不可）→ ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate

        with pytest.raises(ValidationError):
            StageCreate(id=uuid4(), name="S", kind="WORK", required_role=[])

    def test_invalid_kind_raises(self) -> None:
        """(e) kind='INVALID_KIND' → 無効 enum 値 → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate

        with pytest.raises(ValidationError):
            StageCreate(id=uuid4(), name="S", kind="INVALID_KIND", required_role=["DEVELOPER"])

    def test_extra_field_raises(self) -> None:
        """(f) extra_field='z' → extra='forbid' → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate

        with pytest.raises(ValidationError):
            StageCreate.model_validate(
                {
                    "id": str(uuid4()),
                    "name": "S",
                    "kind": "WORK",
                    "required_role": ["DEVELOPER"],
                    "extra_field": "z",
                }
            )

    def test_all_valid_kinds_pass(self) -> None:
        """WORK / INTERNAL_REVIEW / EXTERNAL_REVIEW すべて通過。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate

        for kind in ("WORK", "INTERNAL_REVIEW", "EXTERNAL_REVIEW"):
            schema = StageCreate(id=uuid4(), name="S", kind=kind, required_role=["DEVELOPER"])
            assert schema.kind == kind


class TestTransitionCreateSchema:
    """TC-UT-WFH-002: TransitionCreate スキーマ検証 (Q-3)。"""

    def test_valid_transition_passes(self) -> None:
        """(a) 有効な TransitionCreate (condition='APPROVED') → 通過。"""
        from bakufu.interfaces.http.schemas.workflow import TransitionCreate

        fid = uuid4()
        tid = uuid4()
        schema = TransitionCreate(
            id=uuid4(),
            from_stage_id=fid,
            to_stage_id=tid,
            condition="APPROVED",
        )
        assert schema.condition == "APPROVED"

    def test_invalid_condition_raises(self) -> None:
        """(b) condition='INVALID' → 無効 enum 値 → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import TransitionCreate

        with pytest.raises(ValidationError):
            TransitionCreate(
                id=uuid4(),
                from_stage_id=uuid4(),
                to_stage_id=uuid4(),
                condition="INVALID",
            )

    def test_self_loop_passes(self) -> None:
        """(c) from_stage_id == to_stage_id (self-loop) → スキーマ層では通過。

        domain 層で DAG 検査される。
        """
        from bakufu.interfaces.http.schemas.workflow import TransitionCreate

        same_id = uuid4()
        schema = TransitionCreate(
            id=uuid4(),
            from_stage_id=same_id,
            to_stage_id=same_id,
            condition="APPROVED",
        )
        assert schema.from_stage_id == schema.to_stage_id

    def test_extra_field_raises(self) -> None:
        """(d) extra_field='z' → extra='forbid' → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import TransitionCreate

        with pytest.raises(ValidationError):
            TransitionCreate.model_validate(
                {
                    "id": str(uuid4()),
                    "from_stage_id": str(uuid4()),
                    "to_stage_id": str(uuid4()),
                    "condition": "APPROVED",
                    "extra_field": "z",
                }
            )

    def test_all_valid_conditions_pass(self) -> None:
        """APPROVED / REJECTED / CONDITIONAL / TIMEOUT すべて通過。"""
        from bakufu.interfaces.http.schemas.workflow import TransitionCreate

        for cond in ("APPROVED", "REJECTED", "CONDITIONAL", "TIMEOUT"):
            schema = TransitionCreate(
                id=uuid4(),
                from_stage_id=uuid4(),
                to_stage_id=uuid4(),
                condition=cond,
            )
            assert schema.condition == cond


class TestWorkflowCreateSchema:
    """TC-UT-WFH-003: WorkflowCreate スキーマ（排他バリデーション）(Q-3)。"""

    def test_preset_mode_passes(self) -> None:
        """(a) preset_name='v-model', 他は None → 通過（プリセットモード）。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowCreate

        schema = WorkflowCreate(preset_name="v-model")
        assert schema.preset_name == "v-model"

    def test_json_definition_mode_passes(self) -> None:
        """(b) name + stages + transitions + entry_stage_id → 通過（JSON 定義モード）。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate, WorkflowCreate

        sid = uuid4()
        schema = WorkflowCreate(
            name="X",
            stages=[StageCreate(id=sid, name="S", kind="WORK", required_role=["DEVELOPER"])],
            transitions=[],
            entry_stage_id=sid,
        )
        assert schema.name == "X"

    def test_preset_with_stages_raises(self) -> None:
        """(c) preset_name + stages 同時指定 → 排他違反 → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate, WorkflowCreate

        sid = uuid4()
        with pytest.raises(ValidationError):
            WorkflowCreate(
                preset_name="v-model",
                stages=[StageCreate(id=sid, name="S", kind="WORK", required_role=["DEVELOPER"])],
            )

    def test_all_none_raises(self) -> None:
        """(d) 全フィールド None → 排他違反 → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowCreate

        with pytest.raises(ValidationError):
            WorkflowCreate()

    def test_preset_with_name_passes(self) -> None:
        """(e) preset_name + name → preset モードでは name 上書きは許容。

        WorkflowCreate は preset_name 指定時に
        stages/transitions/entry_stage_id が None であることを要求するが、
        name は別フィールドのため制約外（None 扱いで検証されない）。
        """
        from bakufu.interfaces.http.schemas.workflow import WorkflowCreate

        schema = WorkflowCreate(preset_name="v-model", name="上書き名")
        assert schema.preset_name == "v-model"

    def test_extra_field_raises(self) -> None:
        """(f) extra_field='z' → extra='forbid' → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowCreate

        with pytest.raises(ValidationError):
            WorkflowCreate.model_validate({"preset_name": "v-model", "extra_field": "z"})


class TestWorkflowUpdateSchema:
    """TC-UT-WFH-004: WorkflowUpdate スキーマ（整合バリデーション）(Q-3)。"""

    def test_name_only_passes(self) -> None:
        """(a) name='新名前' のみ → 通過（DAG 更新なし）。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowUpdate

        schema = WorkflowUpdate(name="新名前")
        assert schema.name == "新名前"

    def test_full_dag_replace_passes(self) -> None:
        """(b) stages + transitions + entry_stage_id 全指定 → 通過（DAG 全置換）。"""
        from bakufu.interfaces.http.schemas.workflow import (
            StageCreate,
            WorkflowUpdate,
        )

        sid = uuid4()
        schema = WorkflowUpdate(
            stages=[StageCreate(id=sid, name="S", kind="WORK", required_role=["DEVELOPER"])],
            transitions=[],
            entry_stage_id=sid,
        )
        assert schema.entry_stage_id == sid

    def test_all_none_passes(self) -> None:
        """(c) 全フィールド None → 通過（変更なし）。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowUpdate

        schema = WorkflowUpdate()
        assert schema.name is None
        assert schema.stages is None

    def test_stages_only_raises(self) -> None:
        """(d) stages のみ（transitions=None）→ 整合バリデーション違反 → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import StageCreate, WorkflowUpdate

        sid = uuid4()
        with pytest.raises(ValidationError):
            WorkflowUpdate(
                stages=[StageCreate(id=sid, name="S", kind="WORK", required_role=["DEVELOPER"])]
            )

    def test_empty_name_raises(self) -> None:
        """(e) name='' → min_length 違反 → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowUpdate

        with pytest.raises(ValidationError):
            WorkflowUpdate(name="")

    def test_extra_field_raises(self) -> None:
        """(f) extra_field='z' → extra='forbid' → ValidationError。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowUpdate

        with pytest.raises(ValidationError):
            WorkflowUpdate.model_validate({"name": "X", "extra_field": "z"})


class TestResponseSchemas:
    """TC-UT-WFH-005: レスポンススキーマ群シリアライズ (Q-3)。"""

    def _make_mock_workflow(self) -> object:
        from tests.factories.workflow import make_workflow

        return make_workflow()

    def test_workflow_response_id_is_str(self) -> None:
        """WorkflowResponse.id は str (UUID 文字列)。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowResponse

        wf = self._make_mock_workflow()
        resp = WorkflowResponse.model_validate(wf)
        assert isinstance(resp.id, str)

    def test_workflow_response_stages_is_list(self) -> None:
        """WorkflowResponse.stages は list[StageResponse]。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowResponse

        wf = self._make_mock_workflow()
        resp = WorkflowResponse.model_validate(wf)
        assert isinstance(resp.stages, list)

    def test_workflow_response_transitions_is_list(self) -> None:
        """WorkflowResponse.transitions は list[TransitionResponse]。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowResponse

        wf = self._make_mock_workflow()
        resp = WorkflowResponse.model_validate(wf)
        assert isinstance(resp.transitions, list)

    def test_workflow_response_entry_stage_id_is_str(self) -> None:
        """WorkflowResponse.entry_stage_id は str。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowResponse

        wf = self._make_mock_workflow()
        resp = WorkflowResponse.model_validate(wf)
        assert isinstance(resp.entry_stage_id, str)

    def test_workflow_response_archived_is_bool(self) -> None:
        """WorkflowResponse.archived は bool。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowResponse

        wf = self._make_mock_workflow()
        resp = WorkflowResponse.model_validate(wf)
        assert isinstance(resp.archived, bool)

    def test_workflow_list_response_total_matches_items(self) -> None:
        """WorkflowListResponse.total == len(items)。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowListResponse, WorkflowResponse

        wf = self._make_mock_workflow()
        items = [WorkflowResponse.model_validate(wf)]
        resp = WorkflowListResponse(items=items, total=len(items))
        assert resp.total == 1

    def test_stage_response_required_role_is_list_of_str(self) -> None:
        """StageResponse.required_role は list[str]。"""
        from bakufu.interfaces.http.schemas.workflow import WorkflowResponse

        wf = self._make_mock_workflow()
        resp = WorkflowResponse.model_validate(wf)
        assert all(isinstance(r, str) for stage in resp.stages for r in stage.required_role)

    def test_stage_list_response_has_stages_and_entry(self) -> None:
        """StageListResponse は stages + transitions + entry_stage_id を持つ。"""
        from bakufu.interfaces.http.schemas.workflow import (
            StageListResponse,
            StageResponse,
            TransitionResponse,
        )

        from tests.factories.workflow import make_workflow

        wf = make_workflow()
        resp = StageListResponse(
            stages=[StageResponse.model_validate(s) for s in wf.stages],
            transitions=[TransitionResponse.model_validate(t) for t in wf.transitions],
            entry_stage_id=str(wf.entry_stage_id),
        )
        assert isinstance(resp.stages, list)
        assert isinstance(resp.entry_stage_id, str)

    def test_workflow_preset_list_response_total_is_2(self) -> None:
        """WorkflowPresetListResponse.total=2 (v-model / agile)。"""
        from bakufu.interfaces.http.schemas.workflow import (
            WorkflowPresetListResponse,
            WorkflowPresetResponse,
        )

        items = [
            WorkflowPresetResponse(
                preset_name="v-model",
                display_name="V モデル開発プロセス",
                description="desc",
                stage_count=13,
                transition_count=15,
            ),
            WorkflowPresetResponse(
                preset_name="agile",
                display_name="アジャイル開発プロセス",
                description="desc",
                stage_count=6,
                transition_count=8,
            ),
        ]
        resp = WorkflowPresetListResponse(items=items, total=len(items))
        assert resp.total == 2
