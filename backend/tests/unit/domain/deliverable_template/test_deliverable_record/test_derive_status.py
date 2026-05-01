"""DeliverableRecord.derive_status テスト（TC-UT-DR-004〜010）。

Issue: #123
設計書: docs/features/deliverable-template/ai-validation/test-design.md §derive_status
対応要件: REQ-DT-008（derive_status / ValidationStatus 導出 §確定A / R1-G）

BUG-DR-001 修正済み: CriterionValidationResult に required フィールドを追加し、
derive_status() が required=True の結果のみを overall status 計算に使用するよう修正。
TC-UT-DR-008 の xfail マーカーを解除した。
"""

from __future__ import annotations

from bakufu.domain.value_objects.enums import ValidationStatus

from tests.factories.deliverable_record import (
    make_criterion_validation_result,
    make_deliverable_record,
)


class TestDeriveStatus:
    """TC-UT-DR-004〜010: ValidationStatus 導出全パターン（§確定A / R1-G）。"""

    def test_all_required_true_passed_returns_passed(self) -> None:
        """TC-UT-DR-004: required=true 全件 PASSED → overall PASSED。

        要件: REQ-DT-008, §確定A, R1-G
        """
        results = (
            make_criterion_validation_result(status=ValidationStatus.PASSED),
            make_criterion_validation_result(status=ValidationStatus.PASSED),
        )
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        derived = record.derive_status(results)
        assert derived.validation_status == ValidationStatus.PASSED

    def test_one_required_true_failed_returns_failed(self) -> None:
        """TC-UT-DR-005: required=true に FAILED 1 件 → overall FAILED。

        要件: REQ-DT-008, §確定A, R1-G
        """
        results = (
            make_criterion_validation_result(status=ValidationStatus.PASSED),
            make_criterion_validation_result(status=ValidationStatus.FAILED),
        )
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        derived = record.derive_status(results)
        assert derived.validation_status == ValidationStatus.FAILED

    def test_uncertain_without_failed_returns_uncertain(self) -> None:
        """TC-UT-DR-006: required=true に UNCERTAIN あり FAILED なし → overall UNCERTAIN。

        要件: REQ-DT-008, §確定A, R1-G
        """
        results = (
            make_criterion_validation_result(status=ValidationStatus.PASSED),
            make_criterion_validation_result(status=ValidationStatus.UNCERTAIN),
        )
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        derived = record.derive_status(results)
        assert derived.validation_status == ValidationStatus.UNCERTAIN

    def test_empty_results_returns_passed(self) -> None:
        """TC-UT-DR-007: criterion_results=()（空）→ overall PASSED（境界値）。

        要件: REQ-DT-008, §確定A
        """
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        derived = record.derive_status(())
        assert derived.validation_status == ValidationStatus.PASSED

    def test_only_required_false_failed_returns_passed(self) -> None:
        """TC-UT-DR-008: required=false のみ FAILED → overall PASSED（R1-G 仕様）。

        要件: REQ-DT-008, §確定A, R1-G
        BUG-DR-001 修正後: CriterionValidationResult に required フィールドが追加され、
        derive_status() が required=True の結果のみを overall status 計算に使用するため、
        required=false の FAILED は overall status に影響しない（PASSED を返す）。
        """
        # required=false の criterion の結果として FAILED を渡す。
        results = (
            make_criterion_validation_result(status=ValidationStatus.FAILED, required=False),
        )
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        derived = record.derive_status(results)
        # §確定 R1-G: required=false の FAIL は validation_status に影響しない → PASSED。
        assert derived.validation_status == ValidationStatus.PASSED

    def test_required_true_failed_and_required_false_uncertain_returns_failed(
        self,
    ) -> None:
        """TC-UT-DR-009: required=true FAILED + required=false UNCERTAIN → overall FAILED。

        要件: REQ-DT-008, §確定A, R1-G
        """
        results = (
            make_criterion_validation_result(status=ValidationStatus.FAILED),
            make_criterion_validation_result(status=ValidationStatus.UNCERTAIN),
        )
        record = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        derived = record.derive_status(results)
        assert derived.validation_status == ValidationStatus.FAILED

    def test_derive_status_returns_new_instance(self) -> None:
        """TC-UT-DR-010: derive_status は新インスタンスを返す（純粋関数）。

        要件: REQ-DT-008
        元 record の validation_status は変化しない（PENDING のまま）。
        """
        results = (make_criterion_validation_result(status=ValidationStatus.PASSED),)
        original = make_deliverable_record(
            validation_status=ValidationStatus.PENDING,
            criterion_results=(),
        )
        derived = original.derive_status(results)
        # 新インスタンスであること
        assert derived is not original
        # 元 record は変化していないこと
        assert original.validation_status == ValidationStatus.PENDING
        # 派生 record は PASSED
        assert derived.validation_status == ValidationStatus.PASSED
