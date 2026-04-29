"""Empire CRUD エンドポイント (確定 E).

5本のエンドポイントを実装する:
  POST   /api/empires          → 201 EmpireResponse
  GET    /api/empires          → 200 EmpireListResponse
  GET    /api/empires/{id}     → 200 EmpireResponse
  PATCH  /api/empires/{id}     → 200 EmpireResponse
  DELETE /api/empires/{id}     → 204 No Content

Router 内には ``try/except`` を書かない (http-api-foundation architecture 規律)。
例外は ``app.py`` に登録された専用ハンドラが処理する (確定 B / 確定 C)。

``empire_id`` パスパラメータは ``str`` で受け取り、
``EmpireId(UUID(empire_id))`` に変換する。不正な UUID 形式は
FastAPI の path validation で 422 を返す。
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from bakufu.application.services.empire_service import EmpireService
from bakufu.domain.value_objects.identifiers import EmpireId
from bakufu.interfaces.http.dependencies import get_empire_service
from bakufu.interfaces.http.schemas.empire import (
    AgentRefResponse,
    EmpireCreate,
    EmpireListResponse,
    EmpireResponse,
    EmpireUpdate,
    RoomRefResponse,
)

router = APIRouter(prefix="/api/empires", tags=["empire"])

EmpireServiceDep = Annotated[EmpireService, Depends(get_empire_service)]


def _to_empire_response(empire: object) -> EmpireResponse:
    """domain ``Empire`` → ``EmpireResponse`` 変換。

    ``Empire.id`` は ``EmpireId`` (UUID) のため ``str()`` で文字列化する。
    ``rooms`` / ``agents`` も各 Ref → Response スキーマへマップする。
    """
    from bakufu.domain.empire import Empire

    if not isinstance(empire, Empire):
        raise TypeError(f"Expected Empire, got {type(empire).__name__}")

    rooms = [
        RoomRefResponse(
            room_id=str(ref.room_id),
            name=ref.name,
            archived=ref.archived,
        )
        for ref in empire.rooms
    ]
    agents = [
        AgentRefResponse(
            agent_id=str(ref.agent_id),
            name=ref.name,
            role=ref.role.value,
        )
        for ref in empire.agents
    ]
    return EmpireResponse(
        id=str(empire.id),
        name=empire.name,
        archived=empire.archived,
        rooms=rooms,
        agents=agents,
    )


@router.post("", status_code=201, response_model=EmpireResponse)
async def create_empire(
    body: EmpireCreate,
    service: EmpireServiceDep,
) -> EmpireResponse:
    """Empire を新規作成する (REQ-EM-HTTP-001)。

    - 409: Empire が既に存在する場合 (``EmpireAlreadyExistsError``)
    - 422: name が 1〜80 文字を超える場合
    """
    empire = await service.create(body.name)
    return _to_empire_response(empire)


@router.get("", status_code=200, response_model=EmpireListResponse)
async def list_empires(
    service: EmpireServiceDep,
) -> EmpireListResponse:
    """Empire 一覧を取得する (REQ-EM-HTTP-002)。

    シングルトンのため 0 件または 1 件。空リストは 200 で返す。
    """
    empires = await service.find_all()
    items = [_to_empire_response(e) for e in empires]
    return EmpireListResponse(items=items, total=len(items))


@router.get("/{empire_id}", status_code=200, response_model=EmpireResponse)
async def get_empire(
    empire_id: str,
    service: EmpireServiceDep,
) -> EmpireResponse:
    """Empire を単件取得する (REQ-EM-HTTP-003)。

    - 404: 対象 Empire が存在しない場合 (``EmpireNotFoundError``)
    - 422: ``empire_id`` が不正な UUID 形式の場合
    """
    # EmpireId is a type alias for UUID — UUID() constructs the correct type.
    eid: EmpireId = UUID(empire_id)
    empire = await service.find_by_id(eid)
    return _to_empire_response(empire)


@router.patch("/{empire_id}", status_code=200, response_model=EmpireResponse)
async def update_empire(
    empire_id: str,
    body: EmpireUpdate,
    service: EmpireServiceDep,
) -> EmpireResponse:
    """Empire を部分更新する (REQ-EM-HTTP-004)。

    - 404: 対象 Empire が存在しない場合 (``EmpireNotFoundError``)
    - 409: アーカイブ済み Empire への更新 (``EmpireArchivedError``)
    - 422: name が 1〜80 文字を超える場合 / 不正 UUID
    """
    eid: EmpireId = UUID(empire_id)
    empire = await service.update(eid, body.name)
    return _to_empire_response(empire)


@router.delete("/{empire_id}", status_code=204)
async def delete_empire(
    empire_id: str,
    service: EmpireServiceDep,
) -> Response:
    """Empire を論理削除する (REQ-EM-HTTP-005 / UC-EM-010)。

    ``archived=True`` に設定して永続化する。物理削除は行わない。

    - 204: 成功 (No Content)
    - 404: 対象 Empire が存在しない場合 (``EmpireNotFoundError``)
    """
    eid: EmpireId = UUID(empire_id)
    await service.archive(eid)
    return Response(status_code=204)


__all__ = ["router"]
