"""Value Objects テスト。

TC-UT-SV-001〜012: SemVer 全メソッド・制約・frozen
TC-UT-DRef-001〜002: DeliverableTemplateRef 構築・frozen
TC-UT-AC-001〜005: AcceptanceCriterion 構築・制約・frozen

Issue #115 / docs/features/deliverable-template/domain/test-design.md §UT-SV/DRef/AC
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableTemplateRef,
    SemVer,
)
from pydantic import ValidationError

from tests.factories.deliverable_template import (
    make_acceptance_criterion,
    make_deliverable_template_ref,
    make_semver,
)


# ---------------------------------------------------------------------------
# TC-UT-SV-001: SemVer 正常構築
# ---------------------------------------------------------------------------
class TestSemVerConstruction:
    """TC-UT-SV-001: SemVer(major=1, minor=2, patch=3) → 構築成功。"""

    def test_valid_semver_constructs(self) -> None:
        sv = SemVer(major=1, minor=2, patch=3)
        assert sv.major == 1
        assert sv.minor == 2
        assert sv.patch == 3

    def test_zero_version_is_valid(self) -> None:
        sv = SemVer(major=0, minor=0, patch=0)
        assert sv.major == 0

    def test_factory_creates_valid_instance(self) -> None:
        sv = make_semver(major=2, minor=5, patch=1)
        assert sv.major == 2


# ---------------------------------------------------------------------------
# TC-UT-SV-002: SemVer — 負の major（ge=0 制約）
# ---------------------------------------------------------------------------
class TestSemVerNonNegative:
    """TC-UT-SV-002: SemVer(major=-1) → pydantic.ValidationError。"""

    def test_negative_major_raises(self) -> None:
        with pytest.raises(ValidationError):
            SemVer(major=-1, minor=0, patch=0)

    def test_negative_minor_raises(self) -> None:
        with pytest.raises(ValidationError):
            SemVer(major=0, minor=-1, patch=0)

    def test_negative_patch_raises(self) -> None:
        with pytest.raises(ValidationError):
            SemVer(major=0, minor=0, patch=-1)


# ---------------------------------------------------------------------------
# TC-UT-SV-003: SemVer.from_str — 正常
# ---------------------------------------------------------------------------
class TestSemVerFromStr:
    """TC-UT-SV-003: SemVer.from_str("1.2.3") → SemVer(1,2,3)。"""

    def test_valid_string_parses(self) -> None:
        sv = SemVer.from_str("1.2.3")
        assert sv.major == 1
        assert sv.minor == 2
        assert sv.patch == 3

    def test_zero_version_string_parses(self) -> None:
        sv = SemVer.from_str("0.0.0")
        assert sv.major == 0
        assert sv.minor == 0
        assert sv.patch == 0


# ---------------------------------------------------------------------------
# TC-UT-SV-004: SemVer.from_str — 形式不正
# ---------------------------------------------------------------------------
class TestSemVerFromStrInvalid:
    """TC-UT-SV-004: SemVer.from_str("invalid") → ValueError。"""

    def test_invalid_format_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid SemVer"):
            SemVer.from_str("invalid")

    def test_missing_patch_raises(self) -> None:
        """TC-UT-SV-006: 2 フィールドのみ → ValueError。"""
        with pytest.raises(ValueError):
            SemVer.from_str("1.2")

    def test_extra_fields_raises(self) -> None:
        with pytest.raises(ValueError):
            SemVer.from_str("1.2.3.4")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            SemVer.from_str("")


# ---------------------------------------------------------------------------
# TC-UT-SV-005: SemVer.from_str — 非負整数違反
# ---------------------------------------------------------------------------
class TestSemVerFromStrNegative:
    """TC-UT-SV-005: SemVer.from_str("1.-1.0") → ValueError（非負整数制約）。"""

    def test_negative_minor_in_string_raises(self) -> None:
        with pytest.raises((ValueError, ValidationError)):
            SemVer.from_str("1.-1.0")

    def test_non_integer_raises(self) -> None:
        with pytest.raises(ValueError):
            SemVer.from_str("1.a.0")


# ---------------------------------------------------------------------------
# TC-UT-SV-007: SemVer.is_compatible_with — 同 major
# ---------------------------------------------------------------------------
class TestSemVerCompatibility:
    """TC-UT-SV-007/008: is_compatible_with は major 一致のみを判定。"""

    def test_same_major_is_compatible(self) -> None:
        sv1 = SemVer(major=1, minor=0, patch=0)
        sv2 = SemVer(major=1, minor=5, patch=3)
        assert sv1.is_compatible_with(sv2) is True

    def test_different_major_is_not_compatible(self) -> None:
        """TC-UT-SV-008: 異なる major → False。"""
        sv1 = SemVer(major=1, minor=0, patch=0)
        sv2 = SemVer(major=2, minor=0, patch=0)
        assert sv1.is_compatible_with(sv2) is False

    def test_zero_major_compatible_with_zero_major(self) -> None:
        sv1 = SemVer(major=0, minor=1, patch=0)
        sv2 = SemVer(major=0, minor=99, patch=99)
        assert sv1.is_compatible_with(sv2) is True


# ---------------------------------------------------------------------------
# TC-UT-SV-009: SemVer.__str__
# ---------------------------------------------------------------------------
class TestSemVerStr:
    """TC-UT-SV-009: str(SemVer(1,2,3)) → "1.2.3"。"""

    def test_str_returns_dot_notation(self) -> None:
        sv = SemVer(major=1, minor=2, patch=3)
        assert str(sv) == "1.2.3"

    def test_str_zero_version(self) -> None:
        sv = SemVer(major=0, minor=0, patch=0)
        assert str(sv) == "0.0.0"


# ---------------------------------------------------------------------------
# TC-UT-SV-010: SemVer frozen
# ---------------------------------------------------------------------------
class TestSemVerFrozen:
    """TC-UT-SV-010: frozen モデルへの直接代入 → エラー。"""

    def test_direct_major_assignment_raises(self) -> None:
        sv = SemVer(major=1, minor=0, patch=0)
        with pytest.raises((ValidationError, TypeError)):
            sv.major = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-UT-SV-011: SemVer extra='forbid'
# ---------------------------------------------------------------------------
class TestSemVerExtraForbid:
    """TC-UT-SV-011: 未知フィールドは pydantic.ValidationError。"""

    def test_extra_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            SemVer.model_validate({"major": 1, "minor": 0, "patch": 0, "extra": "x"})


# ---------------------------------------------------------------------------
# TC-UT-SV-012: create_new_version 用 tuple 比較 — boundary
# ---------------------------------------------------------------------------
class TestSemVerTupleComparison:
    """TC-UT-SV-012: (major,minor,patch) tuple 比較が辞書的順序に従う。"""

    def test_patch_increment_is_greater(self) -> None:
        sv1 = SemVer(major=1, minor=0, patch=0)
        sv2 = SemVer(major=1, minor=0, patch=1)
        t1 = (sv1.major, sv1.minor, sv1.patch)
        t2 = (sv2.major, sv2.minor, sv2.patch)
        assert t2 > t1

    def test_minor_takes_precedence_over_patch(self) -> None:
        sv_minor = SemVer(major=1, minor=1, patch=0)
        sv_patch = SemVer(major=1, minor=0, patch=99)
        t_minor = (sv_minor.major, sv_minor.minor, sv_minor.patch)
        t_patch = (sv_patch.major, sv_patch.minor, sv_patch.patch)
        assert t_minor > t_patch

    def test_major_takes_highest_precedence(self) -> None:
        sv_major = SemVer(major=2, minor=0, patch=0)
        sv_minor_patch = SemVer(major=1, minor=99, patch=99)
        t_major = (sv_major.major, sv_major.minor, sv_major.patch)
        t_mp = (sv_minor_patch.major, sv_minor_patch.minor, sv_minor_patch.patch)
        assert t_major > t_mp


# ---------------------------------------------------------------------------
# TC-UT-DRef-001: DeliverableTemplateRef 正常構築
# ---------------------------------------------------------------------------
class TestDeliverableTemplateRefConstruction:
    """TC-UT-DRef-001: valid な DeliverableTemplateRef の構築。"""

    def test_valid_ref_constructs(self) -> None:
        ref = DeliverableTemplateRef(
            template_id=uuid4(),
            minimum_version=SemVer(major=1, minor=0, patch=0),
        )
        assert ref.template_id is not None
        assert ref.minimum_version == SemVer(major=1, minor=0, patch=0)

    def test_factory_creates_valid_ref(self) -> None:
        ref = make_deliverable_template_ref()
        assert ref.template_id is not None


# ---------------------------------------------------------------------------
# TC-UT-DRef-002: DeliverableTemplateRef frozen
# ---------------------------------------------------------------------------
class TestDeliverableTemplateRefFrozen:
    """TC-UT-DRef-002: frozen 不変性。"""

    def test_direct_template_id_assignment_raises(self) -> None:
        ref = make_deliverable_template_ref()
        with pytest.raises((ValidationError, TypeError)):
            ref.template_id = uuid4()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TC-UT-AC-001: AcceptanceCriterion 正常構築
# ---------------------------------------------------------------------------
class TestAcceptanceCriterionConstruction:
    """TC-UT-AC-001: valid な AcceptanceCriterion の構築。"""

    def test_valid_criterion_constructs(self) -> None:
        ac = AcceptanceCriterion(
            id=uuid4(),
            description="正常な受入基準テキスト",
            required=True,
        )
        assert ac.description == "正常な受入基準テキスト"
        assert ac.required is True

    def test_factory_creates_valid_instance(self) -> None:
        ac = make_acceptance_criterion()
        assert len(ac.description) > 0


# ---------------------------------------------------------------------------
# TC-UT-AC-002: AcceptanceCriterion — description 空文字
# ---------------------------------------------------------------------------
class TestAcceptanceCriterionEmptyDescription:
    """TC-UT-AC-002: description='' → pydantic.ValidationError（min_length=1）。"""

    def test_empty_description_raises(self) -> None:
        with pytest.raises(ValidationError):
            AcceptanceCriterion(id=uuid4(), description="", required=True)


# ---------------------------------------------------------------------------
# TC-UT-AC-003: AcceptanceCriterion — description 501 文字
# ---------------------------------------------------------------------------
class TestAcceptanceCriterionMaxLength:
    """TC-UT-AC-003: description > 500 文字 → pydantic.ValidationError（max_length=500）。"""

    def test_description_over_500_chars_raises(self) -> None:
        with pytest.raises(ValidationError):
            AcceptanceCriterion(id=uuid4(), description="a" * 501, required=True)

    def test_description_exactly_500_chars_succeeds(self) -> None:
        ac = AcceptanceCriterion(id=uuid4(), description="a" * 500, required=True)
        assert len(ac.description) == 500


# ---------------------------------------------------------------------------
# TC-UT-AC-004: AcceptanceCriterion — required デフォルト
# ---------------------------------------------------------------------------
class TestAcceptanceCriterionDefaultRequired:
    """TC-UT-AC-004: required 未指定 → required=True（デフォルト値）。"""

    def test_default_required_is_true(self) -> None:
        ac = AcceptanceCriterion(id=uuid4(), description="基準")
        assert ac.required is True


# ---------------------------------------------------------------------------
# TC-UT-AC-005: AcceptanceCriterion frozen
# ---------------------------------------------------------------------------
class TestAcceptanceCriterionFrozen:
    """TC-UT-AC-005: frozen 不変性。"""

    def test_direct_required_assignment_raises(self) -> None:
        ac = make_acceptance_criterion()
        with pytest.raises((ValidationError, TypeError)):
            ac.required = False  # type: ignore[misc]
