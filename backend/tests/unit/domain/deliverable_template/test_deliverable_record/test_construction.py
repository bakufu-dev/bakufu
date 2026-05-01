"""DeliverableRecord 構築テスト（TC-UT-DR-001〜003）。

Issue: #123
設計書: docs/features/deliverable-template/ai-validation/test-design.md §構築
対応要件: REQ-DT-007（DeliverableRecord 構築）
"""

from __future__ import annotations

import pytest

from bakufu.domain.exceptions.deliverable_template import DeliverableRecordInvariantViolation
from bakufu.domain.value_objects.enums import ValidationStatus

from tests.factories.deliverable_record import (
    make_criterion_validation_result,
    make_deliverable_record,
)


class TestDeliverableRecordConstruction:
    """TC-UT-DR-001〜003: DeliverableRecord 構築テスト。"""

    def test_pending_record_construction_succeeds(self) -> None:
        """TC-UT-DR-001: PENDING + criterion_results 空で正常構築。

        要件: REQ-DT-007
        """
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        assert record.validation_status == ValidationStatus.PENDING
        assert record.criterion_results == ()
        assert record.validated_at is None

    def test_passed_with_criterion_results_construction_succeeds(self) -> None:
        """TC-UT-DR-002: PASSED + criterion_results 非空で正常構築。

        要件: REQ-DT-007
        """
        result = make_criterion_validation_result(status=ValidationStatus.PASSED)
        record = make_deliverable_record(
            validation_status=ValidationStatus.PASSED,
            criterion_results=(result,),
        )
        assert record.validation_status == ValidationStatus.PASSED
        assert len(record.criterion_results) == 1

    def test_pending_with_nonempty_criterion_results_raises_invariant_violation(
        self,
    ) -> None:
        """TC-UT-DR-003: PENDING かつ criterion_results 非空 → DeliverableRecordInvariantViolation。

        要件: REQ-DT-007
        """
        result = make_criterion_validation_result(status=ValidationStatus.PASSED)
        with pytest.raises(DeliverableRecordInvariantViolation) as exc_info:
            make_deliverable_record(
                validation_status=ValidationStatus.PENDING,
                criterion_results=(result,),
            )
        assert exc_info.value.kind == "invalid_validation_state"
