"""ExternalReviewGate HTTP API エンドポイント。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from bakufu.interfaces.http.dependencies import (
    ExternalReviewGateServiceDep,
    ExternalReviewSubjectDep,
)
from bakufu.interfaces.http.schemas.external_review_gate import (
    ExternalReviewGateApproveRequest,
    ExternalReviewGateCancelRequest,
    ExternalReviewGateListResponse,
    ExternalReviewGateRejectRequest,
    ExternalReviewGateResponse,
)

gates_router = APIRouter(prefix="/api/gates", tags=["external-review-gate"])
task_gates_router = APIRouter(prefix="/api/tasks", tags=["external-review-gate"])


@gates_router.get(
    "",
    response_model=ExternalReviewGateListResponse,
    status_code=200,
    summary="reviewer 向け Gate 一覧（REQ-ERG-HTTP-001）",
)
async def list_pending_gates(
    service: ExternalReviewGateServiceDep,
    subject: ExternalReviewSubjectDep,
    decision: Literal["PENDING"] = "PENDING",
) -> ExternalReviewGateListResponse:
    """認証済み reviewer の PENDING Gate 一覧を返す。"""
    gates = await service.list_pending(subject)
    items = [ExternalReviewGateResponse.model_validate(gate) for gate in gates]
    return ExternalReviewGateListResponse(items=items, total=len(items))


@task_gates_router.get(
    "/{task_id}/gates",
    response_model=ExternalReviewGateListResponse,
    status_code=200,
    summary="Task の Gate 履歴（REQ-ERG-HTTP-002）",
)
async def list_task_gates(
    task_id: UUID,
    service: ExternalReviewGateServiceDep,
    subject: ExternalReviewSubjectDep,
) -> ExternalReviewGateListResponse:
    """Task の Gate 履歴を認証済み reviewer に絞って返す。"""
    gates = await service.list_by_task(task_id, subject)
    items = [ExternalReviewGateResponse.model_validate(gate) for gate in gates]
    return ExternalReviewGateListResponse(items=items, total=len(items))


@gates_router.get(
    "/{gate_id}",
    response_model=ExternalReviewGateResponse,
    status_code=200,
    summary="Gate 単件取得（REQ-ERG-HTTP-003）",
)
async def get_gate(
    gate_id: UUID,
    service: ExternalReviewGateServiceDep,
    subject: ExternalReviewSubjectDep,
) -> ExternalReviewGateResponse:
    """Gate を返し、閲覧監査を追記する。"""
    gate = await service.get_and_record_view(gate_id, subject)
    return ExternalReviewGateResponse.model_validate(gate)


@gates_router.post(
    "/{gate_id}/approve",
    response_model=ExternalReviewGateResponse,
    status_code=200,
    summary="Gate 承認（REQ-ERG-HTTP-004）",
)
async def approve_gate(
    gate_id: UUID,
    body: ExternalReviewGateApproveRequest,
    service: ExternalReviewGateServiceDep,
    subject: ExternalReviewSubjectDep,
) -> ExternalReviewGateResponse:
    """Gate を承認する。"""
    gate = await service.approve(gate_id, subject, body.comment or "")
    return ExternalReviewGateResponse.model_validate(gate)


@gates_router.post(
    "/{gate_id}/reject",
    response_model=ExternalReviewGateResponse,
    status_code=200,
    summary="Gate 差し戻し（REQ-ERG-HTTP-005）",
)
async def reject_gate(
    gate_id: UUID,
    body: ExternalReviewGateRejectRequest,
    service: ExternalReviewGateServiceDep,
    subject: ExternalReviewSubjectDep,
) -> ExternalReviewGateResponse:
    """Gate を差し戻す。"""
    gate = await service.reject(gate_id, subject, body.feedback_text)
    return ExternalReviewGateResponse.model_validate(gate)


@gates_router.post(
    "/{gate_id}/cancel",
    response_model=ExternalReviewGateResponse,
    status_code=200,
    summary="Gate 取消（REQ-ERG-HTTP-006）",
)
async def cancel_gate(
    gate_id: UUID,
    body: ExternalReviewGateCancelRequest,
    service: ExternalReviewGateServiceDep,
    subject: ExternalReviewSubjectDep,
) -> ExternalReviewGateResponse:
    """Gate を取り消す。"""
    gate = await service.cancel(gate_id, subject, body.reason or "")
    return ExternalReviewGateResponse.model_validate(gate)


__all__ = ["gates_router", "task_gates_router"]
