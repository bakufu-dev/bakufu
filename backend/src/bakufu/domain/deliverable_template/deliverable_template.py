"""DeliverableTemplate 集約ルート。

``docs/features/deliverable-template/domain/detailed-design.md`` に従って実装する。

設計コントラクト:

* **Pre-validate rebuild（確定 A）** — ``create_new_version`` / ``compose`` はいずれも
  ``model_dump(mode='python') → swap → model_validate`` を経由する。
* **Fail Secure（確定 B）** — JSON_SCHEMA / OPENAPI 型で validator が None の場合は
  拒否する。
* **合成時の acceptance_criteria 非継承（確定 B）** — ``compose()`` 呼び出し時は
  acceptance_criteria を空タプルにリセットする。
* **ClassVar DI（確定 C）** — ``_validator`` クラス変数でテスト時に差し替え可能。
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bakufu.domain.deliverable_template.invariant_validators import (
    _validate_acceptance_criteria_no_duplicate_ids,
    _validate_acceptance_criteria_non_empty_descriptions,
    _validate_composition_no_self_ref,
    _validate_schema_format,
    _validate_version_non_negative,
)
from bakufu.domain.exceptions import DeliverableTemplateInvariantViolation
from bakufu.domain.ports.json_schema_validator import AbstractJSONSchemaValidator
from bakufu.domain.value_objects.enums import TemplateType
from bakufu.domain.value_objects.helpers import nfc_strip
from bakufu.domain.value_objects.identifiers import DeliverableTemplateId
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableTemplateRef,
    SemVer,
)

# ---------------------------------------------------------------------------
# メッセージ定数（詳細設計 §MSG）
# ---------------------------------------------------------------------------
_MSG_DT_003_TMPL = (
    "[FAIL] New version must be greater than current version {current}.\n"
    "Next: Use a version greater than {current} (MAJOR.MINOR.PATCH format)."
)


class DeliverableTemplate(BaseModel):
    """成果物テンプレート集約ルート。

    RoleProfile が参照し、Task に紐づく成果物の期待形式を定義する。
    frozen かつ model_validator で 5 つの不変条件を強制する。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    # クラスレベル DI — テスト時に差し替え可能（ClassVar は Pydantic フィールドに含まれない）
    _validator: ClassVar[AbstractJSONSchemaValidator | None] = None

    id: DeliverableTemplateId
    name: str
    description: str
    type: TemplateType
    schema: dict[str, object] | str  # type: ignore[override]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    version: SemVer
    composition: tuple[DeliverableTemplateRef, ...]

    # ---- 事前検証 -------------------------------------------------------
    @field_validator("name", "description", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        """NFC 正規化 + strip を適用する（empire / room と同じパイプライン）。"""
        return nfc_strip(value)

    # ---- 集約レベル不変条件 ---------------------------------------------
    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """5 つの不変条件を決定的順序で検証する。

        順序:
        1. schema format
        2. composition 自己参照なし
        3. version 非負
        4. acceptance_criteria 空説明なし
        5. acceptance_criteria UUID 重複なし
        """
        _validate_schema_format(self.type, self.schema, self.__class__._validator)
        _validate_composition_no_self_ref(self.id, self.composition)
        _validate_version_non_negative(self.version)
        _validate_acceptance_criteria_non_empty_descriptions(self.acceptance_criteria)
        _validate_acceptance_criteria_no_duplicate_ids(self.acceptance_criteria)
        return self

    # ---- 振る舞い（Tell, Don't Ask） ------------------------------------
    def create_new_version(self, new_version: SemVer) -> DeliverableTemplate:
        """``new_version`` を持つ新しい :class:`DeliverableTemplate` を返す。

        新バージョンは現行バージョンより大きくなければならない（タプル比較）。

        Raises:
            DeliverableTemplateInvariantViolation: ``kind='version_not_greater'``
                新バージョンが現行以下の場合。
        """
        current_tuple = (self.version.major, self.version.minor, self.version.patch)
        new_tuple = (new_version.major, new_version.minor, new_version.patch)
        if new_tuple <= current_tuple:
            current_str = str(self.version)
            raise DeliverableTemplateInvariantViolation(
                kind="version_not_greater",
                message=_MSG_DT_003_TMPL.format(current=current_str),
                detail={
                    "current_version": current_str,
                    "requested_version": str(new_version),
                },
            )
        state = self.model_dump(mode="python")
        state["version"] = {
            "major": new_version.major,
            "minor": new_version.minor,
            "patch": new_version.patch,
        }
        return DeliverableTemplate.model_validate(state)

    def compose(self, refs: tuple[DeliverableTemplateRef, ...]) -> DeliverableTemplate:
        """``refs`` を composition に設定した新しい :class:`DeliverableTemplate` を返す。

        確定 B: acceptance_criteria は合成時に継承されないため空タプルにリセットする。

        Raises:
            DeliverableTemplateInvariantViolation: composition に自己参照が含まれる場合。
        """
        state = self.model_dump(mode="python")
        state["composition"] = [
            {
                "template_id": ref.template_id,
                "minimum_version": {
                    "major": ref.minimum_version.major,
                    "minor": ref.minimum_version.minor,
                    "patch": ref.minimum_version.patch,
                },
            }
            for ref in refs
        ]
        state["acceptance_criteria"] = []
        return DeliverableTemplate.model_validate(state)


__all__ = ["DeliverableTemplate"]
