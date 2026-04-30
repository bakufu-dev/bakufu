"""RoleProfile CRUD エンドポイント。

4 本のエンドポイントを実装する（prefix: /api/empires/{empire_id}/role-profiles）:
  GET    /api/empires/{empire_id}/role-profiles          -> 200 RoleProfileListResponse
  GET    /api/empires/{empire_id}/role-profiles/{role}   -> 200 RoleProfileResponse
  PUT    /api/empires/{empire_id}/role-profiles/{role}   -> 200 RoleProfileResponse
  DELETE /api/empires/{empire_id}/role-profiles/{role}   -> 204 No Content

Router 内には ``try/except`` を書かない（http-api-foundation architecture 規律）。
例外は ``app.py`` に登録された専用ハンドラが処理する。

``empire_id`` パスパラメータは ``UUID`` 型で宣言し、FastAPI の path validation に
UUID 形式検証を委ねる。``role`` は ``str`` パスパラメータとして受け取り、
Service が ``Role`` StrEnum に変換する（不正値は Pydantic / ValueError が 422 を返す）。

domain 層への import はゼロ（Q-3 interfaces->domain 直接依存禁止）。
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from bakufu.application.services.role_profile_service import RoleProfileService
from bakufu.interfaces.http.dependencies import get_role_profile_service
from bakufu.interfaces.http.schemas.role_profile import (
    RoleProfileListResponse,
    RoleProfileResponse,
    RoleProfileUpsertRequest,
)

router = APIRouter(
    prefix="/api/empires/{empire_id}/role-profiles",
    tags=["role-profile"],
)

RoleProfileServiceDep = Annotated[RoleProfileService, Depends(get_role_profile_service)]


@router.get("", status_code=200, response_model=RoleProfileListResponse)
async def list_role_profiles(
    empire_id: UUID,
    service: RoleProfileServiceDep,
) -> RoleProfileListResponse:
    """Empire の RoleProfile 全件取得（REQ-RP-HTTP-001）。

    - 200: 空リストも含む
    - 404: Empire が存在しない場合（MSG-RP-HTTP-003）
    """
    profiles = await service.find_all_by_empire(empire_id)
    items = [RoleProfileResponse.model_validate(p) for p in profiles]
    return RoleProfileListResponse(items=items, total=len(items))


@router.get("/{role}", status_code=200, response_model=RoleProfileResponse)
async def get_role_profile(
    empire_id: UUID,
    role: str,
    service: RoleProfileServiceDep,
) -> RoleProfileResponse:
    """Empire × Role の RoleProfile 単件取得（REQ-RP-HTTP-002）。

    - 404: 対象 RoleProfile が存在しない場合（MSG-RP-HTTP-001）
    - 422: role が不正な値の場合
    """
    profile = await service.find_by_empire_and_role_str(empire_id, role)
    return RoleProfileResponse.model_validate(profile)


@router.put("/{role}", status_code=200, response_model=RoleProfileResponse)
async def upsert_role_profile(
    empire_id: UUID,
    role: str,
    body: RoleProfileUpsertRequest,
    service: RoleProfileServiceDep,
) -> RoleProfileResponse:
    """RoleProfile の Upsert（REQ-RP-HTTP-003 / §確定 C 冪等設計）。

    - 200: Upsert 成功
    - 404: Empire が存在しない場合（MSG-RP-HTTP-003）
    - 422: ref 不在（MSG-RP-HTTP-002）/ role 不正値 / 不変条件違反
    """
    profile = await service.upsert(
        empire_id=empire_id,
        role=role,
        refs=[
            {
                "template_id": ref.template_id,
                "minimum_version": {
                    "major": ref.minimum_version.major,
                    "minor": ref.minimum_version.minor,
                    "patch": ref.minimum_version.patch,
                },
            }
            for ref in body.deliverable_template_refs
        ],
    )
    return RoleProfileResponse.model_validate(profile)


@router.delete("/{role}", status_code=204)
async def delete_role_profile(
    empire_id: UUID,
    role: str,
    service: RoleProfileServiceDep,
) -> Response:
    """RoleProfile を削除する（REQ-RP-HTTP-004）。

    - 204: 成功（No Content）
    - 404: 対象 RoleProfile が存在しない場合（MSG-RP-HTTP-001）
    """
    await service.delete(empire_id=empire_id, role=role)
    return Response(status_code=204)


__all__ = ["router"]
