"""共通レスポンス Pydantic モデル。"""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, model_serializer

T = TypeVar("T")


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    detail: dict[str, object] | None = None

    @model_serializer(mode="wrap")
    def _exclude_none_detail(self, handler: Any) -> dict[str, Any]:
        """``detail`` フィールドが ``None`` のときはシリアライズ結果から除外する。

        既存の ``{"code": ..., "message": ...}`` 形式を維持しつつ、
        新規追加した ``detail`` フィールドが ``None`` のときは後方互換性を保つ。
        """
        data = handler(self)
        if data.get("detail") is None:
            data.pop("detail", None)
        return data


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
