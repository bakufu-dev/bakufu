"""ExternalReviewGate HTTP API Pydantic スキーマ。

domain / infrastructure への import は置かない。domain オブジェクトは duck typing で
レスポンス dict に変換する。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _format_dt(value: Any) -> str:
    raw = value.isoformat()
    return raw.replace("+00:00", "Z")


# ── リクエストモデル ────────────────────────────────────────────────────


class GateApprove(BaseModel):
    """POST /api/gates/{id}/approve リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(default="", max_length=10000)


class GateReject(BaseModel):
    """POST /api/gates/{id}/reject リクエスト Body。

    feedback_text は差し戻し理由として業務的に必須（1 文字以上）。
    """

    model_config = ConfigDict(extra="forbid")

    feedback_text: str = Field(min_length=1, max_length=10000)


class GateCancel(BaseModel):
    """POST /api/gates/{id}/cancel リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="", max_length=10000)


# ── レスポンスモデル ────────────────────────────────────────────────────


class AuditEntryResponse(BaseModel):
    """audit_trail の 1 エントリ。"""

    model_config = ConfigDict(extra="forbid")

    actor_id: str
    action: str
    # NOTE: DB は MaskedText で保存（書き込み時 mask() 適用済み）。
    # 読み出し値をそのまま返す（アンマスクなし）— basic-design.md §確定B 参照
    comment: str
    occurred_at: str

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "actor_id"):
            return data
        return {
            "actor_id": str(data.actor_id),
            "action": str(data.action),
            "comment": data.comment,
            "occurred_at": _format_dt(data.occurred_at),
        }


class AttachmentResponse(BaseModel):
    """deliverable_snapshot の添付ファイルメタデータ。"""

    model_config = ConfigDict(extra="forbid")

    sha256: str
    filename: str
    mime_type: str
    size_bytes: int

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "sha256"):
            return data
        return {
            "sha256": data.sha256,
            "filename": data.filename,
            "mime_type": data.mime_type,
            "size_bytes": data.size_bytes,
        }


class DeliverableSnapshotResponse(BaseModel):
    """Gate 生成時に凍結された成果物スナップショット。"""

    model_config = ConfigDict(extra="forbid")

    stage_id: str
    # NOTE: DB は MaskedText で保存（書き込み時 mask() 適用済み）。
    # 読み出し値をそのまま返す（アンマスクなし）— basic-design.md §確定B 参照
    body_markdown: str
    committed_by: str
    committed_at: str
    attachments: list[AttachmentResponse]

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "stage_id"):
            return data
        return {
            "stage_id": str(data.stage_id),
            "body_markdown": data.body_markdown,
            "committed_by": str(data.committed_by),
            "committed_at": _format_dt(data.committed_at),
            "attachments": list(data.attachments),
        }


class GateResponse(BaseModel):
    """Gate 一覧要素（概要情報）。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str
    stage_id: str
    reviewer_id: str
    decision: str
    created_at: str
    decided_at: str | None

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "task_id"):
            return data
        decided_at = data.decided_at
        return {
            "id": str(data.id),
            "task_id": str(data.task_id),
            "stage_id": str(data.stage_id),
            "reviewer_id": str(data.reviewer_id),
            "decision": str(data.decision),
            "created_at": _format_dt(data.created_at),
            "decided_at": _format_dt(decided_at) if decided_at is not None else None,
        }


class GateDetailResponse(BaseModel):
    """Gate 単件詳細 / approve / reject / cancel 操作後レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str
    stage_id: str
    reviewer_id: str
    decision: str
    # NOTE: DB は MaskedText で保存（書き込み時 mask() 適用済み）。
    # 読み出し値をそのまま返す（アンマスクなし）— basic-design.md §確定B 参照
    feedback_text: str
    deliverable_snapshot: DeliverableSnapshotResponse
    audit_trail: list[AuditEntryResponse]
    created_at: str
    decided_at: str | None

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "task_id"):
            return data
        decided_at = data.decided_at
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
            "decided_at": _format_dt(decided_at) if decided_at is not None else None,
        }


class GateListResponse(BaseModel):
    """Gate 一覧レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[GateResponse]
    total: int


__all__ = [
    "AttachmentResponse",
    "AuditEntryResponse",
    "DeliverableSnapshotResponse",
    "GateApprove",
    "GateCancel",
    "GateDetailResponse",
    "GateListResponse",
    "GateReject",
    "GateResponse",
]
