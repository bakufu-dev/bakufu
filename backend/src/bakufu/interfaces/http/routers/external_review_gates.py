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


class ExternalReviewGateHttpRoutes:
    """ExternalReviewGate HTTP 入口をクラスメソッドに閉じる。"""

    @classmethod
    async def list_pending_gates(
        cls,
        service: ExternalReviewGateServiceDep,
        subject: ExternalReviewSubjectDep,
        decision: Literal["PENDING"] = "PENDING",
    ) -> ExternalReviewGateListResponse:
        """認証済み reviewer の PENDING Gate 一覧を返す。"""
        gates = await service.list_pending(subject)
        items = [ExternalReviewGateResponse.model_validate(gate) for gate in gates]
        return ExternalReviewGateListResponse(items=items, total=len(items))

    @classmethod
    async def list_task_gates(
        cls,
        task_id: UUID,
        service: ExternalReviewGateServiceDep,
        subject: ExternalReviewSubjectDep,
    ) -> ExternalReviewGateListResponse:
        """Task の Gate 履歴を認証済み reviewer に絞って返す。"""
        gates = await service.list_by_task(task_id, subject)
        items = [ExternalReviewGateResponse.model_validate(gate) for gate in gates]
        return ExternalReviewGateListResponse(items=items, total=len(items))

    @classmethod
    async def get_gate(
        cls,
        gate_id: UUID,
        service: ExternalReviewGateServiceDep,
        subject: ExternalReviewSubjectDep,
    ) -> ExternalReviewGateResponse:
        """Gate を返し、閲覧監査を追記する。"""
        gate = await service.get_and_record_view(gate_id, subject)
        return ExternalReviewGateResponse.model_validate(gate)

    @classmethod
    async def approve_gate(
        cls,
        gate_id: UUID,
        body: ExternalReviewGateApproveRequest,
        service: ExternalReviewGateServiceDep,
        subject: ExternalReviewSubjectDep,
    ) -> ExternalReviewGateResponse:
        """Gate を承認する。"""
        gate = await service.approve(gate_id, subject, body.comment or "")
        return ExternalReviewGateResponse.model_validate(gate)

    @classmethod
    async def reject_gate(
        cls,
        gate_id: UUID,
        body: ExternalReviewGateRejectRequest,
        service: ExternalReviewGateServiceDep,
        subject: ExternalReviewSubjectDep,
    ) -> ExternalReviewGateResponse:
        """Gate を差し戻す。"""
        gate = await service.reject(gate_id, subject, body.feedback_text)
        return ExternalReviewGateResponse.model_validate(gate)

    @classmethod
    async def cancel_gate(
        cls,
        gate_id: UUID,
        body: ExternalReviewGateCancelRequest,
        service: ExternalReviewGateServiceDep,
        subject: ExternalReviewSubjectDep,
    ) -> ExternalReviewGateResponse:
        """Gate を取り消す。"""
        gate = await service.cancel(gate_id, subject, body.reason or "")
        return ExternalReviewGateResponse.model_validate(gate)


gates_router.add_api_route(
    "",
    ExternalReviewGateHttpRoutes.list_pending_gates,
    methods=["GET"],
    response_model=ExternalReviewGateListResponse,
    status_code=200,
    summary="reviewer 向け Gate 一覧（REQ-ERG-HTTP-001）",
)
task_gates_router.add_api_route(
    "/{task_id}/gates",
    ExternalReviewGateHttpRoutes.list_task_gates,
    methods=["GET"],
    response_model=ExternalReviewGateListResponse,
    status_code=200,
    summary="Task の Gate 履歴（REQ-ERG-HTTP-002）",
)
gates_router.add_api_route(
    "/{gate_id}",
    ExternalReviewGateHttpRoutes.get_gate,
    methods=["GET"],
    response_model=ExternalReviewGateResponse,
    status_code=200,
    summary="Gate 単件取得（REQ-ERG-HTTP-003）",
)
gates_router.add_api_route(
    "/{gate_id}/approve",
    ExternalReviewGateHttpRoutes.approve_gate,
    methods=["POST"],
    response_model=ExternalReviewGateResponse,
    status_code=200,
    summary="Gate 承認（REQ-ERG-HTTP-004）",
)
gates_router.add_api_route(
    "/{gate_id}/reject",
    ExternalReviewGateHttpRoutes.reject_gate,
    methods=["POST"],
    response_model=ExternalReviewGateResponse,
    status_code=200,
    summary="Gate 差し戻し（REQ-ERG-HTTP-005）",
)
gates_router.add_api_route(
    "/{gate_id}/cancel",
    ExternalReviewGateHttpRoutes.cancel_gate,
    methods=["POST"],
    response_model=ExternalReviewGateResponse,
    status_code=200,
    summary="Gate 取消（REQ-ERG-HTTP-006）",
)


__all__ = ["gates_router", "task_gates_router"]
