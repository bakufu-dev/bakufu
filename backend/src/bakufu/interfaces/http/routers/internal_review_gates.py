"""InternalReviewGate HTTP API エンドポイント（受入テスト用 audit trail 確認）。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from bakufu.interfaces.http.dependencies import SessionDep

task_internal_review_gates_router = APIRouter(
    prefix="/api/tasks",
    tags=["internal-review-gate"],
)


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
) -> list[InternalReviewGateResponse]:
    """Task に紐づく全 InternalReviewGate を返す。

    受入テスト（SC-MVP-002 Step 5）の audit trail 確認および
    REJECTED / ALL_APPROVED 履歴の公開 API 参照先として使用する。
    """
    from bakufu.infrastructure.persistence.sqlite.repositories.internal_review_gate_repository import (  # noqa: E501
        SqliteInternalReviewGateRepository,
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
