"""ExternalReviewGate HTTP API Pydantic スキーマ。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bakufu.interfaces.http.schemas.task import AttachmentResponse


class ExternalReviewGateApproveRequest(BaseModel):
    """POST /api/gates/{id}/approve リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    comment: str | None = Field(default=None, max_length=10000)


class ExternalReviewGateRejectRequest(BaseModel):
    """POST /api/gates/{id}/reject リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    feedback_text: str = Field(min_length=1, max_length=10000)


class ExternalReviewGateCancelRequest(BaseModel):
    """POST /api/gates/{id}/cancel リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=10000)


class ExternalReviewGateDeliverableResponse(BaseModel):
    """Gate 内の成果物 snapshot レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    stage_id: str
    body_markdown: str
    submitted_by: str
    submitted_at: str
    attachments: list[AttachmentResponse]

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "stage_id"):
            return data
        return {
            "stage_id": str(data.stage_id),
            "body_markdown": data.body_markdown,
            "submitted_by": str(data.committed_by),
            "submitted_at": _format_dt(data.committed_at),
            "attachments": list(data.attachments),
        }


class ExternalReviewGateAuditEntryResponse(BaseModel):
    """Gate audit_trail レスポンス要素。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    actor_id: str
    action: str
    comment: str
    occurred_at: str

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "actor_id"):
            return data
        return {
            "id": str(data.id),
            "actor_id": str(data.actor_id),
            "action": str(data.action),
            "comment": data.comment,
            "occurred_at": _format_dt(data.occurred_at),
        }


class ExternalReviewGateResponse(BaseModel):
    """Gate 単件レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str
    stage_id: str
    reviewer_id: str
    decision: str
    feedback_text: str
    deliverable_snapshot: ExternalReviewGateDeliverableResponse
    audit_trail: list[ExternalReviewGateAuditEntryResponse]
    created_at: str
    decided_at: str | None

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "reviewer_id"):
            return data
        return {
            "id": str(data.id),
            "task_id": str(data.task_id),
            "stage_id": str(data.stage_id),
            "reviewer_id": str(data.reviewer_id),
            "decision": str(data.decision),
            "feedback_text": data.feedback_text,
            "deliverable_snapshot": data.deliverable_snapshot,
            "audit_trail": list(data.audit_trail),
            "created_at": _format_dt(data.created_at),
            "decided_at": None if data.decided_at is None else _format_dt(data.decided_at),
        }


class ExternalReviewGateListResponse(BaseModel):
    """Gate 一覧レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[ExternalReviewGateResponse]
    total: int


def _format_dt(value: Any) -> str:
    raw = value.isoformat()
    return raw.replace("+00:00", "Z")


__all__ = [
    "ExternalReviewGateApproveRequest",
    "ExternalReviewGateAuditEntryResponse",
    "ExternalReviewGateCancelRequest",
    "ExternalReviewGateDeliverableResponse",
    "ExternalReviewGateListResponse",
    "ExternalReviewGateRejectRequest",
    "ExternalReviewGateResponse",
]
