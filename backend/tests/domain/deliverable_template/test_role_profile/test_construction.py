"""RoleProfile 構築テスト。

TC-UT-RP-001〜005:
- 正常構築（空 refs / 重複なし refs）
- _validate_no_duplicate_refs 異常系
- frozen 不変性
- extra='forbid'

Issue #115 / docs/features/deliverable-template/domain/test-design.md §UT-RP 構築
"""

from __future__ import annotations

import pytest
from bakufu.domain.deliverable_template.role_profile import RoleProfile
from bakufu.domain.exceptions import RoleProfileInvariantViolation
from bakufu.domain.value_objects.enums import Role
from pydantic import ValidationError

from tests.factories.deliverable_template import (
    is_synthetic,
    make_deliverable_template_ref,
    make_role_profile,
)


# ---------------------------------------------------------------------------
# TC-UT-RP-001: 空 refs で構築成功
# ---------------------------------------------------------------------------
class TestRoleProfileEmptyRefs:
    """TC-UT-RP-001: deliverable_template_refs=() で構築成功。"""

    def test_empty_refs_constructs_successfully(self) -> None:
        rp = make_role_profile(deliverable_template_refs=())
        assert rp.deliverable_template_refs == ()

    def test_factory_marks_synthetic(self) -> None:
        rp = make_role_profile()
        assert is_synthetic(rp)


# ---------------------------------------------------------------------------
# TC-UT-RP-002: 重複なし refs で構築成功
# ---------------------------------------------------------------------------
class TestRoleProfileUniqueRefs:
    """TC-UT-RP-002: 重複のない refs で構築成功。"""

    def test_unique_refs_construct_successfully(self) -> None:
        ref_a = make_deliverable_template_ref()
        ref_b = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref_a, ref_b))
        assert len(rp.deliverable_template_refs) == 2


# ---------------------------------------------------------------------------
# TC-UT-RP-003: _validate_no_duplicate_refs — 同一 template_id を 2 件
# ---------------------------------------------------------------------------
class TestRoleProfileDuplicateRefs:
    """TC-UT-RP-003: 同一 template_id の ref 2 件 → duplicate_template_ref。"""

    def test_duplicate_template_id_raises(self) -> None:
        ref_a = make_deliverable_template_ref()
        ref_a_dup = make_deliverable_template_ref(template_id=ref_a.template_id)
        with pytest.raises(RoleProfileInvariantViolation) as exc_info:
            make_role_profile(deliverable_template_refs=(ref_a, ref_a_dup))
        assert exc_info.value.kind == "duplicate_template_ref"

    def test_duplicate_raises_with_template_id_in_detail(self) -> None:
        ref_a = make_deliverable_template_ref()
        ref_a_dup = make_deliverable_template_ref(template_id=ref_a.template_id)
        with pytest.raises(RoleProfileInvariantViolation) as exc_info:
            make_role_profile(deliverable_template_refs=(ref_a, ref_a_dup))
        assert str(ref_a.template_id) in str(exc_info.value.detail["template_id"])


# ---------------------------------------------------------------------------
# TC-UT-RP-004: frozen 不変性
# ---------------------------------------------------------------------------
class TestRoleProfileFrozen:
    """TC-UT-RP-004: frozen モデルへの直接代入は pydantic.ValidationError。"""

    def test_direct_role_assignment_raises(self) -> None:
        rp = make_role_profile()
        with pytest.raises((ValidationError, TypeError)):
            rp.role = Role.LEADER  # type: ignore[misc]

    def test_direct_refs_assignment_raises(self) -> None:
        rp = make_role_profile()
        with pytest.raises((ValidationError, TypeError)):
            rp.deliverable_template_refs = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-UT-RP-005: extra='forbid'
# ---------------------------------------------------------------------------
class TestRoleProfileExtraForbid:
    """TC-UT-RP-005: 未知フィールドは pydantic.ValidationError。"""

    def test_unknown_field_raises_validation_error(self) -> None:
        base = make_role_profile()
        data = base.model_dump(mode="python")
        data["unknown_field"] = "forbidden"
        with pytest.raises(ValidationError):
            RoleProfile.model_validate(data)
