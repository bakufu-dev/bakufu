"""``empire_agent_refs`` テーブル — Empire ↔ Agent 関係行。

:class:`bakufu.domain.value_objects.AgentRef` の値を保存する。``empire_room_refs``
と同様、``agent_id`` は ``agents.id`` への外部キーを意図的に持たない。``agents``
テーブルは ``feature/agent-repository``（別 PR）で投入されるため。その PR が
``op.create_foreign_key(...)`` で FK を追加する。

カスケード: Empire 行を削除するとその agent 参照も一緒に削除される。
``UNIQUE(empire_id, agent_id)`` は Aggregate レベルの重複エージェント不変条件を
ミラーする。

``Masked*`` TypeDecorator は付けない: ``role`` は enum 文字列、``name`` は 40 文字
で境界づけられる。どちらも storage.md §逆引き表 のシークレット保持カラムには
該当しない。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class EmpireAgentRefRow(Base):
    """``empire_agent_refs`` テーブルの ORM マッピング。"""

    __tablename__ = "empire_agent_refs"

    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (UniqueConstraint("empire_id", "agent_id", name="uq_empire_agent_refs_pair"),)


__all__ = ["EmpireAgentRefRow"]
