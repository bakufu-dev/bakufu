"""Empire HTTP API Pydantic スキーマ (確定 A).

リクエスト / レスポンスモデルを定義する。全スキーマに
``ConfigDict(extra="forbid")`` を適用し余分なフィールドを拒否する (Q-3 物理保証)。

レスポンス系スキーマは ``from_attributes=True`` + ``field_validator(mode='before')``
で domain オブジェクトから直接変換する。UUID → str / StrEnum → str の変換は
schema 側 validator が責任を持つため、router が domain 層の型を知る必要はない。
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmpireCreate(BaseModel):
    """POST /api/empires リクエスト Body (REQ-EM-HTTP-001)。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)


class EmpireUpdate(BaseModel):
    """PATCH /api/empires/{id} リクエスト Body (REQ-EM-HTTP-004)。

    ``name=None`` の場合は変更なし (部分更新 PATCH パターン)。
    ``None`` でない場合は 1-80 文字の制約を適用する。
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)


class RoomRefResponse(BaseModel):
    """EmpireResponse 内の rooms 要素。

    ``from_attributes=True`` で domain ``RoomRef`` から直接変換する。
    ``room_id`` は UUID のため ``_coerce_room_id`` で str に変換する。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    room_id: str
    name: str
    archived: bool

    @field_validator("room_id", mode="before")
    @classmethod
    def _coerce_room_id(cls, value: object) -> object:
        """UUID → str 変換。domain の ``RoomRef.room_id`` は UUID 型。"""
        if isinstance(value, UUID):
            return str(value)
        return value


class AgentRefResponse(BaseModel):
    """EmpireResponse 内の agents 要素。

    ``from_attributes=True`` で domain ``AgentRef`` から直接変換する。
    ``agent_id`` は UUID、``role`` は StrEnum のため各 validator で str 変換する。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    agent_id: str
    name: str
    role: str

    @field_validator("agent_id", mode="before")
    @classmethod
    def _coerce_agent_id(cls, value: object) -> object:
        """UUID → str 変換。domain の ``AgentRef.agent_id`` は UUID 型。"""
        if isinstance(value, UUID):
            return str(value)
        return value

    @field_validator("role", mode="before")
    @classmethod
    def _coerce_role(cls, value: object) -> object:
        """StrEnum → str 変換。domain の ``AgentRef.role`` は ``Role`` StrEnum。

        ``Role`` は Python 3.12 の ``StrEnum`` のため ``str(value)`` で
        enum 値の文字列 (例: "LEADER") を返す。str 渡し時はそのまま返す。
        """
        if isinstance(value, str):
            return value
        return str(value)


class EmpireResponse(BaseModel):
    """Empire 単件レスポンス (GET-one / POST / PATCH)。

    ``from_attributes=True`` で domain ``Empire`` から ``model_validate(empire)``
    で直接変換する。``id`` は UUID のため ``_coerce_id`` で str 変換する。
    ネスト要素 (``rooms`` / ``agents``) も ``from_attributes=True`` を持つ
    ``RoomRefResponse`` / ``AgentRefResponse`` が再帰的に変換する。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    archived: bool
    rooms: list[RoomRefResponse]
    agents: list[AgentRefResponse]

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, value: object) -> object:
        """UUID → str 変換。domain の ``Empire.id`` は ``EmpireId`` (UUID 型)。"""
        if isinstance(value, UUID):
            return str(value)
        return value


class EmpireListResponse(BaseModel):
    """GET /api/empires レスポンス (REQ-EM-HTTP-002)。"""

    model_config = ConfigDict(extra="forbid")

    items: list[EmpireResponse]
    total: int


__all__ = [
    "AgentRefResponse",
    "EmpireCreate",
    "EmpireListResponse",
    "EmpireResponse",
    "EmpireUpdate",
    "RoomRefResponse",
]
