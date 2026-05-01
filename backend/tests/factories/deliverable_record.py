"""DeliverableRecord / CriterionValidationResult ファクトリ群。

``docs/features/deliverable-template/ai-validation/test-design.md`` §factory 設計方針 準拠。
WeakValueDictionary による _meta.synthetic レジストリ、
本番コンストラクタ経由での構築。

本モジュールは本番コードから import してはならない。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from pydantic import BaseModel

from bakufu.domain.deliverable_record.deliverable_record import DeliverableRecord
from bakufu.domain.value_objects.deliverable_record_vos import CriterionValidationResult
from bakufu.domain.value_objects.enums import ValidationStatus
from bakufu.domain.value_objects.identifiers import (
    AgentId,
    DeliverableId,
    DeliverableRecordId,
    TaskId,
)
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableTemplateRef,
    SemVer,
)

# モジュールスコープのレジストリ（WeakValueDictionary で GC 圧中立）
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, object] = WeakValueDictionary()


def is_synthetic(instance: object) -> bool:
    """``instance`` がファクトリ由来なら ``True`` を返す（ID ベース判定）。"""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: object) -> None:
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# CriterionValidationResult ファクトリ
# ---------------------------------------------------------------------------
def make_criterion_validation_result(
    *,
    criterion_id: UUID | None = None,
    status: ValidationStatus = ValidationStatus.PASSED,
    reason: str = "合成評価理由",
) -> CriterionValidationResult:
    """妥当な CriterionValidationResult を構築する（_meta.synthetic: True）。"""
    result = CriterionValidationResult(
        criterion_id=criterion_id or uuid4(),
        status=status,
        reason=reason,
    )
    _register(result)
    return result


# ---------------------------------------------------------------------------
# DeliverableRecord ファクトリ
# ---------------------------------------------------------------------------
def make_deliverable_template_ref(
    *,
    template_id: UUID | None = None,
    minimum_version: SemVer | None = None,
) -> DeliverableTemplateRef:
    """妥当な DeliverableTemplateRef を構築する。"""
    ref = DeliverableTemplateRef(
        template_id=template_id or uuid4(),
        minimum_version=minimum_version or SemVer(major=1, minor=0, patch=0),
    )
    _register(ref)
    return ref


def make_deliverable_record(
    *,
    record_id: DeliverableRecordId | None = None,
    deliverable_id: DeliverableId | None = None,
    template_ref: DeliverableTemplateRef | None = None,
    content: str = "テスト成果物テキスト",
    task_id: TaskId | None = None,
    validation_status: ValidationStatus = ValidationStatus.PENDING,
    criterion_results: tuple[CriterionValidationResult, ...] = (),
    produced_by: AgentId | None = None,
    created_at: datetime | None = None,
    validated_at: datetime | None = None,
) -> DeliverableRecord:
    """妥当な DeliverableRecord を構築する（デフォルト: PENDING 初期状態）。

    _meta.synthetic: True（WeakValueDictionary 登録済み）。
    """
    record = DeliverableRecord(
        id=record_id or uuid4(),
        deliverable_id=deliverable_id or uuid4(),
        template_ref=template_ref or make_deliverable_template_ref(),
        content=content,
        task_id=task_id or uuid4(),
        validation_status=validation_status,
        criterion_results=criterion_results,
        produced_by=produced_by,
        created_at=created_at or datetime.now(UTC),
        validated_at=validated_at,
    )
    _register(record)
    return record


# ---------------------------------------------------------------------------
# AcceptanceCriterion ファクトリ
# ---------------------------------------------------------------------------
def make_acceptance_criterion(
    *,
    criterion_id: UUID | None = None,
    description: str = "満たすべき条件",
    required: bool = True,
) -> AcceptanceCriterion:
    """妥当な AcceptanceCriterion を構築する（_meta.synthetic: True）。"""
    ac = AcceptanceCriterion(
        id=criterion_id or uuid4(),
        description=description,
        required=required,
    )
    _register(ac)
    return ac


__all__ = [
    "is_synthetic",
    "make_acceptance_criterion",
    "make_criterion_validation_result",
    "make_deliverable_record",
    "make_deliverable_template_ref",
]
