"""WorkflowService — Workflow Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.room_exceptions import RoomArchivedError, RoomNotFoundError
from bakufu.application.exceptions.workflow_exceptions import (
    WorkflowArchivedError,
    WorkflowNotFoundError,
    WorkflowPresetNotFoundError,
)
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.application.presets.workflow_presets import WORKFLOW_PRESETS, WorkflowPresetDefinition
from bakufu.domain.room.room import Room
from bakufu.domain.value_objects import RoomId, WorkflowId
from bakufu.domain.workflow.entities import Stage, Transition
from bakufu.domain.workflow.workflow import Workflow


class WorkflowService:
    """Workflow Aggregate 操作の application 層サービス（確定 G）。"""

    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        room_repo: RoomRepository,
        session: AsyncSession,
    ) -> None:
        self._workflow_repo = workflow_repo
        self._room_repo = room_repo
        self._session = session

    async def create_for_room(
        self,
        room_id: RoomId,
        preset_name: str | None,
        name: str | None,
        stages: list[dict] | None,
        transitions: list[dict] | None,
        entry_stage_id: UUID | None,
    ) -> Workflow:
        """Room に Workflow を作成し、Room.workflow_id を更新する。"""
        # 1. Room 存在確認
        room = await self._room_repo.find_by_id(room_id)
        if room is None:
            raise RoomNotFoundError(str(room_id))
        # 2. Room archived 確認
        if room.archived:
            raise RoomArchivedError(str(room_id))
        # 3. プリセット解決 or JSON 定義
        if preset_name is not None:
            workflow = self._build_from_preset(preset_name)
        else:
            # stages/transitions/entry_stage_id are all non-None (guaranteed by schema validation)
            workflow = self._build_from_dicts(
                name=name,  # type: ignore[arg-type]
                stages=stages,  # type: ignore[arg-type]
                transitions=transitions,  # type: ignore[arg-type]
                entry_stage_id=entry_stage_id,  # type: ignore[arg-type]
            )
        # 4. UoW: save workflow + update Room.workflow_id
        async with self._session.begin():
            await self._workflow_repo.save(workflow)
            empire_id = await self._room_repo.find_empire_id_by_room_id(room_id)
            state = room.model_dump()
            state["workflow_id"] = str(workflow.id)
            updated_room = Room.model_validate(state)
            await self._room_repo.save(updated_room, empire_id)  # type: ignore[arg-type]
        return workflow

    async def find_by_room(self, room_id: RoomId) -> Workflow | None:
        """Room の Workflow を返す。Room が存在しない場合は RoomNotFoundError。"""
        room = await self._room_repo.find_by_id(room_id)
        if room is None:
            raise RoomNotFoundError(str(room_id))
        return await self._workflow_repo.find_by_id(room.workflow_id)

    async def find_by_id(self, workflow_id: WorkflowId) -> Workflow:
        """Workflow を返す。存在しない場合は WorkflowNotFoundError。"""
        workflow = await self._workflow_repo.find_by_id(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(str(workflow_id))
        return workflow

    async def update(
        self,
        workflow_id: WorkflowId,
        name: str | None,
        stages: list[dict] | None,
        transitions: list[dict] | None,
        entry_stage_id: UUID | None,
    ) -> Workflow:
        """Workflow を部分更新する。"""
        workflow = await self._workflow_repo.find_by_id(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(str(workflow_id))
        if workflow.archived:
            raise WorkflowArchivedError(str(workflow_id), kind="update")
        # 部分更新: name のみ、または stages/transitions/entry_stage_id を全置換
        state = workflow.model_dump()
        if name is not None:
            state["name"] = name
        if stages is not None:
            state["stages"] = self._prepare_stage_dicts(stages)
            state["transitions"] = self._prepare_transition_dicts(transitions or [])
            state["entry_stage_id"] = str(entry_stage_id)
        updated = Workflow.model_validate(state)
        async with self._session.begin():
            await self._workflow_repo.save(updated)
        return updated

    async def archive(self, workflow_id: WorkflowId) -> None:
        """Workflow を論理削除する (archived=True)。"""
        workflow = await self._workflow_repo.find_by_id(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(str(workflow_id))
        archived_workflow = workflow.archive()
        async with self._session.begin():
            await self._workflow_repo.save(archived_workflow)

    async def find_stages(
        self, workflow_id: WorkflowId
    ) -> tuple[list[Stage], list[Transition], object]:
        """Workflow のステージ・トランジション・エントリーステージ ID を返す。"""
        workflow = await self.find_by_id(workflow_id)
        return workflow.stages, workflow.transitions, workflow.entry_stage_id

    def get_presets(self) -> list[WorkflowPresetDefinition]:
        """利用可能なプリセット一覧を返す。"""
        return list(WORKFLOW_PRESETS.values())

    # ---- private helpers ------------------------------------------------

    def _build_from_preset(self, preset_name: str) -> Workflow:
        """プリセット名から Workflow を構築する。"""
        preset = WORKFLOW_PRESETS.get(preset_name)
        if preset is None:
            raise WorkflowPresetNotFoundError(preset_name)
        return Workflow.model_validate(
            {
                "id": uuid4(),
                "name": preset.name,
                "stages": preset.stages,
                "transitions": preset.transitions,
                "entry_stage_id": preset.entry_stage_id,
            }
        )

    def _build_from_dicts(
        self,
        name: str,
        stages: list[dict],
        transitions: list[dict],
        entry_stage_id: UUID,
    ) -> Workflow:
        """dict 定義から Workflow を構築する。"""
        return Workflow.model_validate(
            {
                "id": uuid4(),
                "name": name,
                "stages": self._prepare_stage_dicts(stages),
                "transitions": self._prepare_transition_dicts(transitions),
                "entry_stage_id": str(entry_stage_id),
            }
        )

    @staticmethod
    def _prepare_stage_dicts(stages: list[dict]) -> list[dict]:
        """StageCreate.model_dump() 形式を domain Stage 互換形式に変換する。"""
        result = []
        for stage in stages:
            s = dict(stage)
            if s.get("completion_policy") is None:
                s["completion_policy"] = {"kind": "manual", "description": ""}
            # notify_channels: URL strings → NotifyChannel dict format
            s["notify_channels"] = [
                {"kind": "discord", "target": url}
                for url in s.get("notify_channels", [])
            ]
            result.append(s)
        return result

    @staticmethod
    def _prepare_transition_dicts(transitions: list[dict]) -> list[dict]:
        """TransitionCreate.model_dump() 形式を domain Transition 互換形式に変換する。"""
        return [dict(t) for t in transitions]


__all__ = ["WorkflowService"]
