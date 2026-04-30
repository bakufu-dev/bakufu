"""DeliverableTemplate / RoleProfile 結合テスト（lifecycle シナリオ）。

TC-IT-DT-001〜005:
1. DT lifecycle 完走（構築 → compose → create_new_version）
2. RP lifecycle 完走（構築 → add × 2 → remove → get_all_acceptance_criteria）
3. union / dedup / ordering 完全シナリオ
4. pre-validate 安全性（§確定 A）
5. §確定 C: DI stub validator で端から端まで

外部 I/O ゼロ。factory 経由で全入力を生成。

Issue #115 / docs/features/deliverable-template/domain/test-design.md §結合テスト
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
# TC-IT-DT-001: DT lifecycle 完走（構築 → compose → create_new_version）
# ---------------------------------------------------------------------------
class TestDeliverableTemplateLifecycle:
    """TC-IT-DT-001: 3 段階 lifecycle 完走、各ステップで新インスタンス返却、元インスタンス不変。"""

    def test_full_lifecycle_completes(self) -> None:
        dt = make_deliverable_template(
            version=make_semver(major=1, minor=0, patch=0),
            composition=(),
        )
        original_version = dt.version
        original_composition = dt.composition

        # Step 1: compose
        ref_a = make_deliverable_template_ref()
        ref_b = make_deliverable_template_ref()
        composed_dt = dt.compose((ref_a, ref_b))

        assert len(composed_dt.composition) == 2
        # §確定 B: acceptance_criteria は空にリセット
        assert composed_dt.acceptance_criteria == ()
        # 元 dt は不変
        assert dt.composition == original_composition

        # Step 2: create_new_version
        versioned_dt = composed_dt.create_new_version(make_semver(major=1, minor=1, patch=0))

        assert versioned_dt.version == make_semver(major=1, minor=1, patch=0)
        assert len(versioned_dt.composition) == 2  # composition 引き継ぎ
        # 元 composed_dt は不変（§確定 A）
        assert composed_dt.version == make_semver(major=1, minor=0, patch=0)

        # Step 3: 元 dt の version が初期値のまま
        assert dt.version == original_version


# ---------------------------------------------------------------------------
# TC-IT-DT-002: RP lifecycle 完走（構築 → add × 2 → remove → get_all_acceptance_criteria）
# ---------------------------------------------------------------------------
class TestRoleProfileLifecycle:
    """TC-IT-DT-002: 4 段階 lifecycle 完走、最終 refs=[ref_b]。"""

    def test_full_role_profile_lifecycle(self) -> None:
        rp = make_role_profile()

        # Step 1: ref_a を追加
        ref_a = make_deliverable_template_ref()
        rp_with_a = rp.add_template_ref(ref_a)
        assert len(rp_with_a.deliverable_template_refs) == 1

        # Step 2: ref_b を追加
        ref_b = make_deliverable_template_ref()
        rp_with_ab = rp_with_a.add_template_ref(ref_b)
        assert len(rp_with_ab.deliverable_template_refs) == 2

        # Step 3: ref_a を削除
        rp_with_b = rp_with_ab.remove_template_ref(ref_a.template_id)
        assert len(rp_with_b.deliverable_template_refs) == 1
        assert rp_with_b.deliverable_template_refs[0].template_id == ref_b.template_id

        # Step 4: get_all_acceptance_criteria（ref_b のテンプレートの基準を取得）
        ac = make_acceptance_criterion(description="受入基準テスト")
        tmpl_b = make_deliverable_template(
            template_id=ref_b.template_id,
            acceptance_criteria=(ac,),
        )
        lookup = {tmpl_b.id: tmpl_b}
        result = rp_with_b.get_all_acceptance_criteria(lookup)
        assert len(result) == 1
        assert result[0].description == "受入基準テスト"


# ---------------------------------------------------------------------------
# TC-IT-DT-003: union / dedup / ordering 完全シナリオ
# ---------------------------------------------------------------------------
class TestGetAllCriteriaFullScenario:
    """TC-IT-DT-003: 複数テンプレート、重複 criterion あり、required=True 先頭。"""

    def test_union_dedup_and_ordering(self) -> None:
        shared_id = uuid4()
        # criterion_x は required=True、tmpl_a と tmpl_b の両方に存在（重複）
        criterion_x = make_acceptance_criterion(
            criterion_id=shared_id,
            description="共通必須基準",
            required=True,
        )
        # criterion_y は tmpl_a のみ（required=False）
        criterion_y = make_acceptance_criterion(description="任意基準", required=False)
        # criterion_z は tmpl_c のみ（required=True）
        criterion_z = make_acceptance_criterion(description="別の必須基準", required=True)

        tmpl_a = make_deliverable_template(acceptance_criteria=(criterion_x, criterion_y))
        tmpl_b = make_deliverable_template(acceptance_criteria=(criterion_x,))  # 重複
        tmpl_c = make_deliverable_template(acceptance_criteria=(criterion_z,))

        ref_a = make_deliverable_template_ref(template_id=tmpl_a.id)
        ref_b = make_deliverable_template_ref(template_id=tmpl_b.id)
        ref_c = make_deliverable_template_ref(template_id=tmpl_c.id)
        rp = make_role_profile(deliverable_template_refs=(ref_a, ref_b, ref_c))

        lookup = {tmpl_a.id: tmpl_a, tmpl_b.id: tmpl_b, tmpl_c.id: tmpl_c}
        result = rp.get_all_acceptance_criteria(lookup)

        # 重複排除: criterion_x は 1 件のみ（tmpl_b の重複は除去）
        result_ids = [c.id for c in result]
        assert result_ids.count(shared_id) == 1

        # 合計 3 件（criterion_x + criterion_y + criterion_z）
        assert len(result) == 3

        # required=True 先頭グループ: criterion_x, criterion_z
        required_criteria = [c for c in result if c.required]
        optional_criteria = [c for c in result if not c.required]
        assert len(required_criteria) == 2
        assert len(optional_criteria) == 1

        # ソート後: required 先頭グループが全て optional より先
        required_indices = [result.index(c) for c in required_criteria]
        optional_indices = [result.index(c) for c in optional_criteria]
        assert max(required_indices) < min(optional_indices)


# ---------------------------------------------------------------------------
# TC-IT-DT-004: pre-validate 安全性（§確定 A）
# ---------------------------------------------------------------------------
class TestPreValidateSafety:
    """TC-IT-DT-004: 中間失敗でも状態不変（DT・RP 両方）。"""

    def test_dt_compose_failure_leaves_original_unchanged(self) -> None:
        """DT の compose で自己参照が失敗しても元 DT は不変。"""
        self_id = uuid4()
        dt = make_deliverable_template(template_id=self_id)
        original_composition = dt.composition
        original_name = dt.name

        self_ref = make_deliverable_template_ref(template_id=self_id)
        with pytest.raises(DeliverableTemplateInvariantViolation):
            dt.compose((self_ref,))

        assert dt.composition == original_composition
        assert dt.name == original_name

    def test_rp_add_failure_leaves_original_unchanged(self) -> None:
        """RP の add_template_ref 重複失敗でも元 RP は不変。"""
        ref_a = make_deliverable_template_ref()
        rp = make_role_profile(deliverable_template_refs=(ref_a,))
        original_refs = rp.deliverable_template_refs
        original_id = rp.id

        ref_dup = make_deliverable_template_ref(template_id=ref_a.template_id)
        with pytest.raises(RoleProfileInvariantViolation):
            rp.add_template_ref(ref_dup)

        assert rp.deliverable_template_refs == original_refs
        assert rp.id == original_id


# ---------------------------------------------------------------------------
# TC-IT-DT-005: §確定 C — DI stub validator + 構築チェーン完走
# ---------------------------------------------------------------------------
class TestValidationPortDIEndToEnd:
    """TC-IT-DT-005: valid/invalid スタブを DI して動作が切り替わることを確認。"""

    def setup_method(self) -> None:
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]

    def teardown_method(self) -> None:
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]

    def test_valid_stub_allows_construction(self) -> None:
        """valid スタブを DI → JSON_SCHEMA テンプレートの構築・compose・versioning 完走。"""
        DeliverableTemplate._validator = ValidStubValidator()  # type: ignore[reportPrivateUsage]
        dt = make_deliverable_template(
            type_=TemplateType.JSON_SCHEMA,
            schema={"type": "object"},
            version=make_semver(major=1, minor=0, patch=0),
        )
        assert dt.type == TemplateType.JSON_SCHEMA

        # compose も JSON_SCHEMA のまま動作
        ref = make_deliverable_template_ref()
        composed = dt.compose((ref,))
        assert composed.composition[0].template_id == ref.template_id

        # create_new_version も動作
        versioned = composed.create_new_version(make_semver(major=1, minor=1, patch=0))
        assert versioned.version == make_semver(major=1, minor=1, patch=0)

    def test_invalid_stub_blocks_construction(self) -> None:
        """invalid スタブを DI → JSON_SCHEMA テンプレートの構築が schema_format_invalid。"""
        DeliverableTemplate._validator = InvalidStubValidator()  # type: ignore[reportPrivateUsage]
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.JSON_SCHEMA,
                schema={"type": "object"},
            )
        assert exc_info.value.kind == "schema_format_invalid"

    def test_none_validator_fails_secure(self) -> None:
        """validator=None → JSON_SCHEMA 構築時に Fail Secure（schema_format_invalid）。"""
        DeliverableTemplate._validator = None  # type: ignore[reportPrivateUsage]
        with pytest.raises(DeliverableTemplateInvariantViolation) as exc_info:
            make_deliverable_template(
                type_=TemplateType.JSON_SCHEMA,
                schema={"type": "object"},
            )
        assert exc_info.value.kind == "schema_format_invalid"
