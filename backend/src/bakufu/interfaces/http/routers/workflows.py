"""Workflow CRUD エンドポイント。

2 つの APIRouter:
  room_workflows_router (prefix="/api/rooms"):
    POST  /api/rooms/{room_id}/workflows   -> 201 WorkflowResponse
    GET   /api/rooms/{room_id}/workflows   -> 200 WorkflowListResponse

  workflows_router (prefix="/api/workflows"):
    GET   /api/workflows/presets           -> 200 WorkflowPresetListResponse  (登録優先)
    GET   /api/workflows/{id}              -> 200 WorkflowResponse
    PATCH /api/workflows/{id}              -> 200 WorkflowResponse
    DELETE /api/workflows/{id}             -> 204 No Content
    GET   /api/workflows/{id}/stages       -> 200 StageListResponse

Router 内に try/except を書かない (http-api-foundation architecture 規律)。
domain / infrastructure への import はゼロ (Q-3)。
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from bakufu.application.services.workflow_service import WorkflowService
from bakufu.interfaces.http.dependencies import get_workflow_service
from bakufu.interfaces.http.schemas.workflow import (
    StageListResponse,
    StageResponse,
    TransitionResponse,
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowPresetListResponse,
    WorkflowPresetResponse,
    WorkflowResponse,
    WorkflowUpdate,
)

room_workflows_router = APIRouter(prefix="/api/rooms", tags=["workflow"])
workflows_router = APIRouter(prefix="/api/workflows", tags=["workflow"])

WorkflowServiceDep = Annotated[WorkflowService, Depends(get_workflow_service)]


@room_workflows_router.post(
    "/{room_id}/workflows",
    status_code=201,
    response_model=WorkflowResponse,
)
async def create_workflow(
    room_id: UUID,
    body: WorkflowCreate,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Room に Workflow を作成する。

    - 404: Room が存在しない場合 (``RoomNotFoundError``)
    - 409: アーカイブ済み Room への操作 (``RoomArchivedError``)
    - 404: プリセット名が存在しない場合 (``WorkflowPresetNotFoundError``)
    - 422: Workflow 不変条件違反 (``WorkflowInvariantViolation``)
    """
    workflow = await service.create_for_room(
        room_id=room_id,
        preset_name=body.preset_name,
        name=body.name,
        stages=[s.model_dump() for s in body.stages] if body.stages is not None else None,
        transitions=(
            [t.model_dump() for t in body.transitions] if body.transitions is not None else None
        ),
        entry_stage_id=body.entry_stage_id,
    )
    return WorkflowResponse.model_validate(workflow)


@room_workflows_router.get(
    "/{room_id}/workflows",
    status_code=200,
    response_model=WorkflowListResponse,
)
async def list_workflows(
    room_id: UUID,
    service: WorkflowServiceDep,
) -> WorkflowListResponse:
    """Room の Workflow 一覧を取得する。

    - 404: Room が存在しない場合 (``RoomNotFoundError``)
    """
    workflow = await service.find_by_room(room_id)
    items = [WorkflowResponse.model_validate(workflow)] if workflow is not None else []
    return WorkflowListResponse(items=items, total=len(items))


@workflows_router.get(
    "/presets",
    status_code=200,
    response_model=WorkflowPresetListResponse,
)
async def get_presets(
    service: WorkflowServiceDep,
) -> WorkflowPresetListResponse:
    """利用可能な Workflow プリセット一覧を返す。"""
    presets = service.get_presets()
    items = [
        WorkflowPresetResponse(
            preset_name=p.preset_name,
            display_name=p.display_name,
            description=p.description,
            stage_count=p.stage_count,
            transition_count=p.transition_count,
        )
        for p in presets
    ]
    return WorkflowPresetListResponse(items=items, total=len(items))


@workflows_router.get(
    "/{workflow_id}",
    status_code=200,
    response_model=WorkflowResponse,
)
async def get_workflow(
    workflow_id: UUID,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Workflow を単件取得する。

    - 404: Workflow が存在しない場合 (``WorkflowNotFoundError``)
    """
    workflow = await service.find_by_id(workflow_id)
    return WorkflowResponse.model_validate(workflow)


@workflows_router.patch(
    "/{workflow_id}",
    status_code=200,
    response_model=WorkflowResponse,
)
async def update_workflow(
    workflow_id: UUID,
    body: WorkflowUpdate,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Workflow を部分更新する。

    - 404: Workflow が存在しない場合 (``WorkflowNotFoundError``)
    - 409: アーカイブ済み Workflow への更新 (``WorkflowArchivedError``)
    - 422: Workflow 不変条件違反 (``WorkflowInvariantViolation``)
    """
    workflow = await service.update(
        workflow_id=workflow_id,
        name=body.name,
        stages=[s.model_dump() for s in body.stages] if body.stages is not None else None,
        transitions=(
            [t.model_dump() for t in body.transitions] if body.transitions is not None else None
        ),
        entry_stage_id=body.entry_stage_id,
    )
    return WorkflowResponse.model_validate(workflow)


@workflows_router.delete(
    "/{workflow_id}",
    status_code=204,
)
async def archive_workflow(
    workflow_id: UUID,
    service: WorkflowServiceDep,
) -> Response:
    """Workflow を論理削除する (archived=True)。

    - 204: 成功 (No Content)
    - 404: Workflow が存在しない場合 (``WorkflowNotFoundError``)
    """
    await service.archive(workflow_id)
    return Response(status_code=204)


@workflows_router.get(
    "/{workflow_id}/stages",
    status_code=200,
    response_model=StageListResponse,
)
async def get_stages(
    workflow_id: UUID,
    service: WorkflowServiceDep,
) -> StageListResponse:
    """Workflow のステージ一覧を取得する。

    - 404: Workflow が存在しない場合 (``WorkflowNotFoundError``)
    """
    stages, transitions, entry_stage_id = await service.find_stages(workflow_id)
    return StageListResponse(
        stages=[StageResponse.model_validate(s) for s in stages],
        transitions=[TransitionResponse.model_validate(t) for t in transitions],
        entry_stage_id=str(entry_stage_id),
    )


__all__ = ["room_workflows_router", "workflows_router"]
