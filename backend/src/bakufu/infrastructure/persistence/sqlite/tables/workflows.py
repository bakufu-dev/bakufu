"""``workflows`` テーブル — Workflow Aggregate ルート行。

3 個のスカラー カラム（``id`` / ``name`` / ``entry_stage_id``）を保持する。
``stages`` と ``transitions`` のコレクションは
:mod:`...tables.workflow_stages` / :mod:`...tables.workflow_transitions` の
関連テーブルに置き、行幅を抑え CASCADE 対象を明確にする。

``entry_stage_id`` は ``workflow_stages.stage_id`` への外部キーを **意図的に
持たない** — ``docs/features/workflow-repository/detailed-design.md`` §確定 J
を参照。自然な FK は循環参照（``workflows`` ↔ ``workflow_stages``）を形成し、
deferred 制約が必要となる。SQLite の ``PRAGMA defer_foreign_keys`` は動作するが、
M5+ の PostgreSQL 移行目標に対する portability を狭めてしまう。Aggregate レベル
の ``_validate_entry_in_stages`` が ``entry_stage_id`` が ``stages`` 内に存在する
ことを既に証明しているため、DB 制約は冗長。

どのカラムにも ``Masked*`` TypeDecorator は付けない。CI 3 層防御（grep ガード +
アーキ テスト + storage.md §逆引き表）はこの不在を登録するため、将来の PR が
カラムをサイレントにシークレット保持の意味へ置き換えることはできない。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import Base, UUIDStr


class WorkflowRow(Base):
    """``workflows`` テーブルの ORM マッピング。"""

    __tablename__ = "workflows"

    id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    entry_stage_id: Mapped[UUID] = mapped_column(UUIDStr, nullable=False)


__all__ = ["WorkflowRow"]
