"""Workflow Stage contract resolver port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bakufu.domain.value_objects import (
    StageId,
    StageKind,
    TransitionCondition,
    TransitionId,
    WorkflowId,
)


@dataclass(frozen=True, slots=True)
class WorkflowStageContract:
    """TaskService が必要とする Workflow Stage の契約面。"""

    id: StageId
    kind: StageKind


@dataclass(frozen=True, slots=True)
class WorkflowTransitionContract:
    """GateService が必要とする Workflow Transition の契約面。"""

    id: TransitionId
    from_stage_id: StageId
    to_stage_id: StageId
    condition: TransitionCondition


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

    async def find_transition_by_workflow_stage_condition(
        self,
        workflow_id: WorkflowId,
        stage_id: StageId,
        condition: TransitionCondition,
    ) -> WorkflowTransitionContract | None:
        """Workflow 内の ``stage_id`` から ``condition`` で進む Transition を返す。"""
        ...


__all__ = ["WorkflowStageContract", "WorkflowStageResolver", "WorkflowTransitionContract"]
