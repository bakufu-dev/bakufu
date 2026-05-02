"""Domain Event 基底クラスおよび具体 Event クラス（REQ-WSB-001〜005）。

DDD の Domain Event パターンを実装する。各 Event は Pydantic v2 BaseModel として
定義し、バリデーションは構築時に自動適用される（Fail Fast）。

実装方針は ``docs/features/websocket-broadcast/domain/detailed-design.md``
§確定 A〜F に従う。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DomainEvent(BaseModel):
    """Domain Event 抽象基底クラス（REQ-WSB-001）。

    全 Domain Event に共通するフィールドと ``to_ws_message()`` を保持する。
    具体 Event クラスは本クラスを継承し ``event_type`` / ``aggregate_type`` に
    デフォルト値を設定する。``frozen=True`` により構築後の変更を禁止する（§確定 B）。

    Pydantic v2 ``BaseModel`` として定義する（§確定 A: 既存コードと整合、
    ``model_dump()`` による dict 変換、自動バリデーションの恩恵を受けるため）。
    """

    model_config = ConfigDict(frozen=True)

    #: to_ws_message() でペイロードから除外する基底フィールド名集合（クラスレベル定数）。
    _BASE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"event_id", "event_type", "aggregate_id", "aggregate_type", "occurred_at"}
    )

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    aggregate_id: str
    aggregate_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_ws_message(self) -> dict[str, Any]:
        """WebSocket 送信用 dict を生成する。

        ``event_id / event_type / aggregate_id / aggregate_type / occurred_at``
        を除いた残余フィールドを ``payload`` として格納する（detailed-design §確定 C）。
        ``occurred_at`` は ISO 8601 UTC 形式で出力する。
        """
        payload: dict[str, Any] = {
            k: v for k, v in self.model_dump().items() if k not in self._BASE_FIELDS
        }
        return {
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": payload,
        }


class TaskStateChangedEvent(DomainEvent):
    """Task 状態遷移イベント（REQ-WSB-002）。

    ``TaskService.cancel()`` / ``unblock_retry()`` / ``commit_deliverable()`` が
    業務操作成功後に発行する（M4 スコープ）。
    event_type / aggregate_type は Literal 型で構築時バリデーションを保証し、
    frozen=True により構築後変更不能（§確定 B）。
    """

    event_type: Literal["task.state_changed"] = "task.state_changed"  # pyright: ignore[reportIncompatibleVariableOverride]
    aggregate_type: Literal["Task"] = "Task"  # pyright: ignore[reportIncompatibleVariableOverride]
    directive_id: str
    old_status: str
    new_status: str
    room_id: str


class ExternalReviewGateStateChangedEvent(DomainEvent):
    """ExternalReviewGate 状態遷移イベント（REQ-WSB-003）。

    ``ExternalReviewGateService.approve()`` / ``reject()`` が業務操作成功後に
    発行する（M4 スコープ）。``reviewer_comment`` は Service 層で ``masking.mask()``
    を適用済みの値を渡すこと（§確定 F）。
    event_type / aggregate_type は Literal 型で構築時バリデーションを保証し、
    frozen=True により構築後変更不能（§確定 B）。
    """

    event_type: Literal["external_review_gate.state_changed"] = "external_review_gate.state_changed"  # pyright: ignore[reportIncompatibleVariableOverride]
    aggregate_type: Literal["ExternalReviewGate"] = "ExternalReviewGate"  # pyright: ignore[reportIncompatibleVariableOverride]
    task_id: str
    old_status: str
    new_status: str
    reviewer_comment: str | None = None


class AgentStatusChangedEvent(DomainEvent):
    """Agent ステータス変化イベント（REQ-WSB-004）。

    M4 では型定義のみ凍結する。実 publish（``AgentService.update_status()`` 統合）は
    M5 Phase 2 で実装する（feature-spec.md §6 Out of Scope）。
    event_type / aggregate_type は Literal 型で構築時バリデーションを保証し、
    frozen=True により構築後変更不能（§確定 B）。
    """

    event_type: Literal["agent.status_changed"] = "agent.status_changed"  # pyright: ignore[reportIncompatibleVariableOverride]
    aggregate_type: Literal["Agent"] = "Agent"  # pyright: ignore[reportIncompatibleVariableOverride]
    room_id: str
    old_status: str
    new_status: str


class DirectiveCompletedEvent(DomainEvent):
    """Directive 完了イベント（REQ-WSB-005）。

    M4 では型定義のみ凍結する。実 publish（``DirectiveService.complete()`` / ``fail()`` 統合）は
    M5 Phase 2 で実装する（feature-spec.md §6 Out of Scope）。
    event_type / aggregate_type は Literal 型で構築時バリデーションを保証し、
    frozen=True により構築後変更不能（§確定 B）。
    """

    event_type: Literal["directive.completed"] = "directive.completed"  # pyright: ignore[reportIncompatibleVariableOverride]
    aggregate_type: Literal["Directive"] = "Directive"  # pyright: ignore[reportIncompatibleVariableOverride]
    empire_id: str
    final_status: str


__all__ = [
    "AgentStatusChangedEvent",
    "DirectiveCompletedEvent",
    "DomainEvent",
    "ExternalReviewGateStateChangedEvent",
    "TaskStateChangedEvent",
]
