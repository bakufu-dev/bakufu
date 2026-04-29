"""``agent_providers`` テーブル — Agent ↔ ProviderConfig 子行。

:class:`bakufu.domain.agent.value_objects.ProviderConfig` の値を Agent Aggregate
の関連テーブルとして保存する。``ON DELETE CASCADE`` は親 Agent 削除時に provider
行を消去する。UNIQUE(agent_id, provider_kind) は ``_validate_provider_kind_unique``
Aggregate 不変条件を行レベルでミラーする。

興味深い制約は **部分一意インデックス** ``WHERE is_default = 1`` —
``docs/features/agent-repository/detailed-design.md`` §確定 G を参照。これにより
「Agent ごとに default プロバイダはちょうど 1 つ」不変条件に **多層防御** の基盤
が与えられる: Aggregate レベルのヘルパ ``_validate_default_provider_count`` が
既に強制しているが、将来の PR が破損 SQL 経路（raw INSERT、手書きマイグレーション）
を導入しても、DB は同じ Agent 上で 2 つの ``is_default=1`` 行をホストすることを
拒否し続ける。SQLite は部分インデックスを標準で提供する
（https://www.sqlite.org/partialindex.html）。同じ構文は PostgreSQL にも完全に
ポートできる。

どのカラムにも ``Masked*`` TypeDecorator は付けない。``provider_kind`` は enum
文字列、``model`` はシークレット意味を持たない LLM モデル識別子、``is_default``
は真偽フラグ。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class AgentProviderRow(Base):
    """``agent_providers`` テーブルの ORM マッピング。"""

    __tablename__ = "agent_providers"

    agent_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    provider_kind: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "provider_kind",
            name="uq_agent_providers_pair",
        ),
        # 部分一意インデックス — 1 つの agent_id に対し ``is_default = 1`` の行は
        # 最大 1 つ。SQLite / PostgreSQL の構文は同一。詳細設計 §確定 G:
        # Aggregate レベルの ``_validate_default_provider_count`` チェックと並ぶ
        # 多層防御。
        Index(
            "uq_agent_providers_default",
            "agent_id",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )


__all__ = ["AgentProviderRow"]
