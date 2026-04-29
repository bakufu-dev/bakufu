"""TaskService — Task Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.task_exceptions import (
    TaskNotFoundError,
    TaskStateConflictError,
)
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task.task import Task
from bakufu.domain.value_objects import (
    AgentId,
    Attachment,
    Deliverable,
    RoomId,
    StageId,
    TaskId,
)


class TaskService:
    """Task Aggregate 操作の application 層サービス。"""

    def __init__(self, task_repo: TaskRepository, session: AsyncSession) -> None:
        self._task_repo = task_repo
        self._session = session

    async def find_by_id(self, task_id: TaskId) -> Task:
        """Task を返す。存在しない場合は ``TaskNotFoundError``。"""
        task = await self._task_repo.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def find_all_by_room(self, room_id: RoomId) -> list[Task]:
        """Room に紐付く Task 一覧を返す。Room 不在でも空リスト。"""
        return await self._task_repo.find_all_by_room(room_id)

    async def assign(self, task_id: TaskId, agent_ids: list[UUID]) -> Task:
        """Task に Agent を割り当てる。"""
        async with self._session.begin():
            task = await self._find_by_id_in_uow(task_id)
            try:
                updated = task.assign(list(agent_ids), updated_at=self._now())
            except TaskInvariantViolation as exc:
                self._raise_conflict_if_needed(task, "assign", exc)
                raise
            await self._task_repo.save(updated)
        return updated

    async def cancel(self, task_id: TaskId) -> Task:
        """Task を CANCELLED に遷移させる。"""
        async with self._session.begin():
            task = await self._find_by_id_in_uow(task_id)
            try:
                updated = task.cancel(task.id, "", updated_at=self._now())
            except TaskInvariantViolation as exc:
                self._raise_conflict_if_needed(task, "cancel", exc)
                raise
            await self._task_repo.save(updated)
        return updated

    async def unblock_retry(self, task_id: TaskId) -> Task:
        """BLOCKED Task を IN_PROGRESS に戻す。"""
        async with self._session.begin():
            task = await self._find_by_id_in_uow(task_id)
            try:
                updated = task.unblock_retry(updated_at=self._now())
            except TaskInvariantViolation as exc:
                self._raise_conflict_if_needed(task, "unblock_retry", exc)
                raise
            await self._task_repo.save(updated)
        return updated

    async def commit_deliverable(
        self,
        task_id: TaskId,
        stage_id: StageId,
        body_markdown: str,
        submitted_by: AgentId,
        attachments: list[dict[str, Any]],
    ) -> Task:
        """Stage 成果物を Task に commit する。"""
        async with self._session.begin():
            task = await self._find_by_id_in_uow(task_id)
            try:
                deliverable = Deliverable(
                    stage_id=stage_id,
                    body_markdown=body_markdown,
                    attachments=[Attachment(**a) for a in attachments],
                    committed_by=submitted_by,
                    committed_at=self._now(),
                )
                updated = task.commit_deliverable(
                    stage_id,
                    deliverable,
                    submitted_by,
                    updated_at=self._now(),
                )
            except TaskInvariantViolation as exc:
                self._raise_conflict_if_needed(task, "commit_deliverable", exc)
                raise
            await self._task_repo.save(updated)
        return updated

    async def _find_by_id_in_uow(self, task_id: TaskId) -> Task:
        task = await self._task_repo.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _raise_conflict_if_needed(task: Task, action: str, exc: TaskInvariantViolation) -> None:
        if exc.kind not in {"terminal_violation", "state_transition_invalid"}:
            return
        raise TaskStateConflictError(
            task_id=task.id,
            current_status=task.status,
            action=action,
            message=str(exc),
        ) from exc


__all__ = ["TaskService"]
