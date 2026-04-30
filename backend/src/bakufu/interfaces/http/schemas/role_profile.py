"""RoleProfile HTTP API Pydantic スキーマ。

リクエスト / レスポンスモデルを定義する。全スキーマに
``ConfigDict(extra="forbid")`` を適用し余分なフィールドを拒否する。

``DeliverableTemplateRefCreate`` / ``DeliverableTemplateRefResponse`` は
:mod:`bakufu.interfaces.http.schemas.deliverable_template` から再利用する。
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from bakufu.interfaces.http.schemas.deliverable_template import (
    DeliverableTemplateRefCreate,
    DeliverableTemplateRefResponse,
)


class RoleProfileUpsertRequest(BaseModel):
    """PUT /api/empires/{empire_id}/role-profiles/{role} リクエスト Body。

    ``deliverable_template_refs`` は完全置換のため空リストも許容する。
    """

    model_config = ConfigDict(extra="forbid")

    deliverable_template_refs: list[DeliverableTemplateRefCreate]


class RoleProfileResponse(BaseModel):
    """RoleProfile 単件レスポンス（200）。

    ``from_attributes=True`` で domain ``RoleProfile`` から
    ``model_validate(profile, from_attributes=True)`` で直接変換する。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    empire_id: str
    role: str
    deliverable_template_refs: list[DeliverableTemplateRefResponse]

    @field_validator("id", "empire_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, value: object) -> object:
        """UUID → str 変換。domain の ``id`` / ``empire_id`` は UUID 型。"""
        if isinstance(value, UUID):
            return str(value)
        return value

    @field_validator("role", mode="before")
    @classmethod
    def _coerce_role(cls, value: object) -> object:
        """StrEnum → str 変換。domain の ``role`` は ``Role`` StrEnum。"""
        if isinstance(value, str):
            return value
        return str(value)


class RoleProfileListResponse(BaseModel):
    """GET /api/empires/{empire_id}/role-profiles レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[RoleProfileResponse]
    total: int


__all__ = [
    "RoleProfileListResponse",
    "RoleProfileResponse",
    "RoleProfileUpsertRequest",
]
