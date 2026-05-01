"""Room CRUD + Agent 割り当て/解除エンドポイント (確定 E).

7 本のエンドポイントを 2 つの APIRouter で実装する:
  empire_rooms_router (prefix="/api/empires"):
    POST   /api/empires/{empire_id}/rooms       -> 201 RoomResponse
    GET    /api/empires/{empire_id}/rooms        -> 200 RoomListResponse

  rooms_router (prefix="/api/rooms"):
    GET    /api/rooms/{room_id}                  -> 200 RoomResponse
    PATCH  /api/rooms/{room_id}                  -> 200 RoomResponse
    DELETE /api/rooms/{room_id}                  -> 204 No Content
    POST   /api/rooms/{room_id}/agents           -> 201 RoomResponse
    DELETE /api/rooms/{room_id}/agents/{agent_id}/roles/{role} -> 204 No Content

Router 内には ``try/except`` を書かない (http-api-foundation architecture 規律)。
例外は ``app.py`` に登録された専用ハンドラが処理する (確定 B / 確定 C)。

domain 層への import はゼロ (Q-3 interfaces->domain 直接依存禁止)。
``Room`` → ``RoomResponse`` の変換は ``RoomResponse.model_validate(room)``
が ``from_attributes=True`` + schema 側 ``model_validator(mode='before')`` で完結する。

すべてのパスパラメータ UUID 型は FastAPI の path validation に委ねる
(不正な UUID 形式は FastAPI が 422 を返す / 業務ルール R1-10)。
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from bakufu.application.services.room_role_override_service import RoomRoleOverrideService
from bakufu.application.services.room_service import RoomService
from bakufu.interfaces.http.dependencies import (
    get_room_role_override_service,
    get_room_service,
)
from bakufu.interfaces.http.schemas.room import (
    AgentAssignRequest,
    RoomCreate,
    RoomListResponse,
    RoomResponse,
    RoomRoleOverrideListResponse,
    RoomRoleOverrideRequest,
    RoomRoleOverrideResponse,
    RoomUpdate,
)

# 2 つの router: empire スコープ / room スコープ (確定 E)
empire_rooms_router = APIRouter(prefix="/api/empires", tags=["room"])
rooms_router = APIRouter(prefix="/api/rooms", tags=["room"])

RoomServiceDep = Annotated[RoomService, Depends(get_room_service)]


@empire_rooms_router.post(
    "/{empire_id}/rooms",
    status_code=201,
    response_model=RoomResponse,
)
async def create_room(
    empire_id: UUID,
    body: RoomCreate,
    service: RoomServiceDep,
) -> RoomResponse:
    """Room を新規作成する (REQ-RM-HTTP-001)。

    - 404: Empire が存在しない場合 (``EmpireNotFoundError``)
    - 404: Workflow が存在しない場合 (``WorkflowNotFoundError``)
    - 409: 同 Empire 内で同名 Room が既に存在する場合 (``RoomNameAlreadyExistsError``)
    - 422: name / description / prompt_kit_prefix_markdown が制約違反の場合
    - 422: 不正 UUID (FastAPI path validation)
    """
    room = await service.create(
        empire_id=empire_id,
        name=body.name,
        description=body.description,
        workflow_id=body.workflow_id,
        prompt_kit_prefix_markdown=body.prompt_kit_prefix_markdown,
    )
    return RoomResponse.model_validate(room)


@empire_rooms_router.get(
    "/{empire_id}/rooms",
    status_code=200,
    response_model=RoomListResponse,
)
async def list_rooms(
    empire_id: UUID,
    service: RoomServiceDep,
) -> RoomListResponse:
    """Empire スコープの Room 一覧を取得する (REQ-RM-HTTP-002)。

    空リストも 200 で返す (items=[], total=0)。

    - 404: Empire が存在しない場合 (``EmpireNotFoundError``)
    - 422: 不正 UUID (FastAPI path validation)
    """
    rooms = await service.find_all_by_empire(empire_id)
    items = [RoomResponse.model_validate(r) for r in rooms]
    return RoomListResponse(items=items, total=len(items))


@rooms_router.get("/{room_id}", status_code=200, response_model=RoomResponse)
async def get_room(
    room_id: UUID,
    service: RoomServiceDep,
) -> RoomResponse:
    """Room を単件取得する (REQ-RM-HTTP-003)。

    - 404: 対象 Room が存在しない場合 (``RoomNotFoundError``)
    - 422: 不正 UUID (FastAPI path validation)
    """
    room = await service.find_by_id(room_id)
    return RoomResponse.model_validate(room)


@rooms_router.patch("/{room_id}", status_code=200, response_model=RoomResponse)
async def update_room(
    room_id: UUID,
    body: RoomUpdate,
    service: RoomServiceDep,
) -> RoomResponse:
    """Room を部分更新する (REQ-RM-HTTP-004)。

    - 404: 対象 Room が存在しない場合 (``RoomNotFoundError``)
    - 409: アーカイブ済み Room への更新 (``RoomArchivedError``)
    - 422: name / description / prompt_kit_prefix_markdown が制約違反の場合
    - 422: 不正 UUID (FastAPI path validation)
    """
    room = await service.update(
        room_id=room_id,
        name=body.name,
        description=body.description,
        prompt_kit_prefix_markdown=body.prompt_kit_prefix_markdown,
    )
    return RoomResponse.model_validate(room)


@rooms_router.delete("/{room_id}", status_code=204)
async def archive_room(
    room_id: UUID,
    service: RoomServiceDep,
) -> Response:
    """Room を論理削除する (REQ-RM-HTTP-005 / UC-RM-010)。

    ``archived=True`` に設定して永続化する。物理削除は行わない。

    - 204: 成功 (No Content)
    - 404: 対象 Room が存在しない場合 (``RoomNotFoundError``)
    - 422: 不正 UUID (FastAPI path validation)
    """
    await service.archive(room_id)
    return Response(status_code=204)


@rooms_router.post("/{room_id}/agents", status_code=201, response_model=RoomResponse)
async def assign_agent(
    room_id: UUID,
    body: AgentAssignRequest,
    service: RoomServiceDep,
) -> RoomResponse:
    """Room に Agent を割り当てる (REQ-RM-HTTP-006)。

    - 404: Room が存在しない場合 (``RoomNotFoundError``)
    - 404: Agent が存在しない場合 (``AgentNotFoundError``)
    - 409: アーカイブ済み Room への操作 (``RoomArchivedError``)
    - 422: ``(agent_id, role)`` 重複 / capacity 超過 (``RoomInvariantViolation``)
    - 422: deliverable coverage 不足 (``RoomDeliverableMatchingError``)
    - 422: 不正 UUID / 無効な role 値 (FastAPI / schema validation)
    """
    # custom_refs を dict リストに変換して service に渡す（Q-3: domain 型を import しない）
    # service 内で DeliverableTemplateRef.model_validate(d) により domain VO に変換する。
    custom_refs_dicts = (
        [ref.model_dump() for ref in body.custom_refs] if body.custom_refs is not None else None
    )
    room = await service.assign_agent(
        room_id=room_id,
        agent_id=body.agent_id,
        role=body.role,
        custom_refs=custom_refs_dicts,
    )
    return RoomResponse.model_validate(room)


@rooms_router.delete(
    "/{room_id}/agents/{agent_id}/roles/{role}",
    status_code=204,
)
async def unassign_agent(
    room_id: UUID,
    agent_id: UUID,
    role: str,
    service: RoomServiceDep,
) -> Response:
    """Room から Agent の役割割り当てを解除する (REQ-RM-HTTP-007)。

    ``role`` パスパラメータで ``(agent_id, role)`` ペアを一意識別する。
    無効な role 値は ``RoomInvariantViolation(kind='member_not_found')`` → 404 で返す
    (型バリデーションを domain に委ねることで HTTP 層の責務を最小化する / 確定 E)。

    - 204: 成功 (No Content)
    - 404: Room が存在しない場合 (``RoomNotFoundError``)
    - 404: 指定した membership が存在しない場合 / 無効 role
      (``RoomInvariantViolation`` kind=member_not_found)
    - 409: アーカイブ済み Room への操作 (``RoomArchivedError``)
    - 422: 不正 UUID (FastAPI path validation)
    """
    await service.unassign_agent(room_id=room_id, agent_id=agent_id, role=role)
    return Response(status_code=204)


# ── RoomRoleOverride エンドポイント ───────────────────────────────────────────

RoomRoleOverrideServiceDep = Annotated[
    RoomRoleOverrideService, Depends(get_room_role_override_service)
]


@rooms_router.put(
    "/{room_id}/role-overrides/{role}",
    status_code=200,
    response_model=RoomRoleOverrideResponse,
)
async def upsert_room_role_override(
    room_id: UUID,
    role: str,
    body: RoomRoleOverrideRequest,
    service: RoomRoleOverrideServiceDep,
) -> RoomRoleOverrideResponse:
    """Room スコープのロール別 deliverable template オーバーライドを UPSERT する。

    - 404: Room が存在しない場合 (``RoomNotFoundError``)
    - 409: アーカイブ済み Room への操作 (``RoomArchivedError``)
    - 422: deliverable_template_refs に重複がある場合 (``RoomRoleOverrideInvariantViolation``)
    - 422: 無効な role 値 (``InvalidRoleError``)
    """
    # service が role str → Role 変換と refs dict → domain VO 変換を担う（Q-3 遵守）
    override = await service.upsert_override(
        room_id=room_id,
        role=role,
        refs=[ref.model_dump() for ref in body.deliverable_template_refs],
    )
    return RoomRoleOverrideResponse.model_validate(override)


@rooms_router.delete(
    "/{room_id}/role-overrides/{role}",
    status_code=204,
)
async def delete_room_role_override(
    room_id: UUID,
    role: str,
    service: RoomRoleOverrideServiceDep,
) -> Response:
    """Room スコープのロール別 deliverable template オーバーライドを削除する。

    対象が存在しない場合は no-op で 204 を返す。

    - 204: 成功 (No Content)
    - 404: Room が存在しない場合 (``RoomNotFoundError``)
    - 409: アーカイブ済み Room への操作 (``RoomArchivedError``)
    - 422: 無効な role 値 (``InvalidRoleError``)
    """
    # service が role str → Role 変換を担う（Q-3 遵守）
    await service.delete_override(room_id=room_id, role=role)
    return Response(status_code=204)


@rooms_router.get(
    "/{room_id}/role-overrides",
    status_code=200,
    response_model=RoomRoleOverrideListResponse,
)
async def list_room_role_overrides(
    room_id: UUID,
    service: RoomRoleOverrideServiceDep,
) -> RoomRoleOverrideListResponse:
    """Room スコープの全ロール別 deliverable template オーバーライドを一覧取得する。

    - 200: 成功（空リストも 200 で返す）
    - 404: Room が存在しない場合 (``RoomNotFoundError``)
    - 422: 不正 UUID (FastAPI path validation)
    """
    overrides = await service.find_overrides(room_id=room_id)
    items = [RoomRoleOverrideResponse.model_validate(o) for o in overrides]
    return RoomRoleOverrideListResponse(items=items, total=len(items))


__all__ = ["empire_rooms_router", "rooms_router"]
