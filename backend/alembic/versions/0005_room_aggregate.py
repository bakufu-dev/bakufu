"""Room Aggregate テーブル群: rooms + room_members、加えて empire_room_refs の FK クロージャ。

:class:`SqliteRoomRepository` を支える 2 つのテーブルを追加する:

* ``rooms``（id PK + empire_id FK CASCADE + workflow_id FK RESTRICT +
  スカラー 5 カラム）。``prompt_kit_prefix_markdown`` カラムは Alembic 側では
  ``TEXT`` として保存される（Alembic は ``MaskedText`` を知らない）。マスキング
  ゲートは TypeDecorator により Python 側で行う。
* ``room_members``（複合 PK(room_id, agent_id, role) + room_id に FK CASCADE +
  §確定 R1-D Defense-in-Depth のための UNIQUE(room_id, agent_id, role) +
  room §確定 に従い agent_id には FK を付けない）。

加えて BUG-EMR-001 の FK クロージャを完了する:

* ``empire_room_refs.room_id → rooms.id`` FK（ON DELETE CASCADE）を
  ``op.batch_alter_table('empire_room_refs', recreate='always')`` 経由で追加する。
  SQLite は ``ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY`` を直接サポートしないため
  である。バッチ操作はテーブルを内部的に再構築するため、既存行はすべて保持される。

``docs/features/empire-repository/detailed-design.md`` §確定 F に従い、後続の
``feature/{aggregate}-repository`` PR はそれぞれの revision を積み重ねる。
本 revision は ``down_revision = "0004_agent_aggregate"`` を厳密に固定し、
チェーン検査が単一 head を強制するようにする。

Revision ID: 0005_room_aggregate
Revises: 0004_agent_aggregate
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_room_aggregate"
down_revision: str | None = "0004_agent_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: rooms テーブル（empire_id FK CASCADE + workflow_id FK RESTRICT）。
    op.create_table(
        "rooms",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "empire_id",
            sa.CHAR(32),
            sa.ForeignKey("empires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            sa.CHAR(32),
            sa.ForeignKey("workflows.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column(
            "description",
            sa.String(500),
            nullable=False,
            server_default=sa.text("''"),
        ),
        # MaskedText TypeDecorator は SQLite では TEXT として直列化される。
        # マスキングゲートは Python 側のデコレータで行う（base.py の MaskedText）。
        sa.Column(
            "prompt_kit_prefix_markdown",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # §確定 R1-F: Empire スコープの find_by_name 用の非 UNIQUE 複合インデックス。
    # 左端プレフィックスにより ``WHERE empire_id = ?`` と
    # ``WHERE empire_id = ? AND name = ?`` の両方のクエリを最適化する。
    op.create_index(
        "ix_rooms_empire_id_name",
        "rooms",
        ["empire_id", "name"],
        unique=False,
    )

    # Step 2: room_members テーブル（複合 PK + FK CASCADE + §確定 R1-D の UNIQUE）。
    op.create_table(
        "room_members",
        sa.Column(
            "room_id",
            sa.CHAR(32),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.CHAR(32),
            primary_key=True,
            nullable=False,
            # agents.id への FK を意図的に付けない — アプリケーション層の責務
            # （room §確定、detailed-design §設計判断補足 を参照）。
        ),
        sa.Column(
            "role",
            sa.String(32),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        # §確定 R1-D: 複合 PK に加え明示的に UniqueConstraint を宣言する。
        # これにより CI の Layer 2 アーキテクチャテストが ``__table_args__``
        # スキャンによって制約の存在を検証できる（agent_providers と同パターン）。
        sa.UniqueConstraint(
            "room_id",
            "agent_id",
            "role",
            name="uq_room_members_triplet",
        ),
    )

    # Step 3: empire_room_refs の FK クロージャ（BUG-EMR-001 のクローズ）。
    # SQLite は ``ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY`` を直接サポートしない。
    # Alembic の ``batch_alter_table(recreate='always')`` はテーブルを内部的に再構築し、
    # 既存行をコピーした上で rename する。``recreate='always'`` フラグはカラム変更が
    # 検出されない場合でも再構築を強制する — SQLite で FK を追加するために必要。
    with op.batch_alter_table("empire_room_refs", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_empire_room_refs_room_id",
            "rooms",
            ["room_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    # 逆順: FK クロージャ → インデックス → 子テーブル → 親テーブル。
    with op.batch_alter_table("empire_room_refs", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_empire_room_refs_room_id", type_="foreignkey")

    op.drop_index("ix_rooms_empire_id_name", table_name="rooms")
    # 子テーブルから先に削除する（room_members.room_id は rooms.id への FK CASCADE）。
    op.drop_table("room_members")
    op.drop_table("rooms")
