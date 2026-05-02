"""DomainEvent 各クラス用ファクトリ群.

``docs/features/websocket-broadcast/domain/test-design.md`` §Factory 定義 準拠。
WeakValueDictionary パターン（task.py / external_review_gate.py と同パターン）。
各ファクトリは本番コンストラクタ経由で妥当なデフォルトインスタンスを返し、
``_SYNTHETIC_REGISTRY`` に登録する。これにより ``is_synthetic`` が後から
「ファクトリ由来か」を確認できる。

本モジュールを本番コードから import してはならない ── 合成データ境界を
監査可能に保つため ``tests/`` 配下に配置されている。
"""

from __future__ import annotations

from uuid import uuid4
from weakref import WeakValueDictionary

from bakufu.domain.events import (
    AgentStatusChangedEvent,
    DirectiveCompletedEvent,
    ExternalReviewGateStateChangedEvent,
    TaskStateChangedEvent,
)
from pydantic import BaseModel

# モジュールスコープのレジストリ。値は弱参照で保持するので GC 圧は中立 ──
# 「このオブジェクトはファクトリ由来か」をオブジェクト生存中だけ知ればよい。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。

    検査は構造的ではなく ID ベース (``id``)。これにより独立に生成された
    等値の 2 インスタンスは区別される ── ファクトリが返した実オブジェクトのみ
    合成印が付く。
    """
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """``instance`` を合成レジストリに記録する。"""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# TaskStateChangedEvent ファクトリ
# ---------------------------------------------------------------------------
def make_task_state_changed_event(
    *,
    aggregate_id: str | None = None,
    directive_id: str | None = None,
    old_status: str = "PENDING",
    new_status: str = "IN_PROGRESS",
    room_id: str | None = None,
) -> TaskStateChangedEvent:
    """妥当な :class:`TaskStateChangedEvent` を構築し合成印を付ける。

    デフォルトは PENDING → IN_PROGRESS 遷移の canonical な入口状態。
    ``aggregate_id`` は task_id に相当する（DomainEvent 設計による）。
    """
    event = TaskStateChangedEvent(
        aggregate_id=aggregate_id if aggregate_id is not None else str(uuid4()),
        directive_id=directive_id if directive_id is not None else str(uuid4()),
        old_status=old_status,
        new_status=new_status,
        room_id=room_id if room_id is not None else str(uuid4()),
    )
    _register(event)
    return event


# ---------------------------------------------------------------------------
# ExternalReviewGateStateChangedEvent ファクトリ
# ---------------------------------------------------------------------------
def make_external_review_gate_state_changed_event(
    *,
    aggregate_id: str | None = None,
    task_id: str | None = None,
    old_status: str = "OPEN",
    new_status: str = "PENDING",
    reviewer_comment: str | None = None,
) -> ExternalReviewGateStateChangedEvent:
    """妥当な :class:`ExternalReviewGateStateChangedEvent` を構築し合成印を付ける。

    デフォルトは reviewer_comment=None（省略可能フィールド）の入口状態。
    ``aggregate_id`` は gate_id に相当する（DomainEvent 設計による）。
    """
    event = ExternalReviewGateStateChangedEvent(
        aggregate_id=aggregate_id if aggregate_id is not None else str(uuid4()),
        task_id=task_id if task_id is not None else str(uuid4()),
        old_status=old_status,
        new_status=new_status,
        reviewer_comment=reviewer_comment,
    )
    _register(event)
    return event


# ---------------------------------------------------------------------------
# AgentStatusChangedEvent ファクトリ
# ---------------------------------------------------------------------------
def make_agent_status_changed_event(
    *,
    aggregate_id: str | None = None,
    room_id: str | None = None,
    old_status: str = "idle",
    new_status: str = "running",
) -> AgentStatusChangedEvent:
    """妥当な :class:`AgentStatusChangedEvent` を構築し合成印を付ける。

    デフォルトは idle → running 遷移の canonical な入口状態。
    ``aggregate_id`` は agent_id に相当する（DomainEvent 設計による）。
    """
    event = AgentStatusChangedEvent(
        aggregate_id=aggregate_id if aggregate_id is not None else str(uuid4()),
        room_id=room_id if room_id is not None else str(uuid4()),
        old_status=old_status,
        new_status=new_status,
    )
    _register(event)
    return event


# ---------------------------------------------------------------------------
# DirectiveCompletedEvent ファクトリ
# ---------------------------------------------------------------------------
def make_directive_completed_event(
    *,
    aggregate_id: str | None = None,
    empire_id: str | None = None,
    final_status: str = "DONE",
) -> DirectiveCompletedEvent:
    """妥当な :class:`DirectiveCompletedEvent` を構築し合成印を付ける。

    デフォルトは final_status="DONE" の canonical な完了状態。
    ``aggregate_id`` は directive_id に相当する（DomainEvent 設計による）。
    """
    event = DirectiveCompletedEvent(
        aggregate_id=aggregate_id if aggregate_id is not None else str(uuid4()),
        empire_id=empire_id if empire_id is not None else str(uuid4()),
        final_status=final_status,
    )
    _register(event)
    return event


__all__ = [
    "is_synthetic",
    "make_agent_status_changed_event",
    "make_directive_completed_event",
    "make_external_review_gate_state_changed_event",
    "make_task_state_changed_event",
]
