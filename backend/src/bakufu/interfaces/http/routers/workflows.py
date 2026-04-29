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
from bakufu.interfaces.http.dependencies import HttpDependencies
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

WorkflowServiceDep = Annotated[WorkflowService, Depends(HttpDependencies.get_workflow_service)]


class WorkflowHttpRoutes:
    """Workflow HTTP 入口をクラスメソッドに閉じる。"""

    @classmethod
    async def create_workflow(
        cls,
        room_id: UUID,
        body: WorkflowCreate,
        service: WorkflowServiceDep,
    ) -> WorkflowResponse:
        """Room に Workflow を作成する。"""
        workflow = await service.create_for_room(
            room_id=room_id,
            preset_name=body.preset_name,
            name=body.name,
            stages=([s.model_dump() for s in body.stages] if body.stages is not None else None),
            transitions=(
                [t.model_dump() for t in body.transitions] if body.transitions is not None else None
            ),
            entry_stage_id=body.entry_stage_id,
        )
        return WorkflowResponse.model_validate(workflow)

    @classmethod
    async def list_workflows(
        cls,
        room_id: UUID,
        service: WorkflowServiceDep,
    ) -> WorkflowListResponse:
        """Room の Workflow 一覧を取得する。"""
        workflow = await service.find_by_room(room_id)
        items = [WorkflowResponse.model_validate(workflow)] if workflow is not None else []
        return WorkflowListResponse(items=items, total=len(items))

    @classmethod
    async def get_presets(
        cls,
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

    @classmethod
    async def get_workflow(
        cls,
        workflow_id: UUID,
        service: WorkflowServiceDep,
    ) -> WorkflowResponse:
        """Workflow を単件取得する。"""
        workflow = await service.find_by_id(workflow_id)
        return WorkflowResponse.model_validate(workflow)

    @classmethod
    async def update_workflow(
        cls,
        workflow_id: UUID,
        body: WorkflowUpdate,
        service: WorkflowServiceDep,
    ) -> WorkflowResponse:
        """Workflow を部分更新する。"""
        workflow = await service.update(
            workflow_id=workflow_id,
            name=body.name,
            stages=([s.model_dump() for s in body.stages] if body.stages is not None else None),
            transitions=(
                [t.model_dump() for t in body.transitions] if body.transitions is not None else None
            ),
            entry_stage_id=body.entry_stage_id,
        )
        return WorkflowResponse.model_validate(workflow)

    @classmethod
    async def archive_workflow(
        cls,
        workflow_id: UUID,
        service: WorkflowServiceDep,
    ) -> Response:
        """Workflow を論理削除する (archived=True)。"""
        await service.archive(workflow_id)
        return Response(status_code=204)

    @classmethod
    async def get_stages(
        cls,
        workflow_id: UUID,
        service: WorkflowServiceDep,
    ) -> StageListResponse:
        """Workflow のステージ一覧を取得する。"""
        stages, transitions, entry_stage_id = await service.find_stages(workflow_id)
        return StageListResponse(
            stages=[StageResponse.model_validate(s) for s in stages],
            transitions=[TransitionResponse.model_validate(t) for t in transitions],
            entry_stage_id=str(entry_stage_id),
        )


room_workflows_router.add_api_route(
    "/{room_id}/workflows",
    WorkflowHttpRoutes.create_workflow,
    methods=["POST"],
    status_code=201,
    response_model=WorkflowResponse,
)
room_workflows_router.add_api_route(
    "/{room_id}/workflows",
    WorkflowHttpRoutes.list_workflows,
    methods=["GET"],
    status_code=200,
    response_model=WorkflowListResponse,
)
workflows_router.add_api_route(
    "/presets",
    WorkflowHttpRoutes.get_presets,
    methods=["GET"],
    status_code=200,
    response_model=WorkflowPresetListResponse,
)
workflows_router.add_api_route(
    "/{workflow_id}",
    WorkflowHttpRoutes.get_workflow,
    methods=["GET"],
    status_code=200,
    response_model=WorkflowResponse,
)
workflows_router.add_api_route(
    "/{workflow_id}",
    WorkflowHttpRoutes.update_workflow,
    methods=["PATCH"],
    status_code=200,
    response_model=WorkflowResponse,
)
workflows_router.add_api_route(
    "/{workflow_id}",
    WorkflowHttpRoutes.archive_workflow,
    methods=["DELETE"],
    status_code=204,
)
workflows_router.add_api_route(
    "/{workflow_id}/stages",
    WorkflowHttpRoutes.get_stages,
    methods=["GET"],
    status_code=200,
    response_model=StageListResponse,
)


__all__ = ["room_workflows_router", "workflows_router"]
