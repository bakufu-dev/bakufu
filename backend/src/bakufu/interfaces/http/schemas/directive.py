"""Directive HTTP API Pydantic スキーマ。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from bakufu.application.security.masking import mask
from bakufu.interfaces.http.schemas.task import TaskResponse


class DirectiveCreate(BaseModel):
    """POST /api/rooms/{room_id}/directives リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10000)


class DirectiveResponse(BaseModel):
    """Directive 単件レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    target_room_id: str
    created_at: str
    task_id: str | None

    @field_serializer("text")
    def _mask_text(self, value: str) -> str:
        return mask(value)

    @model_validator(mode="before")
    @classmethod
    def _from_domain(cls, data: Any) -> Any:
        if not hasattr(data, "target_room_id"):
            return data
        return {
            "id": str(data.id),
            "text": data.text,
            "target_room_id": str(data.target_room_id),
            "created_at": _format_dt(data.created_at),
            "task_id": str(data.task_id) if data.task_id is not None else None,
        }


class DirectiveWithTaskResponse(BaseModel):
    """Directive 発行レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    directive: DirectiveResponse
    task: TaskResponse


def _format_dt(value: Any) -> str:
    raw = value.isoformat()
    return raw.replace("+00:00", "Z")


__all__ = [
    "DirectiveCreate",
    "DirectiveResponse",
    "DirectiveWithTaskResponse",
]
