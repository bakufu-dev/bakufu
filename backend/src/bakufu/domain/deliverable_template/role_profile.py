"""RoleProfile 集約ルート。

``docs/features/deliverable-template/domain/detailed-design.md`` に従って実装する。

RoleProfile は Role と DeliverableTemplateRef のコレクションを保持し、
Empire スコープ内で特定のロールに期待される成果物テンプレートを管理する。

設計コントラクト:

* **Pre-validate rebuild（確定 A）** — ``add_template_ref`` / ``remove_template_ref`` は
  いずれも ``model_dump(mode='python') → swap → model_validate`` を経由する。
* **重複防止（不変条件 ``_validate_no_duplicate_refs``）** — model_validator が
  単一の不変条件チェックポイントとなる。``add_template_ref`` は事前ループを持たず、
  ``model_validate`` 経由で ``_validate_no_duplicate_refs`` に委譲する。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from bakufu.domain.deliverable_template.invariant_validators import (
    _MSG_DT_005_TMPL,
    _validate_no_duplicate_refs,
)
from bakufu.domain.exceptions import RoleProfileInvariantViolation
from bakufu.domain.value_objects.enums import Role
from bakufu.domain.value_objects.identifiers import (
    DeliverableTemplateId,
    EmpireId,
    RoleProfileId,
)
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableTemplateRef,
)

if TYPE_CHECKING:
    from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate


class RoleProfile(BaseModel):
    """Role に紐づく DeliverableTemplate 参照コレクションを保持する集約ルート。

    frozen かつ model_validator で重複参照の不変条件を強制する。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    id: RoleProfileId
    empire_id: EmpireId
    role: Role
    deliverable_template_refs: tuple[DeliverableTemplateRef, ...]

    # ---- 集約レベル不変条件 ---------------------------------------------
    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """重複参照がないことを検証する。"""
        _validate_no_duplicate_refs(self.deliverable_template_refs)
        return self

    # ---- 振る舞い（Tell, Don't Ask） ------------------------------------
    def add_template_ref(self, ref: DeliverableTemplateRef) -> RoleProfile:
        """``ref`` を deliverable_template_refs に追加した新しい :class:`RoleProfile` を返す。

        重複チェックは ``model_validate`` → ``_check_invariants`` →
        ``_validate_no_duplicate_refs`` に委譲する（§確定 A: 単一不変条件ポイント）。

        Raises:
            RoleProfileInvariantViolation: ``kind='duplicate_template_ref'``
                ``ref.template_id`` が既に存在する場合。
        """
        state = self.model_dump(mode="python")
        state["deliverable_template_refs"] = [
            *[
                {
                    "template_id": r.template_id,
                    "minimum_version": {
                        "major": r.minimum_version.major,
                        "minor": r.minimum_version.minor,
                        "patch": r.minimum_version.patch,
                    },
                }
                for r in self.deliverable_template_refs
            ],
            {
                "template_id": ref.template_id,
                "minimum_version": {
                    "major": ref.minimum_version.major,
                    "minor": ref.minimum_version.minor,
                    "patch": ref.minimum_version.patch,
                },
            },
        ]
        return RoleProfile.model_validate(state)

    def remove_template_ref(self, template_id: DeliverableTemplateId) -> RoleProfile:
        """``template_id`` に対応する ref を除いた新しい :class:`RoleProfile` を返す。

        一致する ref が見つからない場合は Fail Fast する。

        「存在確認」は **事前条件チェック**（呼び出し元の入力検証）であり、
        不変条件ではない。削除後の状態は常に有効（重複なし）であるため
        ``model_validate`` 後の ``_validate_no_duplicate_refs`` は通過する。
        そのため、ここでは事前条件違反を直接 raise する。

        Raises:
            RoleProfileInvariantViolation: ``kind='template_ref_not_found'``
                ``template_id`` が存在しない場合。
        """
        found = any(r.template_id == template_id for r in self.deliverable_template_refs)
        if not found:
            raise RoleProfileInvariantViolation(
                kind="template_ref_not_found",
                message=_MSG_DT_005_TMPL.format(template_id=template_id),
                detail={"template_id": str(template_id)},
            )
        state = self.model_dump(mode="python")
        state["deliverable_template_refs"] = [
            {
                "template_id": r.template_id,
                "minimum_version": {
                    "major": r.minimum_version.major,
                    "minor": r.minimum_version.minor,
                    "patch": r.minimum_version.patch,
                },
            }
            for r in self.deliverable_template_refs
            if r.template_id != template_id
        ]
        return RoleProfile.model_validate(state)

    def get_all_acceptance_criteria(
        self,
        template_lookup: Mapping[DeliverableTemplateId, DeliverableTemplate],
    ) -> list[AcceptanceCriterion]:
        """全 DeliverableTemplateRef の acceptance_criteria を収集して返す。

        重複 criterion.id は先頭出現を保持して除去し、
        required=True のものを先に、required=False のものを後に並べる。

        Args:
            template_lookup: DeliverableTemplateId → DeliverableTemplate のマッピング。
                refs に対応するテンプレートが含まれている必要がある（KeyError は
                呼び出し元の責務）。

        Returns:
            重複除去・ソート済みの :class:`AcceptanceCriterion` リスト。
        """
        seen_ids: set[UUID] = set()
        all_criteria: list[AcceptanceCriterion] = []

        for ref in self.deliverable_template_refs:
            template: DeliverableTemplate = template_lookup[ref.template_id]
            for criterion in template.acceptance_criteria:
                if criterion.id not in seen_ids:
                    seen_ids.add(criterion.id)
                    all_criteria.append(criterion)

        # required=True を先に、required=False を後に（安定ソート）
        return sorted(all_criteria, key=lambda c: (not c.required,))


__all__ = ["RoleProfile"]
