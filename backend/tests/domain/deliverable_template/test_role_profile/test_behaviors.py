"""RoleProfile ふるまいテスト。

TC-UT-RP-006〜014:
- add_template_ref: 正常系・重複異常系
- remove_template_ref: 正常系・未発見異常系
- get_all_acceptance_criteria: union / dedup / required 優先ソート
- §確定 D: empire-scope 一意性は application 層責務
- §確定 A: pre-validate 失敗時の元インスタンス不変

Issue #115 / docs/features/deliverable-template/domain/test-design.md §UT-RP ふるまい
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import RoleProfileInvariantViolation
from bakufu.domain.value_objects.enums import Role

from tests.factories.deliverable_template import (
    make_acceptance_criterion,
    make_deliverable_template,
    make_deliverable_template_ref,
    make_role_profile,
)


# ---------------------------------------------------------------------------
# TC-UT-RP-006: add_template_ref — 新規 ref
# ---------------------------------------------------------------------------
class TestAddTemplateRef:
    """TC-UT-RP-006: add_template_ref → ref が末尾追加された新インスタンス。"""

    def test_add_ref_to_empty_profile(self) -> None:
        rp = make_role_profile()
        ref_a = make_deliverable_template_ref()
        new_rp = rp.add_template_ref(ref_a)
        assert len(new_rp.deliverable_template_refs) == 1

    def test_add_ref_appends_to_end(self) -> None:
        ref_a = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref_a,))
        ref_b = make_deliverable_template_ref()
        new_rp = rp.add_template_ref(ref_b)
        assert new_rp.deliverable_template_refs[-1].template_id == ref_b.template_id

    def test_add_ref_returns_new_instance(self) -> None:
        rp = make_role_profile()
        ref = make_deliverable_template_ref()
        new_rp = rp.add_template_ref(ref)
        assert new_rp is not rp


# ---------------------------------------------------------------------------
# TC-UT-RP-007: add_template_ref — 既存 template_id の重複
# ---------------------------------------------------------------------------
class TestAddDuplicateTemplateRef:
    """TC-UT-RP-007: 既存 template_id と同一の ref → duplicate_template_ref。"""

    def test_duplicate_template_id_raises(self) -> None:
        ref_a = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref_a,))
        ref_dup = make_deliverable_template_ref(template_id=ref_a.template_id)
        with pytest.raises(RoleProfileInvariantViolation) as exc_info:
            rp.add_template_ref(ref_dup)
        assert exc_info.value.kind == "duplicate_template_ref"

    def test_duplicate_error_contains_template_id(self) -> None:
        ref_a = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref_a,))
        ref_dup = make_deliverable_template_ref(template_id=ref_a.template_id)
        with pytest.raises(RoleProfileInvariantViolation) as exc_info:
            rp.add_template_ref(ref_dup)
        assert str(ref_a.template_id) in str(exc_info.value)


# ---------------------------------------------------------------------------
# TC-UT-RP-008: remove_template_ref — 存在する template_id を削除
# ---------------------------------------------------------------------------
class TestRemoveTemplateRef:
    """TC-UT-RP-008: remove_template_ref → ref を除いた新インスタンス。"""

    def test_remove_existing_ref_succeeds(self) -> None:
        ref_a = make_deliverable_template_ref()
        ref_b = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref_a, ref_b))
        new_rp = rp.remove_template_ref(ref_a.template_id)
        assert len(new_rp.deliverable_template_refs) == 1
        assert new_rp.deliverable_template_refs[0].template_id == ref_b.template_id

    def test_remove_returns_new_instance(self) -> None:
        ref = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref,))
        new_rp = rp.remove_template_ref(ref.template_id)
        assert new_rp is not rp

    def test_remove_last_ref_returns_empty(self) -> None:
        ref = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref,))
        new_rp = rp.remove_template_ref(ref.template_id)
        assert new_rp.deliverable_template_refs == ()


# ---------------------------------------------------------------------------
# TC-UT-RP-009: remove_template_ref — 存在しない template_id
# ---------------------------------------------------------------------------
class TestRemoveNonExistentRef:
    """TC-UT-RP-009: 存在しない template_id → template_ref_not_found。"""

    def test_nonexistent_template_id_raises(self) -> None:
        rp = make_role_profile()
        with pytest.raises(RoleProfileInvariantViolation) as exc_info:
            rp.remove_template_ref(uuid4())
        assert exc_info.value.kind == "template_ref_not_found"


# ---------------------------------------------------------------------------
# TC-UT-RP-010: get_all_acceptance_criteria — required=True 先頭ソート
# ---------------------------------------------------------------------------
class TestGetAllCriteriaOrdering:
    """TC-UT-RP-010: required=True の基準が先頭グループ、required=False が後続グループ。"""

    def test_required_true_comes_before_required_false(self) -> None:
        criterion_required = make_acceptance_criterion(description="必須基準", required=True)
        criterion_optional = make_acceptance_criterion(description="任意基準", required=False)
        tmpl = make_deliverable_template(
            acceptance_criteria=(criterion_optional, criterion_required),
        )
        ref = make_deliverable_template_ref(template_id=tmpl.id)
        rp = make_role_profile(deliverable_template_refs=(ref,))
        lookup = {tmpl.id: tmpl}
        result = rp.get_all_acceptance_criteria(lookup)
        assert len(result) == 2
        assert result[0].required is True
        assert result[1].required is False


# ---------------------------------------------------------------------------
# TC-UT-RP-011: get_all_acceptance_criteria — 同一 id による重複排除
# ---------------------------------------------------------------------------
class TestGetAllCriteriaDedup:
    """TC-UT-RP-011: 同一 AcceptanceCriterion.id の重複は最初の出現のみ保持。"""

    def test_duplicate_criterion_id_is_deduped(self) -> None:
        shared_id = uuid4()
        criterion_x = make_acceptance_criterion(criterion_id=shared_id, description="共通基準")
        tmpl_a = make_deliverable_template(acceptance_criteria=(criterion_x,))
        tmpl_b = make_deliverable_template(acceptance_criteria=(criterion_x,))
        ref_a = make_deliverable_template_ref(template_id=tmpl_a.id)
        ref_b = make_deliverable_template_ref(template_id=tmpl_b.id)
        rp = make_role_profile(deliverable_template_refs=(ref_a, ref_b))
        lookup = {tmpl_a.id: tmpl_a, tmpl_b.id: tmpl_b}
        result = rp.get_all_acceptance_criteria(lookup)
        # 重複排除で 1 件のみ
        assert len(result) == 1
        assert result[0].id == shared_id


# ---------------------------------------------------------------------------
# TC-UT-RP-012: get_all_acceptance_criteria — required=False のみ
# ---------------------------------------------------------------------------
class TestGetAllCriteriaAllOptional:
    """TC-UT-RP-012: required=False のみの criteria は全件後続グループとして返却。"""

    def test_all_optional_criteria_in_second_group(self) -> None:
        opt1 = make_acceptance_criterion(description="任意1", required=False)
        opt2 = make_acceptance_criterion(description="任意2", required=False)
        tmpl = make_deliverable_template(acceptance_criteria=(opt1, opt2))
        ref = make_deliverable_template_ref(template_id=tmpl.id)
        rp = make_role_profile(deliverable_template_refs=(ref,))
        lookup = {tmpl.id: tmpl}
        result = rp.get_all_acceptance_criteria(lookup)
        assert len(result) == 2
        assert all(not c.required for c in result)


# ---------------------------------------------------------------------------
# TC-UT-RP-013: §確定 D — RoleProfile が empire-scope 一意性を強制しない
# ---------------------------------------------------------------------------
class TestRoleProfileNoDomainUniqueConstraint:
    """TC-UT-RP-013: 同一 role の RoleProfile を 2 つ構築できる。
    domain 層は empire-scope 一意性を強制しない。"""

    def test_two_profiles_with_same_role_can_coexist(self) -> None:
        rp1 = make_role_profile(role=Role.DEVELOPER)
        rp2 = make_role_profile(role=Role.DEVELOPER)
        # 両方とも構築成功。empire-scope 一意性は application/repository 層責務
        assert rp1.role == rp2.role
        assert rp1.id != rp2.id


# ---------------------------------------------------------------------------
# TC-UT-RP-014: §確定 A — pre-validate 失敗時の元インスタンス不変
# ---------------------------------------------------------------------------
class TestAddTemplateRefPreValidateSafety:
    """TC-UT-RP-014: add_template_ref 失敗後も元 RoleProfile の属性は変化なし。"""

    def test_failed_add_leaves_original_unchanged(self) -> None:
        ref_a = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref_a,))
        original_refs = rp.deliverable_template_refs
        original_id = rp.id

        ref_dup = make_deliverable_template_ref(template_id=ref_a.template_id)
        with pytest.raises(RoleProfileInvariantViolation):
            rp.add_template_ref(ref_dup)

        # 失敗後もオリジナルは変化なし
        assert rp.deliverable_template_refs == original_refs
        assert rp.id == original_id
