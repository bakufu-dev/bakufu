"""Task Aggregate テーブル群: tasks + 3 子テーブル、BUG-DRR-001 FK クロージャ。

:class:`SqliteTaskRepository` を支える 4 つのテーブルを追加する:

* ``tasks``（id PK + room_id FK CASCADE + directive_id FK CASCADE +
  current_stage_id NOT NULL（FK 無し、Aggregate 境界 §確定 R1-G） +
  status String(32) NOT NULL + last_error MaskedText NULL +
  created_at / updated_at UTCDateTime NOT NULL）。
  インデックス 2 つ: ``ix_tasks_room_id``（単一カラム）と
  ``ix_tasks_status_updated_id``（複合、§確定 R1-K）。
* ``task_assigned_agents``（複合 PK (task_id, agent_id) + task_id への FK CASCADE
  + §設計決定 TR-001 により agent_id への FK 無し + UNIQUE(task_id, agent_id) の
  多層防御）。
* ``deliverables``（id PK + task_id FK CASCADE + stage_id NOT NULL（FK 無し、
  Aggregate 境界） + body_markdown MaskedText NOT NULL + committed_by NOT NULL
  （FK 無し） + committed_at UTCDateTime NOT NULL + UNIQUE(task_id, stage_id)）。
* ``deliverable_attachments``（id PK + deliverable_id FK CASCADE + sha256
  String(64) NOT NULL + filename String(255) NOT NULL + mime_type
  String(128) NOT NULL + size_bytes Integer NOT NULL +
  UNIQUE(deliverable_id, sha256)）。

``conversations`` / ``conversation_messages`` テーブルは除外（§BUG-TR-002
凍結済み）: Task Aggregate には現状 ``conversations`` 属性が無い。これらの
テーブルは ``Task.conversations: list[Conversation]`` を配線する将来の
マイグレーションで追加される。

加えて BUG-DRR-001 FK 申し送りを完了する:

* ``directives.task_id → tasks.id`` FK（ON DELETE RESTRICT）を
  ``op.batch_alter_table('directives', recreate='always')`` 経由で追加する。
  SQLite は ``ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY`` を直接サポートしない
  ため。バッチ操作は内部でテーブルを再構築し、既存行をコピーして名前を変更する。
  0005_room_aggregate の BUG-EMR-001 クロージャ（empire-repository PR #47）と
  同じパターン。

ON DELETE RESTRICT の根拠: Task を参照する Directive は、Task が削除された際に
サイレントに参照を失ってはならない。アプリケーション層は Task 削除前に
``directive.unlink_task()`` + ``save()`` を呼ばなければならない
（Fail Fast §確定 R1-C）。

``docs/features/task-repository/detailed-design.md`` §確定 R1-B、§確定 R1-C、
§確定 R1-K に従う。

Revision ID: 0007_task_aggregate
Revises: 0006_directive_aggregate
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_task_aggregate"
down_revision: str | None = "0006_directive_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- tasks テーブル ----------------------------------------------------
    op.create_table(
        "tasks",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "room_id",
            sa.CHAR(32),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "directive_id",
            sa.CHAR(32),
            sa.ForeignKey("directives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # current_stage_id: workflow_stages.id への FK は意図的に持たない —
        # Aggregate 境界（§確定 R1-G）。TaskService が存在性を検証する。
        sa.Column("current_stage_id", sa.CHAR(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        # last_error: MaskedText は TEXT としてシリアライズされる。Python 側の
        # TypeDecorator がマスキング ゲートを実行する（base.py MaskedText）。
        # NULL = BLOCKED ではない。
        sa.Column("last_error", sa.Text(), nullable=True),
        # UTCDateTime TypeDecorator は ISO-8601 テキストを格納し、Python 側では
        # 常に tz-aware。
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )

    # §確定 R1-K: count_by_room WHERE フィルタ用の単一カラム インデックス。
    op.create_index("ix_tasks_room_id", "tasks", ["room_id"], unique=False)

    # §確定 R1-K: 複合 (status, updated_at, id) インデックス。
    # find_blocked の WHERE status = 'BLOCKED' ORDER BY updated_at DESC, id DESC
    # と count_by_status の WHERE status = ? を 1 回の B-tree スキャンでカバーする。
    op.create_index(
        "ix_tasks_status_updated_id",
        "tasks",
        ["status", "updated_at", "id"],
        unique=False,
    )

    # ---- task_assigned_agents テーブル ------------------------------------
    op.create_table(
        "task_assigned_agents",
        sa.Column(
            "task_id",
            sa.CHAR(32),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        # agent_id: agents.id への FK は意図的に持たない — Aggregate 境界
        # （§設計決定 TR-001、room_members.agent_id 先例と同方針）。
        sa.Column("agent_id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        # 多層防御: 明示的な UNIQUE が Aggregate 不変条件
        # _validate_assigned_agents_unique を DB レベルでミラーする。
        sa.UniqueConstraint("task_id", "agent_id", name="uq_task_assigned_agents"),
    )

    # ---- deliverables テーブル --------------------------------------------
    op.create_table(
        "deliverables",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "task_id",
            sa.CHAR(32),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # stage_id: workflow_stages.id への FK は意図的に持たない — Aggregate
        # 境界（§確定 R1-G、tasks.current_stage_id と同じ理由）。
        sa.Column("stage_id", sa.CHAR(32), nullable=False),
        # body_markdown: MaskedText は TEXT としてシリアライズされる（§確定 R1-E）。
        sa.Column("body_markdown", sa.Text(), nullable=False),
        # committed_by: agents.id への FK は意図的に持たない — Aggregate 境界
        # （§設計決定 TR-001、task_assigned_agents.agent_id と同じ）。
        sa.Column("committed_by", sa.CHAR(32), nullable=False),
        # UTCDateTime TypeDecorator は ISO-8601 テキストを格納する。
        sa.Column("committed_at", sa.Text(), nullable=False),
        # UNIQUE(task_id, stage_id): Aggregate の dict[StageId, Deliverable] キー
        # 一意性不変条件を DB レベルでミラーする。
        sa.UniqueConstraint("task_id", "stage_id", name="uq_deliverables_task_stage"),
    )

    # ---- deliverable_attachments テーブル ---------------------------------
    op.create_table(
        "deliverable_attachments",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "deliverable_id",
            sa.CHAR(32),
            sa.ForeignKey("deliverables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # sha256: 64 文字の小文字 hex。Attachment VO で検証される。
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        # UNIQUE(deliverable_id, sha256): 単一 Deliverable 内のコンテンツ重複を
        # 防ぐ。sha256 は決定的な ORDER BY アンカーを提供する。
        sa.UniqueConstraint(
            "deliverable_id",
            "sha256",
            name="uq_deliverable_attachments_sha256",
        ),
    )

    # ---- BUG-DRR-001 FK クロージャ ----------------------------------------
    # ``directives.task_id → tasks.id`` FK（ON DELETE RESTRICT）。
    # SQLite は ``ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY`` を直接
    # サポートしない。Alembic の ``batch_alter_table(recreate='always')`` が
    # 内部でテーブルを再構築し、既存行をコピーして名前を変更する。
    # ``recreate='always'`` フラグはカラム変更が検出されない場合でも再構築を
    # 強制する — SQLite での FK 追加に必要（0005_room_aggregate での
    # BUG-EMR-001 クロージャと同じパターン）。
    with op.batch_alter_table("directives", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_directives_task_id",
            "tasks",
            ["task_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    # 逆順:
    # 1. まず BUG-DRR-001 FK クロージャを削除する（directives は tasks に依存）。
    with op.batch_alter_table("directives", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_directives_task_id", type_="foreignkey")

    # 2. 子テーブルを削除する（CASCADE 依存順、最深から）。
    op.drop_table("deliverable_attachments")

    # 3. 中間レベルの子テーブルを削除する。
    op.drop_table("deliverables")
    op.drop_table("task_assigned_agents")

    # 4. ルート テーブル削除前にインデックスを削除する。
    op.drop_index("ix_tasks_status_updated_id", table_name="tasks")
    op.drop_index("ix_tasks_room_id", table_name="tasks")

    # 5. ルート テーブルを削除する。
    op.drop_table("tasks")
