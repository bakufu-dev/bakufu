"""Agent Aggregate テーブル群: agents + agent_providers + agent_skills。

:class:`SqliteAgentRepository` を支える 3 つのテーブルを追加する:

* ``agents``（id PK + empire_id FK CASCADE + Persona スカラー群）。
  ``prompt_body`` カラムは ORM 層で :class:`MaskedText` TypeDecorator として
  宣言される（Alembic 側では ``TEXT`` として保存し、マスキングゲートは Python 側に置く）。
* ``agent_providers``（agent_id に FK CASCADE、UNIQUE(agent_id, provider_kind)）
  **に加えて**、``WHERE is_default = 1`` でスコープした ``agent_id`` の部分 UNIQUE
  インデックスを持つ。この部分インデックスは「Agent ごとにデフォルトプロバイダは
  ちょうど 1 つ」の §確定 G Defense-in-Depth 最終防衛線である — 将来の PR で
  破損した SQL 経路が混入しても、DB は同一 Agent に対して ``is_default=1`` の行が
  2 件入ることを拒否する。
* ``agent_skills``（agent_id に FK CASCADE、UNIQUE(agent_id, skill_id)）。
  ``path`` カラムは agent feature §確定 H パイプラインに従い 500 文字に制限する。
  H1〜H10 のトラバーサル防御は VO 側で実装する。

``docs/features/empire-repository/detailed-design.md`` §確定 F に従い、後続の
``feature/{aggregate}-repository`` PR はそれぞれの revision を積み重ねる。本 revision は
``down_revision = "0003_workflow_aggregate"`` を厳密に固定し、チェーン検査が単一 head
を強制するようにする。

Revision ID: 0004_agent_aggregate
Revises: 0003_workflow_aggregate
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_agent_aggregate"
down_revision: str | None = "0003_workflow_aggregate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column(
            "empire_id",
            sa.CHAR(32),
            sa.ForeignKey("empires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column(
            "archetype",
            sa.String(80),
            nullable=False,
            server_default=sa.text("''"),
        ),
        # MaskedText TypeDecorator は SQLite では TEXT として直列化される。
        # マスキングゲートは Python 側のデコレータで行う
        # （infrastructure/persistence/sqlite/base.py 参照）。
        sa.Column(
            "prompt_body",
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

    op.create_table(
        "agent_providers",
        sa.Column(
            "agent_id",
            sa.CHAR(32),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "provider_kind",
            sa.String(32),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "agent_id",
            "provider_kind",
            name="uq_agent_providers_pair",
        ),
    )
    # detailed-design §確定 G: 「Agent ごとにデフォルトプロバイダは高々 1 つ」を
    # 担保する Defense-in-Depth 最終防衛線としての部分 UNIQUE インデックス。
    # SQLite は部分インデックスをネイティブにサポートしており、同じ構文は
    # M5 以降の PostgreSQL マイグレーションにそのまま移植できる。
    op.create_index(
        "uq_agent_providers_default",
        "agent_providers",
        ["agent_id"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "agent_skills",
        sa.Column(
            "agent_id",
            sa.CHAR(32),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("skill_id", sa.CHAR(32), primary_key=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.UniqueConstraint(
            "agent_id",
            "skill_id",
            name="uq_agent_skills_pair",
        ),
    )


def downgrade() -> None:
    # 削除済みの親に対して FK CASCADE が発火しないよう、子テーブルから先に削除する。
    op.drop_table("agent_skills")
    op.drop_index("uq_agent_providers_default", table_name="agent_providers")
    op.drop_table("agent_providers")
    op.drop_table("agents")
