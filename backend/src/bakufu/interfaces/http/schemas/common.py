"""共通レスポンス Pydantic モデル。"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


# 互換しない (BaseModel + Generic[T] の組み合わせが必要)。
# UP046 を抑制して TypeVar ベースの Generic を維持する。
class PaginatedResponse(BaseModel, Generic[T]):  # noqa: UP046
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: int  # >= 0
    offset: int  # >= 0
    limit: int  # >= 1


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
