"""Task HTTP API Pydantic スキーマ。

domain / infrastructure への import は置かない。domain オブジェクトは duck typing で
レスポンス dict に変換する。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from bakufu.application.security.masking import mask


class TaskAssign(BaseModel):
    """POST /api/tasks/{task_id}/assign リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    agent_ids: list[UUID] = Field(min_length=1)


class AttachmentCreate(BaseModel):
    """成果物添付ファイルの作成リクエスト要素。"""

    model_config = ConfigDict(extra="forbid")

    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    filename: str = Field(min_length=1)
    mime_type: str = Field(min_length=1)
    size_bytes: int = Field(gt=0)


class DeliverableCreate(BaseModel):
    """POST /api/tasks/{task_id}/deliverables/{stage_id} リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    body_markdown: str = Field(min_length=1, max_length=100000)
    submitted_by: UUID
    attachments: list[AttachmentCreate] | None = None


class AttachmentResponse(BaseModel):
    """成果物添付ファイルのレスポンス要素。"""

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


class DeliverableResponse(BaseModel):
    """Stage 成果物のレスポンス要素。"""

    model_config = ConfigDict(extra="forbid")

    stage_id: str
    body_markdown: str
    submitted_by: str
    submitted_at: str
    attachments: list[AttachmentResponse]

    @field_serializer("body_markdown")
    def _mask_body_markdown(self, value: str) -> str:
        return mask(value)

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


class TaskResponse(BaseModel):
    """Task 単件レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    room_id: str
    directive_id: str
    current_stage_id: str
    status: str
    assigned_agent_ids: list[str]
    last_error: str | None
    deliverables: dict[str, DeliverableResponse]
    created_at: str
    updated_at: str

    @field_serializer("last_error")
    def _mask_last_error(self, value: str | None) -> str | None:
        if value is None:
            return None
        return mask(value)

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "directive_id"):
            return data
        return {
            "id": str(data.id),
            "room_id": str(data.room_id),
            "directive_id": str(data.directive_id),
            "current_stage_id": str(data.current_stage_id),
            "status": str(data.status),
            "assigned_agent_ids": [str(agent_id) for agent_id in data.assigned_agent_ids],
            "last_error": data.last_error,
            "deliverables": {
                str(stage_id): deliverable for stage_id, deliverable in data.deliverables.items()
            },
            "created_at": _format_dt(data.created_at),
            "updated_at": _format_dt(data.updated_at),
        }


class TaskListResponse(BaseModel):
    """Task 一覧レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[TaskResponse]
    total: int


def _format_dt(value: Any) -> str:
    raw = value.isoformat()
    return raw.replace("+00:00", "Z")


__all__ = [
    "AttachmentCreate",
    "AttachmentResponse",
    "DeliverableCreate",
    "DeliverableResponse",
    "TaskAssign",
    "TaskListResponse",
    "TaskResponse",
]
