"""Room HTTP API Pydantic スキーマ (確定 A).

リクエスト / レスポンスモデルを定義する。全スキーマに
``ConfigDict(extra="forbid")`` を適用し余分なフィールドを拒否する (Q-3 物理保証)。

レスポンス系スキーマは ``from_attributes=True`` + ``field_validator(mode='before')``
で domain オブジェクトから直接変換する。UUID → str / StrEnum → str / datetime → str
の変換は schema 側 validator が責任を持つため、router が domain 層の型を知る必要はない。

``RoomResponse`` は domain ``Room`` の ``prompt_kit: PromptKit`` フィールドを
``prompt_kit_prefix_markdown: str`` にフラット化する。``model_validator(mode='before')``
が ``room.prompt_kit.prefix_markdown`` を取り出してから field validation に渡す。
domain import はゼロ (Q-3 interfaces->domain 直接依存禁止)。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from bakufu.interfaces.http.schemas.deliverable_template import (
    DeliverableTemplateRefCreate,
    DeliverableTemplateRefResponse,
)

# ---------------------------------------------------------------------------
# 有効な Role 値（domain import なし — Q-3 interfaces→domain 直接依存禁止）
# 値は bakufu.domain.value_objects.enums.Role StrEnum の確定文言。
# ---------------------------------------------------------------------------
_VALID_ROLES: frozenset[str] = frozenset(
    {
        "LEADER",
        "DEVELOPER",
        "TESTER",
        "REVIEWER",
        "UX",
        "SECURITY",
        "ASSISTANT",
        "DISCUSSANT",
        "WRITER",
        "SITE_ADMIN",
    }
)


class MemberResponse(BaseModel):
    """Room メンバー (AgentMembership) レスポンス要素 (確定 A §レスポンスサブスキーマ)。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    agent_id: str
    role: str
    joined_at: str

    @field_validator("agent_id", mode="before")
    @classmethod
    def _coerce_agent_id(cls, value: object) -> object:
        """UUID → str 変換。domain の ``AgentMembership.agent_id`` は UUID 型。"""
        if isinstance(value, UUID):
            return str(value)
        return value

    @field_validator("role", mode="before")
    @classmethod
    def _coerce_role(cls, value: object) -> object:
        """StrEnum → str 変換。domain の ``AgentMembership.role`` は ``Role`` StrEnum。"""
        return str(value)

    @field_validator("joined_at", mode="before")
    @classmethod
    def _coerce_joined_at(cls, value: object) -> object:
        """datetime → ISO 8601 str 変換。"""
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)


class RoomCreate(BaseModel):
    """POST /api/empires/{empire_id}/rooms リクエスト Body (REQ-RM-HTTP-001)。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    workflow_id: UUID
    prompt_kit_prefix_markdown: str = Field(default="", max_length=10000)


class RoomUpdate(BaseModel):
    """PATCH /api/rooms/{room_id} リクエスト Body (REQ-RM-HTTP-004)。

    ``None`` フィールドは変更なし (部分更新 PATCH パターン)。
    全フィールドが ``None`` の場合は変更なし (save せず既存 Room を返す)。
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    prompt_kit_prefix_markdown: str | None = Field(default=None, max_length=10000)


class AgentAssignRequest(BaseModel):
    """POST /api/rooms/{room_id}/agents リクエスト Body (REQ-RM-HTTP-006)。"""

    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    role: str = Field(min_length=1, max_length=50)
    custom_refs: list[DeliverableTemplateRefCreate] | None = Field(default=None, max_length=50)

    @field_validator("role", mode="before")
    @classmethod
    def _validate_role(cls, value: object) -> object:
        """有効な Role 値か検証する (domain import なし / Q-3 遵守)。

        有効値は ``bakufu.domain.value_objects.Role`` StrEnum の確定文言に対応する。
        """
        if isinstance(value, str) and value not in _VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(_VALID_ROLES)!r}, got {value!r}")
        return value


class RoomResponse(BaseModel):
    """Room 単件レスポンス (GET-one / POST / PATCH / DELETE-archive)。

    ``from_attributes=True`` で domain ``Room`` から ``model_validate(room)``
    で直接変換する。``prompt_kit: PromptKit`` を ``prompt_kit_prefix_markdown``
    にフラット化するため ``model_validator(mode='before')`` が前処理する。
    domain import はゼロ (Q-3)。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    description: str
    workflow_id: str
    members: list[MemberResponse]
    prompt_kit_prefix_markdown: str
    archived: bool

    @model_validator(mode="before")
    @classmethod
    def _flatten_room(cls, data: Any) -> Any:
        """domain Room → flat dict 変換 (Q-3: domain import なし)。

        ``Room.prompt_kit.prefix_markdown`` を ``prompt_kit_prefix_markdown``
        にフラット化する。``Any`` 型 + ``hasattr`` による duck-typing で
        型 import を回避する (pyright strict 対応)。dict 渡しの場合はそのまま通す。
        """
        if hasattr(data, "prompt_kit"):
            return {
                "id": str(data.id),
                "name": data.name,
                "description": data.description,
                "workflow_id": str(data.workflow_id),
                "members": list(data.members),
                "prompt_kit_prefix_markdown": data.prompt_kit.prefix_markdown,
                "archived": data.archived,
            }
        return data


class RoomListResponse(BaseModel):
    """GET /api/empires/{empire_id}/rooms レスポンス (REQ-RM-HTTP-002)。

    空リストも 200 で返す (items=[], total=0)。
    """

    model_config = ConfigDict(extra="forbid")

    items: list[RoomResponse]
    total: int


class RoomRoleOverrideRequest(BaseModel):
    """PUT /api/rooms/{room_id}/role-overrides/{role} リクエスト Body。"""

    model_config = ConfigDict(extra="forbid")

    deliverable_template_refs: list[DeliverableTemplateRefCreate]


class RoomRoleOverrideResponse(BaseModel):
    """RoomRoleOverride 単件レスポンス。

    ``from_attributes=True`` で domain ``RoomRoleOverride`` VO から
    ``model_validate(override)`` で直接変換する。
    ``room_id: RoomId (UUID)`` / ``role: Role (StrEnum)`` を str にフラット化するため
    ``model_validator(mode='before')`` が前処理する。domain import はゼロ (Q-3)。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    room_id: str
    role: str
    deliverable_template_refs: list[DeliverableTemplateRefResponse]

    @model_validator(mode="before")
    @classmethod
    def _flatten_override(cls, data: Any) -> Any:
        """domain RoomRoleOverride → flat dict 変換 (Q-3: domain import なし)。"""
        if hasattr(data, "room_id"):
            return {
                "room_id": str(data.room_id),
                "role": str(data.role),
                "deliverable_template_refs": list(data.deliverable_template_refs),
            }
        return data


class RoomRoleOverrideListResponse(BaseModel):
    """GET /api/rooms/{room_id}/role-overrides レスポンス。"""

    model_config = ConfigDict(extra="forbid")

    items: list[RoomRoleOverrideResponse]
    total: int


__all__ = [
    "AgentAssignRequest",
    "MemberResponse",
    "RoomCreate",
    "RoomListResponse",
    "RoomResponse",
    "RoomRoleOverrideListResponse",
    "RoomRoleOverrideRequest",
    "RoomRoleOverrideResponse",
    "RoomUpdate",
]
