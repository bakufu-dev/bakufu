"""DeliverableRecord 機能の Value Object 定義。

CriterionValidationResult — LLM による単一 AcceptanceCriterion 評価結果 VO。

設計書: docs/features/deliverable-template/domain/detailed-design.md §VO: CriterionValidationResult
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from bakufu.domain.value_objects.enums import ValidationStatus


class CriterionValidationResult(BaseModel):
    """LLM による単一 AcceptanceCriterion 評価結果 VO（不変）。

    Attributes:
        criterion_id: 対応する AcceptanceCriterion の UUID。
        status: LLM による判定結果（PASSED / FAILED / UNCERTAIN。PENDING は不可）。
        reason: LLM が提供する判定根拠（0〜1000 文字）。
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    criterion_id: UUID
    status: ValidationStatus
    reason: str = Field(max_length=1000)


__all__ = ["CriterionValidationResult"]
