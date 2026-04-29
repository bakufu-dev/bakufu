"""Task HTTP API エンドポイント。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from bakufu.interfaces.http.dependencies import TaskServiceDep
from bakufu.interfaces.http.schemas.task import (
    DeliverableCreate,
    TaskAssign,
    TaskListResponse,
    TaskResponse,
)

tasks_router = APIRouter(prefix="/api/tasks", tags=["task"])
room_tasks_router = APIRouter(prefix="/api/rooms", tags=["task"])


class TaskHttpRoutes:
    """Task HTTP 入口をクラスメソッドに閉じる。"""

    @classmethod
    async def get_task(cls, task_id: UUID, service: TaskServiceDep) -> TaskResponse:
        """Task を 1 件返す。"""
        task = await service.find_by_id(task_id)
        return TaskResponse.model_validate(task)

    @classmethod
    async def list_tasks_by_room(
        cls,
        room_id: UUID,
        service: TaskServiceDep,
    ) -> TaskListResponse:
        """Room に紐付く Task を返す。Room 不在でも空リスト。"""
        tasks = await service.find_all_by_room(room_id)
        items = [TaskResponse.model_validate(task) for task in tasks]
        return TaskListResponse(items=items, total=len(items))

    @classmethod
    async def assign_task(
        cls,
        task_id: UUID,
        body: TaskAssign,
        service: TaskServiceDep,
    ) -> TaskResponse:
        """Task に Agent を割り当てる。"""
        task = await service.assign(task_id, body.agent_ids)
        return TaskResponse.model_validate(task)

    @classmethod
    async def cancel_task(cls, task_id: UUID, service: TaskServiceDep) -> TaskResponse:
        """Task をキャンセルする。"""
        task = await service.cancel(task_id)
        return TaskResponse.model_validate(task)

    @classmethod
    async def unblock_task(cls, task_id: UUID, service: TaskServiceDep) -> TaskResponse:
        """BLOCKED Task を再試行可能状態へ戻す。"""
        task = await service.unblock_retry(task_id)
        return TaskResponse.model_validate(task)

    @classmethod
    async def commit_deliverable(
        cls,
        task_id: UUID,
        stage_id: UUID,
        body: DeliverableCreate,
        service: TaskServiceDep,
    ) -> TaskResponse:
        """Stage 成果物を Task に commit する。"""
        task = await service.commit_deliverable(
            task_id=task_id,
            stage_id=stage_id,
            body_markdown=body.body_markdown,
            submitted_by=body.submitted_by,
            attachments=[a.model_dump() for a in body.attachments or []],
        )
        return TaskResponse.model_validate(task)


tasks_router.add_api_route(
    "/{task_id}",
    TaskHttpRoutes.get_task,
    methods=["GET"],
    response_model=TaskResponse,
    status_code=200,
    summary="Task 単件取得（REQ-TS-HTTP-001）",
)
room_tasks_router.add_api_route(
    "/{room_id}/tasks",
    TaskHttpRoutes.list_tasks_by_room,
    methods=["GET"],
    response_model=TaskListResponse,
    status_code=200,
    summary="Room の Task 一覧取得（REQ-TS-HTTP-002）",
)
tasks_router.add_api_route(
    "/{task_id}/assign",
    TaskHttpRoutes.assign_task,
    methods=["POST"],
    response_model=TaskResponse,
    status_code=200,
    summary="Agent 割り当て（REQ-TS-HTTP-003）",
)
tasks_router.add_api_route(
    "/{task_id}/cancel",
    TaskHttpRoutes.cancel_task,
    methods=["PATCH"],
    response_model=TaskResponse,
    status_code=200,
    summary="Task キャンセル（REQ-TS-HTTP-004）",
)
tasks_router.add_api_route(
    "/{task_id}/unblock",
    TaskHttpRoutes.unblock_task,
    methods=["PATCH"],
    response_model=TaskResponse,
    status_code=200,
    summary="BLOCKED Task の復旧（REQ-TS-HTTP-005）",
)
tasks_router.add_api_route(
    "/{task_id}/deliverables/{stage_id}",
    TaskHttpRoutes.commit_deliverable,
    methods=["POST"],
    response_model=TaskResponse,
    status_code=200,
    summary="成果物 commit（REQ-TS-HTTP-006）",
)


__all__ = ["room_tasks_router", "tasks_router"]
