"""DeliverableTemplate CRUD エンドポイント。

5 本のエンドポイントを実装する:
  POST   /api/deliverable-templates          -> 201 DeliverableTemplateResponse
  GET    /api/deliverable-templates          -> 200 DeliverableTemplateListResponse
  GET    /api/deliverable-templates/{id}     -> 200 DeliverableTemplateResponse
  PUT    /api/deliverable-templates/{id}     -> 200 DeliverableTemplateResponse
  DELETE /api/deliverable-templates/{id}     -> 204 No Content

Router 内には ``try/except`` を書かない（http-api-foundation architecture 規律）。
例外は ``app.py`` に登録された専用ハンドラが処理する。

``template_id`` パスパラメータは ``UUID`` 型で宣言し、FastAPI の path validation に
UUID 形式検証を委ねる。

domain 層への import はゼロ（Q-3 interfaces->domain 直接依存禁止）。
schema → service のデータ変換は service が dict 形式で受け取り内部で変換する。
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from bakufu.application.services.deliverable_template_service import (
    DeliverableTemplateService,
)
from bakufu.interfaces.http.dependencies import get_deliverable_template_service
from bakufu.interfaces.http.schemas.deliverable_template import (
    DeliverableTemplateCreate,
    DeliverableTemplateListResponse,
    DeliverableTemplateResponse,
    DeliverableTemplateUpdate,
)

router = APIRouter(prefix="/api/deliverable-templates", tags=["deliverable-template"])

DeliverableTemplateServiceDep = Annotated[
    DeliverableTemplateService, Depends(get_deliverable_template_service)
]


@router.post("", status_code=201, response_model=DeliverableTemplateResponse)
async def create_deliverable_template(
    body: DeliverableTemplateCreate,
    service: DeliverableTemplateServiceDep,
) -> DeliverableTemplateResponse:
    """DeliverableTemplate を新規作成する（REQ-DT-HTTP-001）。

    - 422: Pydantic バリデーション失敗 / 不変条件違反 / DAG 循環 / ref 不在
    """
    template = await service.create(
        name=body.name,
        description=body.description,
        type_=body.type,
        schema=body.schema,
        acceptance_criteria=[
            {"id": ac.id, "description": ac.description, "required": ac.required}
            for ac in body.acceptance_criteria
        ],
        version={
            "major": body.version.major,
            "minor": body.version.minor,
            "patch": body.version.patch,
        },
        composition=[
            {
                "template_id": ref.template_id,
                "minimum_version": {
                    "major": ref.minimum_version.major,
                    "minor": ref.minimum_version.minor,
                    "patch": ref.minimum_version.patch,
                },
            }
            for ref in body.composition
        ],
    )
    return DeliverableTemplateResponse.model_validate(template)


@router.get("", status_code=200, response_model=DeliverableTemplateListResponse)
async def list_deliverable_templates(
    service: DeliverableTemplateServiceDep,
) -> DeliverableTemplateListResponse:
    """DeliverableTemplate 全件取得（REQ-DT-HTTP-002）。

    空リストは 200 で返す。
    """
    templates = await service.find_all()
    items = [DeliverableTemplateResponse.model_validate(t) for t in templates]
    return DeliverableTemplateListResponse(items=items, total=len(items))


@router.get("/{template_id}", status_code=200, response_model=DeliverableTemplateResponse)
async def get_deliverable_template(
    template_id: UUID,
    service: DeliverableTemplateServiceDep,
) -> DeliverableTemplateResponse:
    """DeliverableTemplate 単件取得（REQ-DT-HTTP-003）。

    - 404: 対象 DeliverableTemplate が存在しない場合（MSG-DT-HTTP-001）
    - 422: ``template_id`` が不正な UUID 形式の場合
    """
    template = await service.find_by_id(template_id)
    return DeliverableTemplateResponse.model_validate(template)


@router.put("/{template_id}", status_code=200, response_model=DeliverableTemplateResponse)
async def update_deliverable_template(
    template_id: UUID,
    body: DeliverableTemplateUpdate,
    service: DeliverableTemplateServiceDep,
) -> DeliverableTemplateResponse:
    """DeliverableTemplate 全フィールド更新（REQ-DT-HTTP-004）。

    - 404: 対象 DeliverableTemplate が存在しない場合（MSG-DT-HTTP-001）
    - 422: version 降格（MSG-DT-HTTP-004）/ DAG 循環・上限超過（MSG-DT-HTTP-003a/b/c）
           / ref 不在（MSG-DT-HTTP-002）/ 不変条件違反
    """
    template = await service.update(
        template_id=template_id,
        name=body.name,
        description=body.description,
        type_=body.type,
        schema=body.schema,
        acceptance_criteria=[
            {"id": ac.id, "description": ac.description, "required": ac.required}
            for ac in body.acceptance_criteria
        ],
        version={
            "major": body.version.major,
            "minor": body.version.minor,
            "patch": body.version.patch,
        },
        composition=[
            {
                "template_id": ref.template_id,
                "minimum_version": {
                    "major": ref.minimum_version.major,
                    "minor": ref.minimum_version.minor,
                    "patch": ref.minimum_version.patch,
                },
            }
            for ref in body.composition
        ],
    )
    return DeliverableTemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=204)
async def delete_deliverable_template(
    template_id: UUID,
    service: DeliverableTemplateServiceDep,
) -> Response:
    """DeliverableTemplate を削除する（REQ-DT-HTTP-005）。

    - 204: 成功（No Content）
    - 404: 対象 DeliverableTemplate が存在しない場合（MSG-DT-HTTP-001）
    - 422: ``template_id`` が不正な UUID 形式の場合
    """
    await service.delete(template_id)
    return Response(status_code=204)


__all__ = ["router"]
