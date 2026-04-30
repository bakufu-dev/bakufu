"""DeliverableTemplate 不変条件テスト。

TC-UT-DT-008〜016c: 5 不変条件 helper 全種
TC-UT-MSG-001〜005: MSG 2 行構造 + Next: hint 物理保証
TC-UT-A09-001〜003: detail フィールドホワイトリスト（A09）

Issue #115 / docs/features/deliverable-template/domain/test-design.md §不変条件
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.deliverable_template.deliverable_template import DeliverableTemplate
from bakufu.domain.exceptions import (
    DeliverableTemplateInvariantViolation,
    RoleProfileInvariantViolation,
)
from bakufu.domain.value_objects.enums import TemplateType
from pydantic import ValidationError

from tests.factories.deliverable_template import (
    InvalidStubValidator,
    ValidStubValidator,
    make_acceptance_criterion,
    make_deliverable_template,
    make_deliverable_template_ref,
    make_role_profile,
    make_semver,
)


# ---------------------------------------------------------------------------
# TC-UT-DT-008: _validate_schema_format — JSON_SCHEMA + str（非 dict）
# ---------------------------------------------------------------------------
class TestSchemaFormatJsonSchemaStr:
    """TC-UT-DT-008: type=JSON_SCHEMA, schema=str → schema_format_invalid。"""

    def setup_method(self) -> None:
        DeliverableTemplate._validator = ValidStubValidator()  # type: ignore[reportPrivateUsage]

    def teardown_method(self) -> None:
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]

    def test_json_schema_with_str_schema_raises(self) -> None:
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.JSON_SCHEMA,
                schema="not a dict",
            )
        assert exc_info.value.kind == "schema_format_invalid"


# ---------------------------------------------------------------------------
# TC-UT-DT-009: _validate_schema_format — JSON_SCHEMA + 無効 dict (stub)
# ---------------------------------------------------------------------------
class TestSchemaFormatJsonSchemaInvalidDict:
    """TC-UT-DT-009: type=JSON_SCHEMA, 無効な dict + InvalidStub → schema_format_invalid。"""

    def setup_method(self) -> None:
        DeliverableTemplate._validator = InvalidStubValidator()  # type: ignore[reportPrivateUsage]

    def teardown_method(self) -> None:
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]

    def test_json_schema_with_invalid_dict_raises(self) -> None:
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.JSON_SCHEMA,
                schema={"invalid_key": True},
            )
        assert exc_info.value.kind == "schema_format_invalid"


# ---------------------------------------------------------------------------
# TC-UT-DT-010: _validate_schema_format — MARKDOWN + dict（str 期待違反）
# ---------------------------------------------------------------------------
class TestSchemaFormatMarkdownDict:
    """TC-UT-DT-010: type=MARKDOWN, schema=dict → schema_format_invalid。"""

    def test_markdown_with_dict_schema_raises(self) -> None:
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.MARKDOWN,
                schema={"key": "value"},
            )
        assert exc_info.value.kind == "schema_format_invalid"


# ---------------------------------------------------------------------------
# TC-UT-DT-011: §確定 C — AbstractJSONSchemaValidator DI 可能
# ---------------------------------------------------------------------------
class TestValidationPortDI:
    """TC-UT-DT-011: valid スタブを DI して JSON_SCHEMA 構築成功。スタブ差し替えが機能する。"""

    def setup_method(self) -> None:
        DeliverableTemplate._validator = ValidStubValidator()  # type: ignore[reportPrivateUsage]

    def teardown_method(self) -> None:
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]

    def test_valid_stub_allows_json_schema_construction(self) -> None:
        dt = make_deliverable_template(
            type_=TemplateType.JSON_SCHEMA,
            schema={"type": "object"},
        )
        assert dt.type == TemplateType.JSON_SCHEMA

    def test_none_validator_fails_secure_for_json_schema(self) -> None:
        """validator=None 時は Fail Secure で schema_format_invalid。"""
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.JSON_SCHEMA,
                schema={"type": "object"},
            )
        assert exc_info.value.kind == "schema_format_invalid"

    def test_invalid_stub_raises_schema_format_invalid(self) -> None:
        DeliverableTemplate._validator = InvalidStubValidator()  # type: ignore[reportPrivateUsage]
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.JSON_SCHEMA,
                schema={"type": "object"},
            )
        assert exc_info.value.kind == "schema_format_invalid"


# ---------------------------------------------------------------------------
# TC-UT-DT-012: _validate_composition_no_self_ref — 自己 ID
# ---------------------------------------------------------------------------
class TestCompositionSelfRef:
    """TC-UT-DT-012: composition に自己 ID → composition_self_ref。"""

    def test_self_reference_in_composition_raises(self) -> None:
        self_id = uuid4()
        self_ref = make_deliverable_template_ref(template_id=self_id)
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                template_id=self_id,
                composition=(self_ref,),
            )
        assert exc_info.value.kind == "composition_self_ref"


# ---------------------------------------------------------------------------
# TC-UT-DT-013: _validate_composition_no_self_ref — 空 tuple
# ---------------------------------------------------------------------------
class TestCompositionEmpty:
    """TC-UT-DT-013: composition=() → 構築成功。"""

    def test_empty_composition_succeeds(self) -> None:
        dt = make_deliverable_template(composition=())
        assert dt.composition == ()


# ---------------------------------------------------------------------------
# TC-UT-DT-014: _validate_composition_no_self_ref — 他テンプレートへの ref
# ---------------------------------------------------------------------------
class TestCompositionNonSelfRef:
    """TC-UT-DT-014: composition に他テンプレート ID のみ → 構築成功。"""

    def test_non_self_ref_composition_succeeds(self) -> None:
        other_ref = make_deliverable_template_ref()
        dt = make_deliverable_template(composition=(other_ref,))
        assert len(dt.composition) == 1


# ---------------------------------------------------------------------------
# TC-UT-DT-015: _validate_version_non_negative — 負の major
# ---------------------------------------------------------------------------
class TestVersionNonNegative:
    """TC-UT-DT-015: SemVer(major=-1) → Pydantic ValidationError（ge=0 制約）。"""

    def test_negative_major_raises_validation_error(self) -> None:
        with pytest.raises((ValidationError, DeliverableTemplateInvariantViolation)):
            make_deliverable_template(version=make_semver(major=-1))

    def test_negative_minor_raises(self) -> None:
        with pytest.raises((ValidationError, DeliverableTemplateInvariantViolation)):
            make_deliverable_template(version=make_semver(minor=-1))

    def test_negative_patch_raises(self) -> None:
        with pytest.raises((ValidationError, DeliverableTemplateInvariantViolation)):
            make_deliverable_template(version=make_semver(patch=-1))


# ---------------------------------------------------------------------------
# TC-UT-DT-016: _validate_acceptance_criteria_non_empty_descriptions
# ---------------------------------------------------------------------------
class TestAcceptanceCriteriaEmptyDescription:
    """TC-UT-DT-016: AcceptanceCriterion.description='' → acceptance_criteria_empty_description。"""

    def test_empty_description_raises(self) -> None:
        """空文字列の description は Pydantic か domain validator が弾く。"""
        with pytest.raises((ValidationError, DeliverableTemplateInvariantViolation)):
            make_deliverable_template(
                acceptance_criteria=(make_acceptance_criterion(description=""),),
            )

    def test_empty_acceptance_criteria_tuple_succeeds(self) -> None:
        """TC-UT-DT-016b: acceptance_criteria=() → 構築成功（0 件は許容）。"""
        dt = make_deliverable_template(acceptance_criteria=())
        assert dt.acceptance_criteria == ()


# ---------------------------------------------------------------------------
# TC-UT-DT-016c: _validate_acceptance_criteria_no_duplicate_ids
# ---------------------------------------------------------------------------
class TestAcceptanceCriteriaNoDuplicateIds:
    """TC-UT-DT-016c: acceptance_criteria に同一 UUID → acceptance_criteria_duplicate_id。"""

    def test_duplicate_criterion_id_raises(self) -> None:
        shared_id = uuid4()
        ac1 = make_acceptance_criterion(criterion_id=shared_id, description="基準1")
        ac2 = make_acceptance_criterion(criterion_id=shared_id, description="基準2")
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(acceptance_criteria=(ac1, ac2))
        assert exc_info.value.kind == "acceptance_criteria_duplicate_id"

    def test_unique_criterion_ids_succeed(self) -> None:
        ac1 = make_acceptance_criterion(description="基準1")
        ac2 = make_acceptance_criterion(description="基準2")
        dt = make_deliverable_template(acceptance_criteria=(ac1, ac2))
        assert len(dt.acceptance_criteria) == 2


# ---------------------------------------------------------------------------
# TC-UT-MSG-001〜005: MSG 2 行構造 + Next: hint 物理保証
# ---------------------------------------------------------------------------
class TestMsgNextHint:
    """TC-UT-MSG-001〜005: 全 5 MSG-DT で "[FAIL]" + "Next:" の 2 行構造を CI 強制。"""

    def setup_method(self) -> None:
        DeliverableTemplate._validator = InvalidStubValidator()  # type: ignore[reportPrivateUsage]

    def teardown_method(self) -> None:
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]

    def test_msg_dt_001_schema_format_invalid_has_next(self) -> None:
        """TC-UT-MSG-001: MSG-DT-001 (schema_format_invalid) に Next: あり。"""
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.JSON_SCHEMA,
                schema={"type": "object"},
            )
        msg = str(exc_info.value)
        assert "[FAIL]" in msg
        assert "Next:" in msg

    def test_msg_dt_002_composition_self_ref_has_next(self) -> None:
        """TC-UT-MSG-002: MSG-DT-002 (composition_self_ref) に Next: あり。"""
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]  # MARKDOWN OK
        self_id = uuid4()
        self_ref = make_deliverable_template_ref(template_id=self_id)
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                template_id=self_id,
                composition=(self_ref,),
            )
        msg = str(exc_info.value)
        assert "[FAIL]" in msg
        assert "Next:" in msg
        assert "self-referential" in msg

    def test_msg_dt_003_version_not_greater_has_next(self) -> None:
        """TC-UT-MSG-003: MSG-DT-003 (version_not_greater) に Next: あり。
        current 文字列が含まれる。"""
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]
        dt = make_deliverable_template(version=make_semver(major=1, minor=0, patch=0))
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            dt.create_new_version(make_semver(major=0, minor=9, patch=0))
        msg = str(exc_info.value)
        assert "[FAIL]" in msg
        assert "Next:" in msg
        assert "1.0.0" in msg  # current version が含まれる

    def test_msg_dt_004_duplicate_template_ref_has_next(self) -> None:
        """TC-UT-MSG-004: MSG-DT-004 (duplicate_template_ref) に Next: あり。"""
        ref_a = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref_a,))
        with pytest.raises(RoleProfileInvariantViolation) as exc_info:
            rp.add_template_ref(make_deliverable_template_ref(template_id=ref_a.template_id))
        msg = str(exc_info.value)
        assert "[FAIL]" in msg
        assert "Next:" in msg
        assert str(ref_a.template_id) in msg

    def test_msg_dt_005_template_ref_not_found_has_next(self) -> None:
        """TC-UT-MSG-005: MSG-DT-005 (template_ref_not_found) に Next: あり。"""
        rp = make_role_profile()
        non_existent_id = uuid4()
        with pytest.raises(RoleProfileInvariantViolation) as exc_info:
            rp.remove_template_ref(non_existent_id)
        msg = str(exc_info.value)
        assert "[FAIL]" in msg
        assert "Next:" in msg
        assert str(non_existent_id) in msg


# ---------------------------------------------------------------------------
# TC-UT-A09-001〜003: detail フィールドホワイトリスト（A09）
# ---------------------------------------------------------------------------
class TestA09DetailWhitelist:
    """TC-UT-A09-001〜003: 例外の detail フィールドに description/schema 本文が混入しない。"""

    def test_a09_001_schema_format_invalid_detail_no_schema_content(self) -> None:
        """TC-UT-A09-001: schema_format_invalid の detail に schema 本文が含まれない。"""
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.MARKDOWN,
                schema={"secret": "SUPER_SECRET_API_KEY_12345"},
            )
        detail = exc_info.value.detail
        # detail には schema 型名のみ（schema 本文は含まない）
        assert "SUPER_SECRET_API_KEY_12345" not in str(detail)
        assert "schema_type" in detail  # 型情報のみ含む

    def test_a09_002_acceptance_criteria_detail_no_description_content(self) -> None:
        """TC-UT-A09-002: acceptance_criteria_empty_description の detail に
        description 本文が含まれない。"""
        # 空の description は Pydantic または domain validator が弾く（description_length=0 のみ）
        with pytest.raises((ValidationError, DeliverableTemplateInvariantViolation)) as exc_info:
            make_deliverable_template(
                acceptance_criteria=(make_acceptance_criterion(description=""),),
            )
        if isinstance(exc_info.value, DeliverableTemplateInvariantViolation):
            detail = exc_info.value.detail
            # description 本文ではなく長さ情報のみ
            assert "description_length" in detail
            assert detail["description_length"] == 0

    def test_a09_003_duplicate_criterion_detail_no_description_content(self) -> None:
        """TC-UT-A09-003: acceptance_criteria_duplicate_id の detail に
        description 本文が含まれない。"""
        shared_id = uuid4()
        ac1 = make_acceptance_criterion(
            criterion_id=shared_id,
            description="秘密の受入基準テキスト",
        )
        ac2 = make_acceptance_criterion(criterion_id=shared_id, description="別の説明")
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(acceptance_criteria=(ac1, ac2))
        detail = exc_info.value.detail
        # criterion_id のみ含み、description 本文は含まない
        assert "criterion_id" in detail
        assert "秘密の受入基準テキスト" not in str(detail)
        assert "別の説明" not in str(detail)
