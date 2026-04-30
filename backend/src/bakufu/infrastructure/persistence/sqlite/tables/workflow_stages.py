"""``workflow_stages`` テーブル — Workflow ↔ Stage 子行。

:class:`bakufu.domain.workflow.entities.Stage` の値を Workflow Aggregate の関連
テーブルとして保存する。``stage_id`` は意図的に ``workflows.entry_stage_id`` への
外部キーには **しない**（``docs/features/workflow-repository/detailed-design.md``
§確定 J）。Aggregate レベルの ``_validate_entry_in_stages`` が既に参照不変条件を
強制している。

カスケード: Workflow 行の削除はその stage 行を消去する（``ON DELETE CASCADE``）。
``UNIQUE(workflow_id, stage_id)`` 制約は
:func:`bakufu.domain.workflow.dag_validators._validate_stage_id_unique` を行レベル
でミラーする。

カラム別シークレット ハンドリング（§確定 H + M2 persistence foundation 申し送り #6）:

* ``notify_channels_json`` は :class:`MaskedJSONEncoded` カラム。
  ``process_bind_param`` フックがネストされた各 ``target`` フィールドを
  :func:`bakufu.infrastructure.security.masking.mask_in` 経由でルーティングする
  ため、Discord webhook の ``token`` セグメントが平文でディスクに到達することはない。
  多層防御: ``NotifyChannel.field_serializer(when_used='json')`` も
  ``model_dump(mode='json')`` 時にマスクするが、TypeDecorator が ORM と Core
  ``insert(table).values(...)`` の両経路で発火する *ゲート* となる（BUG-PF-001
  コントラクト）。
* ``completion_policy_json`` は通常の :class:`JSONEncoded` カラム — VO は
  Schneier 申し送り #6 の 6 カテゴリ スキャンに照らしてもシークレット保持値を
  持たないため、``MaskedJSONEncoded`` だと **過剰マスキング**（詳細設計 §確定 I
  で禁止）になる。
* ``required_deliverables_json`` は通常の :class:`JSONEncoded` カラム（Issue #117）。
  ``DeliverableRequirement`` は ``template_ref``（UUID + SemVer）と ``optional``（bool）
  のみを保持し、シークレット値を含まないため ``MaskedJSONEncoded`` だと過剰マスキング。
* 残りのカラムは UUID / enum を保持し、6 つのマスキング カテゴリには該当しない。

CI 3 層防御は本テーブル上の ``MaskedJSONEncoded`` カラム数を厳密に 1 個に固定する
（``notify_channels_json`` への positive コントラクト、その他全カラムは no-mask）。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bakufu.infrastructure.persistence.sqlite.base import (
    Base,
    JSONEncoded,
    MaskedJSONEncoded,
    UUIDStr,
)


class WorkflowStageRow(Base):
    """``workflow_stages`` テーブルの ORM マッピング。"""

    __tablename__ = "workflow_stages"

    workflow_id: Mapped[UUID] = mapped_column(
        UUIDStr,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    stage_id: Mapped[UUID] = mapped_column(UUIDStr, primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    roles_csv: Mapped[str] = mapped_column(String(255), nullable=False)
    # §確定 C（Issue #117）: json.loads → list[dict] →
    # DeliverableRequirement.model_validate 経由で復元。
    # DEFAULT '[]' は 0011_stage_required_deliverables.py の server_default で強制。
    required_deliverables_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)
    completion_policy_json: Mapped[Any] = mapped_column(JSONEncoded, nullable=False)
    # デフォルト ``[]`` は 0003_workflow_aggregate.py の ``server_default`` で SQL
    # レベルにおいて強制される。Repository が常に明示的なリストを渡すため、
    # ORM 側のデフォルト指定は不要。
    notify_channels_json: Mapped[Any] = mapped_column(MaskedJSONEncoded, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "stage_id",
            name="uq_workflow_stages_pair",
        ),
    )


__all__ = ["WorkflowStageRow"]
