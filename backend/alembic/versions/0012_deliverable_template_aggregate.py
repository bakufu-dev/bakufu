"""DeliverableTemplate / RoleProfile Aggregate テーブル追加（Issue #119）。

2 テーブルを追加する:

* ``deliverable_templates`` — DeliverableTemplate Aggregate ルート行
  （8 カラム: id / name / description / type / version / schema /
  acceptance_criteria_json / composition_json）
* ``role_profiles`` — RoleProfile Aggregate ルート行
  （4 カラム: id / empire_id / role / deliverable_template_refs_json）
  + UNIQUE(empire_id, role) + FK → empires.id ON DELETE CASCADE

§確定 K（``docs/features/deliverable-template/repository/detailed-design.md``）:

* upgrade は deliverable_templates → role_profiles の順で CREATE する
  （FK を持つ role_profiles が後）。
* downgrade は逆順: role_profiles → deliverable_templates で DROP する
  （FK を持つ role_profiles を先に削除してから親テーブルを削除）。
* MVP 時点で本番データなし → DEFAULT '[]' のみで充足（データ変換不要）。

Revision ID: 0012_deliverable_template_aggregate
Revises: 0011_stage_required_deliverables
Create Date: 2026-04-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_deliverable_template_aggregate"
down_revision: str | None = "0011_stage_required_deliverables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Step 1: deliverable_templates テーブル作成（FK なし — 先に作成可能）。
    op.create_table(
        "deliverable_templates",
        sa.Column("id", sa.CHAR(32), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        # TemplateType enum 値: "MARKDOWN" / "JSON_SCHEMA" / "OPENAPI" /
        # "CODE_SKELETON" / "PROMPT"（§確定 D の type 判別キー）。
        sa.Column("type", sa.String(32), nullable=False),
        # SemVer TEXT 形式 "major.minor.patch"（例: "1.2.3"）— §確定 E。
        sa.Column("version", sa.String(20), nullable=False),
        # §確定 D: JSON_SCHEMA/OPENAPI は json.dumps した dict を格納。
        # それ以外は plain text をそのまま格納。
        sa.Column("schema", sa.Text(), nullable=False),
        # §確定 F: list[AcceptanceCriterion] の JSON シリアライズ（DEFAULT '[]'）。
        sa.Column(
            "acceptance_criteria_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        # §確定 F: list[DeliverableTemplateRef] の JSON シリアライズ（DEFAULT '[]'）。
        sa.Column(
            "composition_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Step 2: role_profiles テーブル作成（empires.id への FK あり — 後に作成）。
    op.create_table(
        "role_profiles",
        sa.Column("id", sa.CHAR(32), nullable=False),
        # empires.id への FK（ON DELETE CASCADE）。
        sa.Column("empire_id", sa.CHAR(32), nullable=False),
        # Role StrEnum 値（例: "DEVELOPER" / "REVIEWER"）。
        sa.Column("role", sa.String(32), nullable=False),
        # §確定 G: list[DeliverableTemplateRef] の JSON シリアライズ（DEFAULT '[]'）。
        sa.Column(
            "deliverable_template_refs_json",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.ForeignKeyConstraint(
            ["empire_id"],
            ["empires.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        # §確定 H: 同一 Empire 内で同 Role 値の RoleProfile は 1 件のみ（R1-D）。
        sa.UniqueConstraint("empire_id", "role", name="uq_role_profiles_empire_role"),
    )


def downgrade() -> None:
    # FK を持つ role_profiles を先に削除してから deliverable_templates を削除する。
    op.drop_table("role_profiles")
    op.drop_table("deliverable_templates")
