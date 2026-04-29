"""Empire CRUD エンドポイント (確定 E).

5本のエンドポイントを実装する:
  POST   /api/empires          -> 201 EmpireResponse
  GET    /api/empires          -> 200 EmpireListResponse
  GET    /api/empires/{id}     -> 200 EmpireResponse
  PATCH  /api/empires/{id}     -> 200 EmpireResponse
  DELETE /api/empires/{id}     -> 204 No Content

Router 内には ``try/except`` を書かない (http-api-foundation architecture 規律)。
例外は ``app.py`` に登録された専用ハンドラが処理する (確定 B / 確定 C)。

domain 層への import はゼロ (Q-3 interfaces->domain 直接依存禁止)。
``Empire`` → ``EmpireResponse`` の変換は ``EmpireResponse.model_validate(empire)``
が ``from_attributes=True`` + schema 側 ``field_validator`` で完結する。

``empire_id`` パスパラメータは ``UUID`` 型で宣言し、FastAPI の path validation に
UUID 形式検証を委ねる。不正な UUID 形式は FastAPI が 422 を返す。
``EmpireId`` は ``UUID`` の型エイリアスのため domain import は不要。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response

from bakufu.interfaces.http.dependencies import EmpireServiceDep
from bakufu.interfaces.http.schemas.empire import (
    EmpireCreate,
    EmpireListResponse,
    EmpireResponse,
    EmpireUpdate,
)

router = APIRouter(prefix="/api/empires", tags=["empire"])


@router.post("", status_code=201, response_model=EmpireResponse)
async def create_empire(
    body: EmpireCreate,
    service: EmpireServiceDep,
) -> EmpireResponse:
    """Empire を新規作成する (REQ-EM-HTTP-001)。

    - 409: Empire が既に存在する場合 (``EmpireAlreadyExistsError``)
    - 422: name が 1-80 文字を超える場合
    """
    empire = await service.create(body.name)
    return EmpireResponse.model_validate(empire)


@router.get("", status_code=200, response_model=EmpireListResponse)
async def list_empires(
    service: EmpireServiceDep,
) -> EmpireListResponse:
    """Empire 一覧を取得する (REQ-EM-HTTP-002)。

    シングルトンのため 0 件または 1 件。空リストは 200 で返す。
    """
    empires = await service.find_all()
    items = [EmpireResponse.model_validate(e) for e in empires]
    return EmpireListResponse(items=items, total=len(items))


@router.get("/{empire_id}", status_code=200, response_model=EmpireResponse)
async def get_empire(
    empire_id: UUID,
    service: EmpireServiceDep,
) -> EmpireResponse:
    """Empire を単件取得する (REQ-EM-HTTP-003)。

    - 404: 対象 Empire が存在しない場合 (``EmpireNotFoundError``)
    - 422: ``empire_id`` が不正な UUID 形式の場合 (FastAPI path validation)
    """
    empire = await service.find_by_id(empire_id)
    return EmpireResponse.model_validate(empire)


@router.patch("/{empire_id}", status_code=200, response_model=EmpireResponse)
async def update_empire(
    empire_id: UUID,
    body: EmpireUpdate,
    service: EmpireServiceDep,
) -> EmpireResponse:
    """Empire を部分更新する (REQ-EM-HTTP-004)。

    - 404: 対象 Empire が存在しない場合 (``EmpireNotFoundError``)
    - 409: アーカイブ済み Empire への更新 (``EmpireArchivedError``)
    - 422: name が 1-80 文字を超える場合 / 不正 UUID (FastAPI path validation)
    """
    empire = await service.update(empire_id, body.name)
    return EmpireResponse.model_validate(empire)


@router.delete("/{empire_id}", status_code=204)
async def delete_empire(
    empire_id: UUID,
    service: EmpireServiceDep,
) -> Response:
    """Empire を論理削除する (REQ-EM-HTTP-005 / UC-EM-010)。

    ``archived=True`` に設定して永続化する。物理削除は行わない。

    - 204: 成功 (No Content)
    - 404: 対象 Empire が存在しない場合 (``EmpireNotFoundError``)
    - 422: ``empire_id`` が不正な UUID 形式の場合 (FastAPI path validation)
    """
    await service.archive(empire_id)
    return Response(status_code=204)


__all__ = ["router"]
