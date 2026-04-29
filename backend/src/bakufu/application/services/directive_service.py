"""DirectiveService — Directive 発行と Task 起票の application 層サービス。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.room_exceptions import (
    RoomArchivedError,
    RoomNotFoundError,
)
from bakufu.application.exceptions.workflow_exceptions import WorkflowNotFoundError
from bakufu.application.ports.directive_repository import DirectiveRepository
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.domain.directive.directive import Directive
from bakufu.domain.task.task import Task
from bakufu.domain.value_objects import RoomId, TaskStatus


class DirectiveService:
    """Directive 発行と Task 起票を同一 Unit-of-Work で扱う。"""

    def __init__(
        self,
        directive_repo: DirectiveRepository,
        task_repo: TaskRepository,
        room_repo: RoomRepository,
        workflow_repo: WorkflowRepository,
        session: AsyncSession,
    ) -> None:
        self._directive_repo = directive_repo
        self._task_repo = task_repo
        self._room_repo = room_repo
        self._workflow_repo = workflow_repo
        self._session = session

    async def issue(self, room_id: RoomId, raw_text: str) -> tuple[Directive, Task]:
        """Directive を発行し、対応する PENDING Task を同一 Tx で作成する。"""
        async with self._session.begin():
            room = await self._room_repo.find_by_id(room_id)
            if room is None:
                raise RoomNotFoundError(str(room_id))
            if room.archived:
                raise RoomArchivedError(str(room_id))

            workflow = await self._workflow_repo.find_by_id(room.workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(room.workflow_id))

            now = self._now()
            text = raw_text if raw_text.startswith("$") else f"${raw_text}"
            directive = Directive(
                id=uuid4(),
                text=text,
                target_room_id=room_id,
                created_at=now,
            )
            task = Task(
                id=uuid4(),
                room_id=room_id,
                directive_id=directive.id,
                current_stage_id=workflow.entry_stage_id,
                status=TaskStatus.PENDING,
                assigned_agent_ids=[],
                deliverables={},
                created_at=now,
                updated_at=now,
                last_error=None,
            )

            await self._directive_repo.save(directive)
            directive_with_task = directive.link_task(task.id)
            await self._directive_repo.save(directive_with_task)
            await self._task_repo.save(task)

        return directive_with_task, task

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)


__all__ = ["DirectiveService"]
