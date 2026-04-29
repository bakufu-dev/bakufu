"""SQLite implementation of WorkflowStageResolver."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.ports.workflow_stage_resolver import (
    WorkflowStageContract,
    WorkflowStageResolver,
)
from bakufu.domain.value_objects import StageId, StageKind, WorkflowId
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import WorkflowStageRow
from bakufu.infrastructure.persistence.sqlite.tables.workflows import WorkflowRow


class SqliteWorkflowStageResolver(WorkflowStageResolver):
    """Workflow Stage の契約面だけを読み取る SQLite adapter。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_entry_stage_id(self, workflow_id: WorkflowId) -> StageId | None:
        stmt = select(WorkflowRow.entry_stage_id).where(WorkflowRow.id == workflow_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_workflow_and_stage(
        self,
        workflow_id: WorkflowId,
        stage_id: StageId,
    ) -> WorkflowStageContract | None:
        stmt = select(WorkflowStageRow).where(
            WorkflowStageRow.workflow_id == workflow_id,
            WorkflowStageRow.stage_id == stage_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return WorkflowStageContract(id=row.stage_id, kind=StageKind(row.kind))


__all__ = ["SqliteWorkflowStageResolver"]
