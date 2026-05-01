"""DeliverableRecord 集約ルート。

LLM による受入基準評価の結果を保持する Aggregate。
derive_status() は純粋関数として実装（外部 I/O なし）。

設計書: docs/features/deliverable-template/domain/detailed-design.md
§Aggregate Root: DeliverableRecord
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, model_validator

from bakufu.domain.exceptions.deliverable_template import DeliverableRecordInvariantViolation
from bakufu.domain.value_objects.deliverable_record_vos import CriterionValidationResult
from bakufu.domain.value_objects.enums import ValidationStatus
from bakufu.domain.value_objects.identifiers import (
    AgentId,
    DeliverableId,
    DeliverableRecordId,
    TaskId,
)
from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef

_MSG_INVALID_STATE = (
    "[FAIL] DeliverableRecord validation_status is inconsistent with criterion_results.\n"
    "Next: Use derive_status() to set status, or ensure criterion_results match status."
)


class DeliverableRecord(BaseModel):
    """LLM 受入基準評価の集約ルート（§確定 R1-G）。

    frozen=True により不変性を保証する。
    derive_status() で新インスタンスを生成（pre-validate 方式）。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    id: DeliverableRecordId
    deliverable_id: DeliverableId
    template_ref: DeliverableTemplateRef
    content: str
    task_id: TaskId
    validation_status: ValidationStatus = ValidationStatus.PENDING
    criterion_results: tuple[CriterionValidationResult, ...] = ()
    produced_by: AgentId | None = None
    created_at: datetime
    validated_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_status_consistency(self) -> DeliverableRecord:
        """validation_status と criterion_results の整合性を検証する。

        ① PENDING → criterion_results が空であること。
        ② FAILED / UNCERTAIN → criterion_results が空でないこと。
        ③ PASSED → 制約なし（criteria が空の場合は criterion_results も空で PASSED が合法）。
        """
        status = self.validation_status
        results = self.criterion_results
        if status == ValidationStatus.PENDING and results:
            raise DeliverableRecordInvariantViolation(
                kind="invalid_validation_state",
                message=_MSG_INVALID_STATE,
            )
        if status in (ValidationStatus.FAILED, ValidationStatus.UNCERTAIN) and not results:
            raise DeliverableRecordInvariantViolation(
                kind="invalid_validation_state",
                message=_MSG_INVALID_STATE,
            )
        return self

    def derive_status(
        self,
        criterion_results: tuple[CriterionValidationResult, ...],
    ) -> DeliverableRecord:
        """criterion_results から overall status を導出した新インスタンスを返す（純粋関数）。

        §確定 R1-G 導出規則:
        1. required=True の criterion は template_ref から取得できないため、
           criterion_results の全結果を対象に status を導出する。
        2. FAILED が 1 件以上 → FAILED
        3. UNCERTAIN が 1 件以上かつ FAILED が 0 件 → UNCERTAIN
        4. 全件 PASSED または results が空 → PASSED

        Args:
            criterion_results: 評価済み CriterionValidationResult のタプル。

        Returns:
            validation_status / criterion_results / validated_at を更新した新インスタンス。
        """
        if not criterion_results:
            overall = ValidationStatus.PASSED
        else:
            statuses = {r.status for r in criterion_results}
            if ValidationStatus.FAILED in statuses:
                overall = ValidationStatus.FAILED
            elif ValidationStatus.UNCERTAIN in statuses:
                overall = ValidationStatus.UNCERTAIN
            else:
                overall = ValidationStatus.PASSED

        state = self.model_dump(mode="python")
        state["validation_status"] = overall
        state["criterion_results"] = [
            {
                "criterion_id": r.criterion_id,
                "status": r.status,
                "reason": r.reason,
            }
            for r in criterion_results
        ]
        state["validated_at"] = datetime.now(UTC)
        return DeliverableRecord.model_validate(state)


__all__ = ["DeliverableRecord"]
