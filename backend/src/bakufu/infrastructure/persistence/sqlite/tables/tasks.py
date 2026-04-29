"""``tasks`` テーブル — Task Aggregate ルート行。

Task Aggregate ルートの 8 個のスカラー カラムを保持する。子コレクション
（アサイン エージェント / 会話 / メッセージ / 成果物 / 添付）はコンパニオン
モジュールに置き、ルート行の幅を抑え CASCADE 対象を明確にする。

``room_id`` は ``rooms.id`` に対する ``ON DELETE CASCADE`` 外部キーを持つ —
Room が削除されると関連 Task も一緒に削除される。

``directive_id`` は ``directives.id`` に対する ``ON DELETE CASCADE`` 外部キーを
持つ — Directive が削除されると関連 Task も一緒に削除される。

``current_stage_id`` は ``workflow_stages.id`` への FK を意図的に **持たない** —
Task と Workflow は別の Aggregate であり、FK を加えると Aggregate 境界違反となり、
ON DELETE の曖昧性も生じる（§確定 R1-G）。存在検証はアプリケーション層
（``TaskService``）の責務。

``last_error`` は :class:`MaskedText` カラム（§確定 R1-E）。マスキング ゲートウェイ
が、行が SQLite に到達する *前* に埋め込まれた API キー / OAuth トークン / LLM
エラー シークレットを ``<REDACTED:*>`` に置換する — DB ダンプ / SQL ログからの
シークレット漏洩を防ぐ。Nullable: BLOCKED の Task のみ ``last_error`` 値を持つ。

2 つのインデックスを作成する（§確定 R1-K）:

* ``ix_tasks_room_id`` — ``count_by_room`` の WHERE フィルタ用。``room_id`` 上の
  非 UNIQUE 単一カラム インデックス。
* ``ix_tasks_status_updated_id`` — 複合 ``(status, updated_at, id)`` 非 UNIQUE
  インデックス。``find_blocked`` の ``WHERE status = 'BLOCKED' ORDER BY
  updated_at DESC, id DESC`` を 1 回の B-tree スキャンで最適化する。status
  プレフィックスは ``count_by_status`` にも効く。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    MaskedText,
    UTCDateTime,
    UUIDStr,
)


class TaskRow(Base):
    """``tasks`` テーブルの ORM マッピング。"""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    room_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    directive_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("directives.id", ondelete="CASCADE"),
        nullable=False,
    )
    # current_stage_id: workflow_stages.id への FK は意図的に持たない。
    # Task と Workflow は別の Aggregate であり、Aggregate 境界により Task は
    # Workflow の内部 stage テーブルに直接依存してはならない。
    # 存在検証は TaskService の責務（§確定 R1-G）。
    current_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # last_error: MaskedText — LLM のエラー メッセージは API キー / 認証トークンを
    # 含み得る。MaskedText.process_bind_param が SQLite 格納前にシークレットを
    # 伏字化する（§確定 R1-E、伏字化は不可逆）。
    last_error: Mapped[str | None] = mapped_column(MaskedText, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        # §確定 R1-K: count_by_room 用の非 UNIQUE 単一カラム インデックス。
        Index("ix_tasks_room_id", "room_id"),
        # §確定 R1-K: 複合 (status, updated_at, id) インデックス。
        # find_blocked の WHERE status = 'BLOCKED' は先頭プレフィックスを使い、
        # ORDER BY updated_at DESC, id DESC は後続カラムを使う。
        # count_by_status も status プレフィックスの恩恵を受ける。
        Index("ix_tasks_status_updated_id", "status", "updated_at", "id"),
    )


__all__ = ["TaskRow"]
