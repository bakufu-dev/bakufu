"""Empire HTTP API Pydantic スキーマ (確定 A).

リクエスト / レスポンスモデルを定義する。全スキーマに
``ConfigDict(extra="forbid")`` を適用し余分なフィールドを拒否する (Q-3 物理保証)。

``EmpireResponse`` は ``ConfigDict(from_attributes=True)`` も適用するが、
domain ``Empire.id`` は ``EmpireId`` (UUID ラッパー) のため
``str(empire.id)`` での文字列変換が必要な点に注意。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EmpireCreate(BaseModel):
    """POST /api/empires リクエスト Body (REQ-EM-HTTP-001)。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)


class EmpireUpdate(BaseModel):
    """PATCH /api/empires/{id} リクエスト Body (REQ-EM-HTTP-004)。

    ``name=None`` の場合は変更なし (部分更新 PATCH パターン)。
    ``None`` でない場合は 1〜80 文字の制約を適用する。
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)


class RoomRefResponse(BaseModel):
    """EmpireResponse 内の rooms 要素。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    room_id: str
    name: str
    archived: bool


class AgentRefResponse(BaseModel):
    """EmpireResponse 内の agents 要素。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    agent_id: str
    name: str
    role: str


class EmpireResponse(BaseModel):
    """Empire 単件レスポンス (GET-one / POST / PATCH)。

    ``from_attributes=True`` で domain ``Empire`` から直接変換可能。
    ``id`` は ``str(empire.id)`` で文字列化してから渡す必要がある。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    name: str
    archived: bool
    rooms: list[RoomRefResponse]
    agents: list[AgentRefResponse]


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
