"""TaskService — Task Aggregate 操作の application 層サービス。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.exceptions.agent_exceptions import (
    AgentArchivedError,
    AgentNotFoundError,
)
from bakufu.application.exceptions.room_exceptions import RoomNotFoundError
from bakufu.application.exceptions.task_exceptions import (
    TaskAuthorizationError,
    TaskNotFoundError,
    TaskStateConflictError,
)
from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.application.ports.event_bus import EventBusPort
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.domain.events import TaskStateChangedEvent
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

    def __init__(
        self,
        task_repo: TaskRepository,
        room_repo: RoomRepository,
        agent_repo: AgentRepository,
        session: AsyncSession,
        event_bus: EventBusPort,
    ) -> None:
        self._task_repo = task_repo
        self._room_repo = room_repo
        self._agent_repo = agent_repo
        self._session = session
        self._event_bus = event_bus

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
            assignees: list[AgentId] = list(agent_ids)
            await self._ensure_room_members(task, assignees, "assign")
            try:
                updated = task.assign(assignees, updated_at=self._now())
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
        # トランザクション commit 後に publish（業務操作成功後のみ）
        await self._event_bus.publish(
            TaskStateChangedEvent(
                aggregate_id=str(task.id),
                directive_id=str(task.directive_id),
                old_status=str(task.status),
                new_status=str(updated.status),
                room_id=str(task.room_id),
            )
        )
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
        # トランザクション commit 後に publish（業務操作成功後のみ）
        await self._event_bus.publish(
            TaskStateChangedEvent(
                aggregate_id=str(task.id),
                directive_id=str(task.directive_id),
                old_status=str(task.status),
                new_status=str(updated.status),
                room_id=str(task.room_id),
            )
        )
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
            await self._ensure_active_agent(submitted_by)
            self._ensure_assigned_agent(task, submitted_by, "commit_deliverable")
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
        # トランザクション commit 後に publish（業務操作成功後のみ）
        await self._event_bus.publish(
            TaskStateChangedEvent(
                aggregate_id=str(task.id),
                directive_id=str(task.directive_id),
                old_status=str(task.status),
                new_status=str(updated.status),
                room_id=str(task.room_id),
            )
        )
        return updated

    async def _find_by_id_in_uow(self, task_id: TaskId) -> Task:
        task = await self._task_repo.find_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def _ensure_room_members(
        self,
        task: Task,
        agent_ids: list[AgentId],
        action: str,
    ) -> None:
        room = await self._room_repo.find_by_id(task.room_id)
        if room is None:
            raise RoomNotFoundError(str(task.room_id))

        member_ids = {membership.agent_id for membership in room.members}
        for agent_id in agent_ids:
            await self._ensure_active_agent(agent_id)
            if agent_id not in member_ids:
                raise TaskAuthorizationError(
                    task_id=task.id,
                    action=action,
                    reason="Agent is not a member of the Task room.",
                )

    async def _ensure_active_agent(self, agent_id: AgentId) -> None:
        agent = await self._agent_repo.find_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(str(agent_id))
        if agent.archived:
            raise AgentArchivedError(str(agent_id))

    @staticmethod
    def _ensure_assigned_agent(task: Task, agent_id: AgentId, action: str) -> None:
        if agent_id in task.assigned_agent_ids:
            return
        raise TaskAuthorizationError(
            task_id=task.id,
            action=action,
            reason="Agent is not assigned to this Task.",
        )

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
