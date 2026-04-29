"""Workflow 内部 Entity: :class:`Stage` と :class:`Transition`。

両者は Pydantic v2 frozen モデル。設計ドキュメントが指摘する *責務* 境界を
ファイル レベル境界に反映するため :mod:`bakufu.domain.workflow.workflow` から
分離して配置する:

* Entity は **自己** 不変条件（Stage の ``required_role`` 非空および
  ``EXTERNAL_REVIEW`` notify_channels ルール）を所有する。これらは entity が
  単独で構築された場合（preset 定義、ファクトリ）でも発火するため、Workflow
  が値を目にする前に違反を捕捉できる。
* Aggregate Root は **コレクション** 不変条件（DAG、一意性、容量）を所有する。
  それらは :mod:`bakufu.domain.workflow.dag_validators` の純粋関数として実装
  されており、ファイル レベル境界が「Stage 自己検証は Aggregate ヘルパとコード
  を共有しない」を強制する — Confirmation F twin-defense の物理的根拠。
"""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import StageInvariantViolation
from bakufu.domain.value_objects import (
    CompletionPolicy,
    NotifyChannel,
    Role,
    StageId,
    StageKind,
    TransitionCondition,
    TransitionId,
    nfc_strip,
)


class Stage(BaseModel):
    """``model_validator`` で **自己** 不変条件をチェックする Workflow Stage。

    自己チェックは :class:`StageInvariantViolation` を送出するため、Workflow の
    外で構築された Stage（例 preset 定義、ファクトリ）でも違反が早期に表面化する。
    Workflow Aggregate は後で同じ条件を
    :func:`bakufu.domain.workflow.dag_validators._validate_external_review_notify`
    と ``_validate_required_role_non_empty`` で再検証する — この二重経路は
    設計通り（Confirmation F twin-defense）。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: StageId
    name: str = Field(min_length=1, max_length=80)
    kind: StageKind
    required_role: frozenset[Role]
    deliverable_template: str = Field(default="", max_length=10_000)
    completion_policy: CompletionPolicy
    notify_channels: list[NotifyChannel] = []

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_self_invariants(self) -> Self:
        # REQ-WF-007-① required_role 非空（MSG-WF-007）。
        if not self.required_role:
            raise StageInvariantViolation(
                kind="empty_required_role",
                message=f"[FAIL] Stage {self.id} required_role must not be empty",
                detail={"stage_id": str(self.id)},
            )
        # REQ-WF-007-② EXTERNAL_REVIEW は notify_channels を宣言しなければならない
        # （MSG-WF-006）。
        if self.kind is StageKind.EXTERNAL_REVIEW and not self.notify_channels:
            raise StageInvariantViolation(
                kind="missing_notify",
                message=(
                    f"[FAIL] EXTERNAL_REVIEW stage {self.id} must have at least one notify_channel"
                ),
                detail={"stage_id": str(self.id)},
            )
        return self


class Transition(BaseModel):
    """2 つの Stage 間の有向エッジ。参照整合性は Aggregate の責務。

    Transition は Pydantic フィールド レベルの型強制を超える自己不変条件を
    持たない: その意味は周囲の ``stages`` コレクションに依存するため、構造
    検証は :func:`bakufu.domain.workflow.dag_validators._validate_transition_refs`
    および ``_validate_transition_determinism`` に置く。
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: TransitionId
    from_stage_id: StageId
    to_stage_id: StageId
    condition: TransitionCondition
    label: str = Field(default="", max_length=80)


__all__ = [
    "Stage",
    "Transition",
]
