"""Directive Aggregate テーブル: directives。

:class:`SqliteDirectiveRepository` を支えるテーブルを追加する:

* ``directives``（id PK + text MaskedText NOT NULL + target_room_id は rooms.id
  への FK CASCADE + created_at DateTime NOT NULL + task_id は nullable CHAR(32)
  でこの段階では FK を付けない — 下記 §BUG-DRR-001 申し送り 参照）。
* Room スコープの ``find_by_room`` クエリ用の
  ``INDEX(target_room_id, created_at)`` 複合インデックス。

§BUG-DRR-001 FK申し送り:
``directives.task_id`` は本 revision では nullable CHAR(32) として宣言する。
``tasks.id`` への FK は task-repository PR で
``op.batch_alter_table('directives', recreate='always')`` 経由でクローズする
（0005_room_aggregate での BUG-EMR-001 クローズと同パターン、empire-repository PR #33）。

延期する FK には ON DELETE RESTRICT を推奨する: Directive は指示の監査証跡であり、
Directive がまだ参照している Task の削除はブロックすべきである。

``docs/features/directive-repository/detailed-design.md`` §確定 R1-B
および §確定 R1-C に従う。

Revision ID: 0006_directive_aggregate
Revises: 0005_room_aggregate
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_directive_aggregate"
down_revision: str | None = "0005_room_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # directives テーブル: 5 カラムのフラットな Aggregate（子テーブルなし）。
    op.create_table(
        "directives",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        # MaskedText TypeDecorator は SQLite では TEXT として直列化される。
        # マスキングゲートは Python 側のデコレータで行う（base.py の MaskedText）。§確定 R1-E。
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "target_room_id",
            sa.CHAR(32),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # created_at uses Text storage (UTCDateTime TypeDecorator stores
        # ISO-8601 string). Always UTC-aware at the Python layer.
        sa.Column("created_at", sa.Text(), nullable=False),
        # task_id: nullable CHAR(32) with NO FK at this level — see §BUG-DRR-001.
        # The FK closure (fk_directives_task_id → tasks.id RESTRICT) is deferred
        # to the task-repository PR.
        sa.Column("task_id", sa.CHAR(32), nullable=True),
    )

    # §確定 R1-D: composite index for Room-scoped find_by_room query.
    # Left-prefix covers ``WHERE target_room_id = ?`` and
    # ``WHERE target_room_id = ? ORDER BY created_at DESC``.
    op.create_index(
        "ix_directives_target_room_id_created_at",
        "directives",
        ["target_room_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse order: index first, then table.
    op.drop_index("ix_directives_target_room_id_created_at", table_name="directives")
    op.drop_table("directives")
