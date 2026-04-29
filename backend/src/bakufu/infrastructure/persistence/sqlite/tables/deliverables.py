"""``deliverables`` テーブル — Task Aggregate 用の Deliverable 子行。

各行は Stage ごとの成果物スナップショット 1 件を表す。Task Aggregate は
``deliverables: dict[StageId, Deliverable]`` を保持するため、与えられた Stage に
ついては最新コミットだけが残る（dict キーの一意性）。``UNIQUE(task_id, stage_id)``
制約はこの不変条件をデータベース レベルでも強制する。

``task_id`` は ``tasks.id`` への ``ON DELETE CASCADE`` 外部キーを持つ。
``deliverable_attachments`` 行は
``deliverables.id → deliverable_attachments.deliverable_id`` の CASCADE 連鎖により
推移的に削除される。

``stage_id`` は ``workflow_stages.id`` への FK を意図的に **持たない** —
``tasks.current_stage_id`` と同じ Aggregate 境界の理由（§確定 R1-G）。

``committed_by`` は ``agents.id`` への FK を意図的に **持たない** —
``task_assigned_agents.agent_id`` と同じ Aggregate 境界の理由（§設計決定 TR-001）。

``body_markdown`` は :class:`MaskedText` カラム（§確定 R1-E）。成果物として提出
されるエージェント出力には埋め込まれた API キー / 認証トークンが含まれ得る。
マスキング ゲートウェイが、行が SQLite に到達する *前* にそれらを ``<REDACTED:*>``
に置換する（不可逆伏字化、§確定 R1-G 不可逆性凍結）。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class DeliverableRow(Base):
    """``deliverables`` テーブルの ORM マッピング。"""

    __tablename__ = "deliverables"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    # stage_id: workflow_stages.id への FK は意図的に持たない。
    # Aggregate 境界: Workflow と Task は独立した Aggregate であり、Stage 削除を
    # deliverables に CASCADE 伝播させてはならない（§確定 R1-G）。
    stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    # body_markdown: MaskedText — エージェント提出出力はシークレットを含み得る。
    # MaskedText.process_bind_param が SQLite 格納前に伏字化する（§確定 R1-E）。
    body_markdown: Mapped[str] = mapped_column(MaskedText, nullable=False)
    # committed_by: agents.id への FK は意図的に持たない。
    # Aggregate 境界（§設計決定 TR-001、room_members.agent_id 先例と同方針）。
    committed_by: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    committed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        # UNIQUE(task_id, stage_id): Aggregate の
        # ``deliverables: dict[StageId, Deliverable]`` キー一意性不変条件を
        # DB レベルでミラーする。また、save() §確定 R1-B の step-1 DELETE +
        # step-8 INSERT パターンが UNIQUE 違反に遭遇しないことも保証する。
        UniqueConstraint("task_id", "stage_id", name="uq_deliverables_task_stage"),
    )


__all__ = ["DeliverableRow"]
