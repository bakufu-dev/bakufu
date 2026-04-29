"""``agents`` テーブル — Agent Aggregate ルート行。

Agent Aggregate の 8 個のスカラー カラムを保持する。2 つの関連コレクション
（``providers`` / ``skills``）は :mod:`...tables.agent_providers` /
:mod:`...tables.agent_skills` に置き、行幅を抑え CASCADE 対象を明確にする。

``empire_id`` は ``empires.id`` への ``ON DELETE CASCADE`` 外部キーを持つ —
Empire が削除されると雇用された Agent も一緒に削除される。Agent Aggregate ルート
は対応する ``empire_id`` フィールドを保持する（``backend/src/bakufu/domain/agent/
agent.py`` 参照）ため、``SqliteAgentRepository.save()`` は呼び元に問い合わせず
このカラムを埋められる。

``name`` は意図的に DB レベルで UNIQUE として **宣言しない**。「Empire 内で名前
一意」の不変条件は :meth:`AgentRepository.find_by_name` 経由でアプリケーション層
が強制する（``docs/features/agent-repository/detailed-design.md`` §設計判断補足
「なぜ agents.name に DB UNIQUE を張らないか」を参照）。これにより、
``IntegrityError`` に先取りされず、MSG-AG-NNN 文言がアプリケーション層の声で出る。

カラム別シークレット ハンドリング（§確定 H + Schneier 申し送り #3 实適用）:

* ``prompt_body`` は :class:`MaskedText` カラム。``MaskingGateway`` が API キー /
  OAuth トークン / GitHub PAT 等の断片を、行が SQLite に到達する *前* に
  ``<REDACTED:*>`` に置換する。これにより raw SQL 検査やバックアップでも CEO が
  貼り付けたシークレットが漏洩しない。``MaskingGateway`` の **不可逆性** により、
  :class:`SqliteAgentRepository.find_by_id` 経由の往復は ``prompt_body`` が伏字化
  された形の Persona を返す（§確定 H 不可逆性凍結） — プロンプト ディスパッチ前に
  ``<REDACTED:*>`` マーカーを検出する責務は ``feature/llm-adapter`` に置かれる。
* このテーブルの他カラムはマスクされない。CI 3 層防御の *partial-mask* コントラクト
  はマスク カラム数を厳密に 1 つに固定するため、将来の PR がマスキング表面を
  サイレントに広げる（あるいは ``prompt_body`` を素の :class:`Text` に戻す）こと
  はできない。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UUIDStr,
)


class AgentRow(Base):
    """``agents`` テーブルの ORM マッピング。"""

    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("empires.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    archetype: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    prompt_body: Mapped[str] = mapped_column(MaskedText, nullable=False, default="")
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


__all__ = ["AgentRow"]
