"""Directive HTTP API エンドポイント。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from bakufu.interfaces.http.dependencies import DirectiveServiceDep
from bakufu.interfaces.http.schemas.directive import (
    DirectiveCreate,
    DirectiveResponse,
    DirectiveWithTaskResponse,
)
from bakufu.interfaces.http.schemas.task import TaskResponse

room_directives_router = APIRouter(prefix="/api/rooms", tags=["directive"])


@room_directives_router.post(
    "/{room_id}/directives",
    response_model=DirectiveWithTaskResponse,
    status_code=201,
    summary="Directive 発行 + Task 起票（REQ-DR-HTTP-001）",
)
async def issue_directive(
    room_id: UUID,
    body: DirectiveCreate,
    service: DirectiveServiceDep,
) -> DirectiveWithTaskResponse:
    """Directive を発行し、Task を同時に起票する。"""
    directive, task = await service.issue(room_id, body.text)
    return DirectiveWithTaskResponse(
        directive=DirectiveResponse.model_validate(directive),
        task=TaskResponse.model_validate(task),
    )


__all__ = ["room_directives_router"]
