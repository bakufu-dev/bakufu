"""ExternalReviewGate Aggregate テーブル群: 3 テーブル + 3 インデックス。

:class:`SqliteExternalReviewGateRepository` を支える 3 つのテーブルを追加する:

* ``external_review_gates``（id PK + task_id FK CASCADE + stage_id NOT NULL
  （FK 無し、Aggregate 境界 §設計決定 ERGR-001） + reviewer_id NOT NULL（FK 無し、
  Owner Aggregate は M2 範囲） + decision String(32) NOT NULL + feedback_text
  MaskedText NOT NULL + snapshot_stage_id NOT NULL（FK 無し） +
  snapshot_body_markdown MaskedText NOT NULL + snapshot_committed_by NOT NULL
  （FK 無し） + snapshot_committed_at UTCDateTime NOT NULL + created_at
  UTCDateTime NOT NULL + decided_at UTCDateTime NULL）。
  インデックス 3 つ: ``ix_external_review_gates_task_id_created``（複合）、
  ``ix_external_review_gates_reviewer_decision``（複合）、
  ``ix_external_review_gates_decision``（単一カラム）。

* ``external_review_gate_attachments``（id PK（save 内部、save ごとに uuid4()） +
  gate_id FK CASCADE + sha256 String(64) NOT NULL + filename String(255) NOT NULL
  + mime_type String(128) NOT NULL + size_bytes Integer NOT NULL +
  UNIQUE(gate_id, sha256)）。

* ``external_review_audit_entries``（id PK（ドメイン AuditEntry.id） + gate_id
  FK CASCADE + actor_id NOT NULL（FK 無し、Owner Aggregate 境界） + action
  String(32) NOT NULL + comment MaskedText NOT NULL + occurred_at UTCDateTime
  NOT NULL）。

``external_review_gates.task_id → tasks.id`` ON DELETE CASCADE: Task が削除
されるとその関連 Gate も一緒に削除される。これは唯一の Aggregate 間 FK
（§設計決定 ERGR-001 — 他のすべての UUID 参照は境界横断であり意図的に FK 無し）。

``stage_id``、``reviewer_id``、``snapshot_stage_id``、``snapshot_committed_by``、
``actor_id`` は意図的に **FK を持たない**（§設計決定 ERGR-001）:
- Stage / Workflow Aggregate 境界（Gate は workflow_stages に依存してはならない）。
- Owner Aggregate は未実装（M2 範囲。MVP は固定 UUID を使う）。
- snapshot_committed_by: Agent 削除に CASCADE が伴うと監査凍結された
  スナップショットを破壊してしまう（task-repository §設計決定 TR-001 と同論理）。
- actor_id: reviewer_id と同じ Owner Aggregate の根拠。

Aggregate 間 FK 申し送りは追加しない: §設計決定 ERGR-001 がこれを恒久的な
設計決定として解決する（BUG 申し送りではない）。

``docs/features/external-review-gate-repository/detailed-design.md`` §確定 R1-B、
§設計決定 ERGR-001、§確定 R1-K に従う。

Revision ID: 0008_external_review_gate_aggregate
Revises: 0007_task_aggregate
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_external_review_gate_aggregate"
down_revision: str | None = "0007_task_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- external_review_gates テーブル ------------------------------------
    op.create_table(
        "external_review_gates",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "task_id",
            sa.CHAR(32),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # stage_id: workflow_stages.id への FK は意図的に持たない —
        # Aggregate 境界（§設計決定 ERGR-001）。GateService が存在性を検証する。
        sa.Column("stage_id", sa.CHAR(32), nullable=False),
        # reviewer_id: 意図的に FK 無し — Owner Aggregate は未実装
        # （§設計決定 ERGR-001）。MVP: CEO = 固定 UUID を持つ単一システム所有者。
        sa.Column("reviewer_id", sa.CHAR(32), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        # feedback_text: MaskedText は TEXT としてシリアライズされる
        # （§設計決定 ERGR-002、§確定 R1-E）。CEO のレビュー コメント。webhook URL
        # / API キーを持ち得る。
        sa.Column("feedback_text", sa.Text(), nullable=False),
        # インライン snapshot_* カラム — Gate 作成後は不変（§確定 D）。
        # snapshot_stage_id: workflow_stages.id への FK 無し — Aggregate 境界。
        sa.Column("snapshot_stage_id", sa.CHAR(32), nullable=False),
        # snapshot_body_markdown: MaskedText は TEXT としてシリアライズされる
        # （§確定 R1-E）。Agent が書く成果物本体。LLM 出力はシークレットを含み得る。
        sa.Column("snapshot_body_markdown", sa.Text(), nullable=False),
        # snapshot_committed_by: agents.id への FK 無し — CASCADE 付きの Agent
        # 削除は監査凍結されたスナップショットを破壊してしまう（§設計決定 ERGR-001）。
        sa.Column("snapshot_committed_by", sa.CHAR(32), nullable=False),
        # UTCDateTime TypeDecorator は ISO-8601 テキストを格納し、Python 側では
        # 常に tz-aware。
        sa.Column("snapshot_committed_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        # decided_at: decision == PENDING のときに限り NULL（ドメイン不変条件）。
        sa.Column("decided_at", sa.Text(), nullable=True),
    )

    # §確定 R1-K: find_by_task_id 用の複合 (task_id, created_at) インデックス。
    op.create_index(
        "ix_external_review_gates_task_id_created",
        "external_review_gates",
        ["task_id", "created_at"],
        unique=False,
    )

    # §確定 R1-K: find_pending_by_reviewer 用の複合 (reviewer_id, decision)。
    op.create_index(
        "ix_external_review_gates_reviewer_decision",
        "external_review_gates",
        ["reviewer_id", "decision"],
        unique=False,
    )

    # §確定 R1-K: count_by_decision 用の単一カラム (decision)。
    op.create_index(
        "ix_external_review_gates_decision",
        "external_review_gates",
        ["decision"],
        unique=False,
    )

    # ---- external_review_gate_attachments テーブル -------------------------
    op.create_table(
        "external_review_gate_attachments",
        # id: save 内部 PK（save() ごとに uuid4() を再生成）。
        # ビジネス キー: UNIQUE(gate_id, sha256)。
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "gate_id",
            sa.CHAR(32),
            sa.ForeignKey("external_review_gates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # sha256: 64 文字の小文字 hex。Attachment VO で検証される。
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        # UNIQUE(gate_id, sha256): 1 つの Gate 内のコンテンツ重複を防ぐ。
        # sha256 は決定的な ORDER BY アンカーを提供する（§確定 R1-H）。
        sa.UniqueConstraint(
            "gate_id",
            "sha256",
            name="uq_erg_attachments_gate_sha256",
        ),
    )

    # ---- external_review_audit_entries テーブル ---------------------------
    op.create_table(
        "external_review_audit_entries",
        # id: ドメイン AuditEntry.id から取得（save 時に再生成しない）。
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "gate_id",
            sa.CHAR(32),
            sa.ForeignKey("external_review_gates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # actor_id: 意図的に FK 無し — Owner Aggregate は未実装
        # （§設計決定 ERGR-001）。上の reviewer_id と同じ根拠。
        sa.Column("actor_id", sa.CHAR(32), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        # comment: MaskedText は TEXT としてシリアライズされる（§確定 R1-E）。
        # CEO 著作テキスト。webhook URL / API キーを持ち得る。
        sa.Column("comment", sa.Text(), nullable=False),
        # UTCDateTime TypeDecorator は ISO-8601 テキストを格納する。
        sa.Column("occurred_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    # 逆順: まず子テーブル（CASCADE FK 順）、次にルート。
    # 1. 最深の子テーブルを削除する（本マイグレーション内に依存先がない）。
    op.drop_table("external_review_audit_entries")
    op.drop_table("external_review_gate_attachments")

    # 2. ルート テーブル削除前にインデックスを削除する。
    op.drop_index(
        "ix_external_review_gates_decision",
        table_name="external_review_gates",
    )
    op.drop_index(
        "ix_external_review_gates_reviewer_decision",
        table_name="external_review_gates",
    )
    op.drop_index(
        "ix_external_review_gates_task_id_created",
        table_name="external_review_gates",
    )

    # 3. ルート テーブルを削除する。
    op.drop_table("external_review_gates")
