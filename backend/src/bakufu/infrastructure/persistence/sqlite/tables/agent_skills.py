"""``agent_skills`` テーブル — Agent ↔ SkillRef 子行。

:class:`bakufu.domain.agent.value_objects.SkillRef` の値を Agent Aggregate の
関連テーブルとして保存する。``ON DELETE CASCADE`` は親 Agent 削除時に skill 行を
消去する。UNIQUE(agent_id, skill_id) は ``_validate_skill_id_unique`` Aggregate
不変条件を行レベルでミラーする。

``path`` は通常の ``String(500)`` として保存する — H1〜H10 トラバーサル防御
パイプラインは VO 構築時に走る
（:func:`bakufu.domain.agent.path_validators._validate_skill_path`）ため、
:meth:`SqliteAgentRepository.find_by_id` 経由の水和では ``_from_row`` 内部の
``SkillRef.model_validate`` 呼び出しがバリデータを自動的に再実行する。
リポジトリは直接コントラクトを再チェックすることはない。

どのカラムにも ``Masked*`` TypeDecorator は付けない。Skill 名 / パス / id は
シークレット意味を持たない運用メタデータ。CI 3 層防御の *no-mask* コントラクト
が本テーブルを登録する。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class AgentSkillRow(Base):
    """``agent_skills`` テーブルの ORM マッピング。"""

    __tablename__ = "agent_skills"

    agent_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    skill_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "skill_id",
            name="uq_agent_skills_pair",
        ),
    )


__all__ = ["AgentSkillRow"]
