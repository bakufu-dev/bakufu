"""DeliverableTemplate ふるまいテスト。

TC-UT-DT-018〜025:
- create_new_version: 正常系・境界値・pre-validate 不変性（§確定 A）
- compose: 正常系・自己参照異常系・acceptance_criteria 非継承（§確定 B）

Issue #115 / docs/features/deliverable-template/domain/test-design.md §UT-DT ふるまい
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.exceptions import DeliverableTemplateInvariantViolation

from tests.factories.deliverable_template import (
    make_acceptance_criterion,
    make_deliverable_template,
    make_deliverable_template_ref,
    make_semver,
)


# ---------------------------------------------------------------------------
# TC-UT-DT-018: create_new_version — patch bump（new > current）
# ---------------------------------------------------------------------------
class TestCreateNewVersionPatchBump:
    """TC-UT-DT-018: new_version > current（patch bump）→ 新インスタンス、version のみ更新。"""

    def test_patch_bump_returns_new_instance_with_updated_version(self) -> None:
        dt = make_deliverable_template(version=make_semver(major=1, minor=2, patch=3))
        new_dt = dt.create_new_version(make_semver(major=1, minor=2, patch=4))
        assert new_dt.version == make_semver(major=1, minor=2, patch=4)

    def test_other_attributes_are_preserved(self) -> None:
        dt = make_deliverable_template(
            name="テンプレート名",
            version=make_semver(major=1, minor=0, patch=0),
        )
        new_dt = dt.create_new_version(make_semver(major=1, minor=0, patch=1))
        assert new_dt.name == "テンプレート名"
        assert new_dt.id == dt.id

    def test_returns_different_instance(self) -> None:
        dt = make_deliverable_template(version=make_semver(major=1, minor=0, patch=0))
        new_dt = dt.create_new_version(make_semver(major=1, minor=0, patch=1))
        assert new_dt is not dt


# ---------------------------------------------------------------------------
# TC-UT-DT-019: create_new_version — major bump
# ---------------------------------------------------------------------------
class TestCreateNewVersionMajorBump:
    """TC-UT-DT-019: new_version > current（major bump）→ 新インスタンス。"""

    def test_major_bump_succeeds(self) -> None:
        dt = make_deliverable_template(version=make_semver(major=1, minor=5, patch=3))
        new_dt = dt.create_new_version(make_semver(major=2, minor=0, patch=0))
        assert new_dt.version == make_semver(major=2, minor=0, patch=0)


# ---------------------------------------------------------------------------
# TC-UT-DT-020: create_new_version — new_version == current
# ---------------------------------------------------------------------------
class TestCreateNewVersionEqual:
    """TC-UT-DT-020: new_version == current → version_not_greater。"""

    def test_equal_version_raises(self) -> None:
        dt = make_deliverable_template(version=make_semver(major=1, minor=2, patch=3))
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            dt.create_new_version(make_semver(major=1, minor=2, patch=3))
        assert exc_info.value.kind == "version_not_greater"


# ---------------------------------------------------------------------------
# TC-UT-DT-021: create_new_version — new_version < current
# ---------------------------------------------------------------------------
class TestCreateNewVersionLess:
    """TC-UT-DT-021: new_version < current → version_not_greater。"""

    def test_lesser_version_raises(self) -> None:
        dt = make_deliverable_template(version=make_semver(major=1, minor=2, patch=3))
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            dt.create_new_version(make_semver(major=1, minor=2, patch=2))
        assert exc_info.value.kind == "version_not_greater"

    def test_lesser_minor_raises(self) -> None:
        dt = make_deliverable_template(version=make_semver(major=1, minor=5, patch=0))
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            dt.create_new_version(make_semver(major=1, minor=4, patch=9))
        assert exc_info.value.kind == "version_not_greater"

    def test_lesser_major_raises(self) -> None:
        dt = make_deliverable_template(version=make_semver(major=2, minor=0, patch=0))
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            dt.create_new_version(make_semver(major=1, minor=9, patch=9))
        assert exc_info.value.kind == "version_not_greater"


# ---------------------------------------------------------------------------
# TC-UT-DT-022: §確定 A — pre-validate: 失敗時の元インスタンス不変
# ---------------------------------------------------------------------------
class TestCreateNewVersionPreValidateSafety:
    """TC-UT-DT-022: 失敗後も元インスタンスの全属性が変化なし（§確定 A）。"""

    def test_failed_create_new_version_leaves_original_unchanged(self) -> None:
        dt = make_deliverable_template(
            name="オリジナル",
            version=make_semver(major=1, minor=0, patch=0),
        )
        original_name = dt.name
        original_version = dt.version
        original_id = dt.id

        with pytest.raises(DeliverableTemplateInvariantViolation):
            dt.create_new_version(make_semver(major=0, minor=9, patch=0))

        # 失敗後もオリジナルは変化なし
        assert dt.name == original_name
        assert dt.version == original_version
        assert dt.id == original_id


# ---------------------------------------------------------------------------
# TC-UT-DT-023: compose — 正常系（非自己参照 refs）
# ---------------------------------------------------------------------------
class TestComposeNormal:
    """TC-UT-DT-023: compose(refs) → 新インスタンス、composition=refs。"""

    def test_compose_with_valid_refs_updates_composition(self) -> None:
        ref_a = make_deliverable_template_ref()
        ref_b = make_deliverable_template_ref()
        dt = make_deliverable_template()
        new_dt = dt.compose((ref_a, ref_b))
        assert len(new_dt.composition) == 2

    def test_compose_returns_new_instance(self) -> None:
        ref = make_deliverable_template_ref()
        dt = make_deliverable_template()
        new_dt = dt.compose((ref,))
        assert new_dt is not dt

    def test_compose_preserves_name_and_other_attributes(self) -> None:
        dt = make_deliverable_template(name="元テンプレート", description="説明")
        ref = make_deliverable_template_ref()
        new_dt = dt.compose((ref,))
        assert new_dt.name == "元テンプレート"
        assert new_dt.id == dt.id


# ---------------------------------------------------------------------------
# TC-UT-DT-024: compose — 自己参照 refs
# ---------------------------------------------------------------------------
class TestComposeSelfRef:
    """TC-UT-DT-024: compose に自己参照 ref → composition_self_ref。"""

    def test_self_ref_in_compose_raises(self) -> None:
        self_id = uuid4()
        dt = make_deliverable_template(template_id=self_id)
        self_ref = make_deliverable_template_ref(template_id=self_id)
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            dt.compose((self_ref,))
        assert exc_info.value.kind == "composition_self_ref"


# ---------------------------------------------------------------------------
# TC-UT-DT-025: §確定 B — compose は acceptance_criteria を引き継がない
# ---------------------------------------------------------------------------
class TestComposeDoesNotInheritCriteria:
    """TC-UT-DT-025: compose 後の新インスタンスの acceptance_criteria は空タプル（§確定 B）。"""

    def test_compose_resets_acceptance_criteria_to_empty(self) -> None:
        ac = make_acceptance_criterion(description="既存の受入基準")
        dt = make_deliverable_template(acceptance_criteria=(ac,))
        assert len(dt.acceptance_criteria) == 1  # 元は 1 件

        ref = make_deliverable_template_ref()
        new_dt = dt.compose((ref,))

        # 合成後は acceptance_criteria が空にリセットされる
        assert new_dt.acceptance_criteria == ()

    def test_compose_empty_refs_also_resets_criteria(self) -> None:
        ac = make_acceptance_criterion(description="基準")
        dt = make_deliverable_template(acceptance_criteria=(ac,))
        new_dt = dt.compose(())
        assert new_dt.acceptance_criteria == ()
