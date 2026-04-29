"""``task_assigned_agents`` テーブル — Task Aggregate 用 AgentId リスト。

各行は与えられた Task に対するアサイン エージェント 1 件を表す。リスト順は
``order_index``（0 始まり、Aggregate の ``assigned_agent_ids: list[AgentId]`` 位置
と一致）で保存される。

``agent_id`` は ``agents.id`` への FK を意図的に **持たない** — 恒久的な Aggregate
境界の設計決定（§設計決定 TR-001）。FK を加えると Agent アーカイブ時にアサイン
エージェント行が CASCADE 削除され、IN_PROGRESS Task を破壊するリスクがある。
room-repository の ``room_members.agent_id`` が同じ先例を確立している。

UNIQUE(task_id, agent_id) は同じ Agent を 1 つの Task に重複アサインすることを
防ぎ、Aggregate レベルの ``_validate_assigned_agents_unique`` 不変条件をデータ
ベース レベルでもミラーする多層防御。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class TaskAssignedAgentRow(Base):
    """``task_assigned_agents`` テーブルの ORM マッピング。"""

    __tablename__ = "task_assigned_agents"

    task_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    # agent_id: agents.id への FK は意図的に持たない。
    # Aggregate 境界: Agent 削除をアサイン エージェント行に CASCADE 伝播させては
    # ならない（§設計決定 TR-001、room_members.agent_id 先例と同方針）。
    agent_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        # 多層防御: 明示的な UNIQUE が Aggregate 不変条件
        # _validate_assigned_agents_unique を DB レベルでミラーする。
        UniqueConstraint("task_id", "agent_id", name="uq_task_assigned_agents"),
    )


__all__ = ["TaskAssignedAgentRow"]
