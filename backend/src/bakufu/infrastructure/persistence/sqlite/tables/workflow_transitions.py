"""``workflow_transitions`` テーブル — Workflow ↔ Transition 子行。

:class:`bakufu.domain.workflow.entities.Transition` の値を Workflow Aggregate の
関連テーブルとして保存する。``from_stage_id`` / ``to_stage_id`` は **意図的に**
外部キーには **しない**（``docs/features/workflow-repository/detailed-design.md``
§確定 J）。Aggregate レベルの ``_validate_transition_refs`` が、構築時に両端が
Workflow の ``stages`` コレクション内に存在することを既に強制する。

カスケード: Workflow 行の削除はその transition 行を消去する（``ON DELETE CASCADE``）。
``UNIQUE(workflow_id, transition_id)`` 制約は
:func:`bakufu.domain.workflow.dag_validators._validate_transition_id_unique` を行
レベルでミラーする。

どのカラムにも ``Masked*`` TypeDecorator は付けない — ソース／ターゲットの stage
ID も、enum 文字列の ``condition`` も、人間可読ラベルも Schneier 申し送り #6 の
シークレット カテゴリには該当しない。CI 3 層防御のノー マスク コントラクトに
登録される。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class WorkflowTransitionRow(Base):
    """``workflow_transitions`` テーブルの ORM マッピング。"""

    __tablename__ = "workflow_transitions"

    workflow_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    transition_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    from_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    to_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    condition: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False, default="")

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "transition_id",
            name="uq_workflow_transitions_pair",
        ),
    )


__all__ = ["WorkflowTransitionRow"]
