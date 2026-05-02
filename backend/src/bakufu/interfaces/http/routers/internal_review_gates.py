"""InternalReviewGate HTTP API エンドポイント（受入テスト用 audit trail 確認）。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from bakufu.interfaces.http.dependencies import SessionDep

_MSG_INVALID_AUTH_HEADER = (
    "[FAIL] Invalid or missing Authorization header.\n"
    "Next: Set the header as: Authorization: Bearer <owner-id> (UUID format)."
)

task_internal_review_gates_router = APIRouter(
    prefix="/api/tasks",
    tags=["internal-review-gate"],
)


def _get_owner_id(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> UUID:
    """Authorization: Bearer <owner-id> ヘッダーから OwnerId を抽出する。"""
    if authorization is None:
        raise HTTPException(status_code=422, detail=_MSG_INVALID_AUTH_HEADER)
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=422, detail=_MSG_INVALID_AUTH_HEADER)
    token = authorization[len("Bearer ") :]
    try:
        return UUID(token)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=_MSG_INVALID_AUTH_HEADER) from exc


_OwnerIdDep = Annotated[UUID, Depends(_get_owner_id)]


class VerdictResponse(BaseModel):
    """InternalReviewGate の個別 Verdict レスポンス DTO。"""

    role: str
    agent_id: str
    decision: str
    comment: str
    decided_at: datetime


class InternalReviewGateResponse(BaseModel):
    """InternalReviewGate レスポンス DTO。"""

    id: str
    task_id: str
    stage_id: str
    required_gate_roles: list[str]
    gate_decision: str
    verdicts: list[VerdictResponse]
    created_at: datetime


@task_internal_review_gates_router.get(
    "/{task_id}/internal-review-gates",
    response_model=list[InternalReviewGateResponse],
    status_code=200,
    summary="Task の InternalReviewGate 一覧取得（audit trail 確認用）",
)
async def list_internal_review_gates_by_task(
    task_id: UUID,
    session: SessionDep,
    owner_id: _OwnerIdDep,
) -> list[InternalReviewGateResponse]:
    """Task に紐づく全 InternalReviewGate を返す。

    受入テスト（SC-MVP-002 Step 5）の audit trail 確認および
    REJECTED / ALL_APPROVED 履歴の公開 API 参照先として使用する。

    Authorization: Bearer <owner-id> ヘッダー必須（Finding 2 対応）。
    owner_id が Task の assigned_agent_ids に含まれない場合は 403 を返す（IDOR 防御）。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (  # noqa: E501
        SqliteInternalReviewGateRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    # IDOR 防御: owner_id が task の assigned_agent_ids に含まれるか確認（Finding 2 残存修正）
    task_repo = SqliteTaskRepository(session)
    task = await task_repo.find_by_id(task_id)
    if task is None or owner_id not in task.assigned_agent_ids:
        raise HTTPException(
            status_code=403,
            detail=(
                "[FAIL] Access denied: owner_id is not an assigned agent of this task.\n"
                "Next: Verify the task_id and your Authorization token."
            ),
        )

    repo = SqliteInternalReviewGateRepository(session)
    gates = await repo.find_all_by_task_id(task_id)

    return [
        InternalReviewGateResponse(
            id=str(gate.id),
            task_id=str(gate.task_id),
            stage_id=str(gate.stage_id),
            required_gate_roles=sorted(str(r) for r in gate.required_gate_roles),
            gate_decision=gate.gate_decision.value,
            verdicts=[
                VerdictResponse(
                    role=str(v.role),
                    agent_id=str(v.agent_id),
                    decision=v.decision.value,
                    comment=v.comment,
                    decided_at=v.decided_at,
                )
                for v in gate.verdicts
            ],
            created_at=gate.created_at,
        )
        for gate in gates
    ]


__all__ = ["task_internal_review_gates_router"]
