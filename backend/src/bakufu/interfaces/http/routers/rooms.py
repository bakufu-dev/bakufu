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

from bakufu.application.services.room_service import RoomService
from bakufu.interfaces.http.dependencies import HttpDependencies
from bakufu.interfaces.http.schemas.room import (
    AgentAssignRequest,
    RoomCreate,
    RoomListResponse,
    RoomResponse,
    RoomUpdate,
)

# 2 つの router: empire スコープ / room スコープ (確定 E)
empire_rooms_router = APIRouter(prefix="/api/empires", tags=["room"])
rooms_router = APIRouter(prefix="/api/rooms", tags=["room"])

RoomServiceDep = Annotated[RoomService, Depends(HttpDependencies.get_room_service)]


class RoomHttpRoutes:
    """Room HTTP 入口をクラスメソッドに閉じる。"""

    @classmethod
    async def create_room(
        cls,
        empire_id: UUID,
        body: RoomCreate,
        service: RoomServiceDep,
    ) -> RoomResponse:
        """Room を新規作成する (REQ-RM-HTTP-001)。"""
        room = await service.create(
            empire_id=empire_id,
            name=body.name,
            description=body.description,
            workflow_id=body.workflow_id,
            prompt_kit_prefix_markdown=body.prompt_kit_prefix_markdown,
        )
        return RoomResponse.model_validate(room)

    @classmethod
    async def list_rooms(
        cls,
        empire_id: UUID,
        service: RoomServiceDep,
    ) -> RoomListResponse:
        """Empire スコープの Room 一覧を取得する (REQ-RM-HTTP-002)。"""
        rooms = await service.find_all_by_empire(empire_id)
        items = [RoomResponse.model_validate(r) for r in rooms]
        return RoomListResponse(items=items, total=len(items))

    @classmethod
    async def get_room(
        cls,
        room_id: UUID,
        service: RoomServiceDep,
    ) -> RoomResponse:
        """Room を単件取得する (REQ-RM-HTTP-003)。"""
        room = await service.find_by_id(room_id)
        return RoomResponse.model_validate(room)

    @classmethod
    async def update_room(
        cls,
        room_id: UUID,
        body: RoomUpdate,
        service: RoomServiceDep,
    ) -> RoomResponse:
        """Room を部分更新する (REQ-RM-HTTP-004)。"""
        room = await service.update(
            room_id=room_id,
            name=body.name,
            description=body.description,
            prompt_kit_prefix_markdown=body.prompt_kit_prefix_markdown,
        )
        return RoomResponse.model_validate(room)

    @classmethod
    async def archive_room(
        cls,
        room_id: UUID,
        service: RoomServiceDep,
    ) -> Response:
        """Room を論理削除する (REQ-RM-HTTP-005 / UC-RM-010)。"""
        await service.archive(room_id)
        return Response(status_code=204)

    @classmethod
    async def assign_agent(
        cls,
        room_id: UUID,
        body: AgentAssignRequest,
        service: RoomServiceDep,
    ) -> RoomResponse:
        """Room に Agent を割り当てる (REQ-RM-HTTP-006)。"""
        room = await service.assign_agent(
            room_id=room_id,
            agent_id=body.agent_id,
            role=body.role,
        )
        return RoomResponse.model_validate(room)

    @classmethod
    async def unassign_agent(
        cls,
        room_id: UUID,
        agent_id: UUID,
        role: str,
        service: RoomServiceDep,
    ) -> Response:
        """Room から Agent の役割割り当てを解除する (REQ-RM-HTTP-007)。"""
        await service.unassign_agent(room_id=room_id, agent_id=agent_id, role=role)
        return Response(status_code=204)


empire_rooms_router.add_api_route(
    "/{empire_id}/rooms",
    RoomHttpRoutes.create_room,
    methods=["POST"],
    status_code=201,
    response_model=RoomResponse,
)
empire_rooms_router.add_api_route(
    "/{empire_id}/rooms",
    RoomHttpRoutes.list_rooms,
    methods=["GET"],
    status_code=200,
    response_model=RoomListResponse,
)
rooms_router.add_api_route(
    "/{room_id}",
    RoomHttpRoutes.get_room,
    methods=["GET"],
    status_code=200,
    response_model=RoomResponse,
)
rooms_router.add_api_route(
    "/{room_id}",
    RoomHttpRoutes.update_room,
    methods=["PATCH"],
    status_code=200,
    response_model=RoomResponse,
)
rooms_router.add_api_route(
    "/{room_id}",
    RoomHttpRoutes.archive_room,
    methods=["DELETE"],
    status_code=204,
)
rooms_router.add_api_route(
    "/{room_id}/agents",
    RoomHttpRoutes.assign_agent,
    methods=["POST"],
    status_code=201,
    response_model=RoomResponse,
)
rooms_router.add_api_route(
    "/{room_id}/agents/{agent_id}/roles/{role}",
    RoomHttpRoutes.unassign_agent,
    methods=["DELETE"],
    status_code=204,
)


__all__ = ["empire_rooms_router", "rooms_router"]
