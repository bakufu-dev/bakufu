"""Workflow Stage contract resolver port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bakufu.domain.value_objects import StageId, StageKind, WorkflowId


@dataclass(frozen=True, slots=True)
class WorkflowStageContract:
    """TaskService が必要とする Workflow Stage の契約面。"""

    id: StageId
    kind: StageKind


class WorkflowStageResolver(Protocol):
    """Workflow 全体を再水和せず、Stage 契約だけを解決する port。"""

    async def find_entry_stage_id(self, workflow_id: WorkflowId) -> StageId | None:
        """Workflow の entry_stage_id を返す。Workflow が存在しなければ ``None``。"""
        ...

    async def find_by_workflow_and_stage(
        self,
        workflow_id: WorkflowId,
        stage_id: StageId,
    ) -> WorkflowStageContract | None:
        """Workflow 内の Stage 契約を返す。存在しなければ ``None``。"""
        ...


__all__ = ["WorkflowStageContract", "WorkflowStageResolver"]
