"""definitions.py ユニットテスト（TC-UT-TL-001〜002）。

Issue: #124
設計書: docs/features/deliverable-template/template-library/test-design.md
対応要件: §確定 A / §確定 B / §確定 C / §確定 G

DB 不要（UT）。import 時に全テンプレートが valid Aggregate として構築できることを確認する。
"""

from __future__ import annotations

from uuid import UUID, uuid5

from bakufu.application.services.template_library.definitions import (
    BAKUFU_TEMPLATE_NS,
    PRESET_ROLE_TEMPLATE_MAP,
    WELL_KNOWN_TEMPLATES,
)
from bakufu.domain.value_objects.enums import Role, TemplateType
from bakufu.domain.value_objects.template_vos import SemVer


class TestWellKnownTemplates:
    """TC-UT-TL-001: WELL_KNOWN_TEMPLATES 12 件全件の不変条件。"""

    def test_count_is_12(self) -> None:
        """(1) len(WELL_KNOWN_TEMPLATES) == 12。"""
        assert len(WELL_KNOWN_TEMPLATES) == 12

    def test_all_type_markdown(self) -> None:
        """(2) 各テンプレートの type == TemplateType.MARKDOWN。"""
        for t in WELL_KNOWN_TEMPLATES:
            assert t.type == TemplateType.MARKDOWN, f"{t.id}: type={t.type}"

    def test_all_version_1_0_0(self) -> None:
        """(3) 各テンプレートの version == SemVer(1, 0, 0)。"""
        expected = SemVer(major=1, minor=0, patch=0)
        for t in WELL_KNOWN_TEMPLATES:
            assert t.version == expected, f"{t.id}: version={t.version}"

    def test_uuid5_matches_slug(self) -> None:
        """(4) id が UUID5(BAKUFU_TEMPLATE_NS, slug) と一致。

        slug ↔ id の対応は definitions.py の _build_template() が保証する。
        逆算: uuid5(BAKUFU_TEMPLATE_NS, slug) を再計算して比較する。
        """
        slugs = [
            "leader-plan",
            "leader-priority",
            "leader-stakeholder",
            "dev-design",
            "dev-adr",
            "dev-acceptance",
            "dev-impl-pr",
            "dev-lib-readme",
            "tester-testdesign",
            "tester-report",
            "tester-regression",
            "reviewer-review",
        ]
        assert len(WELL_KNOWN_TEMPLATES) == len(slugs)
        for template, slug in zip(WELL_KNOWN_TEMPLATES, slugs, strict=True):
            expected_id = uuid5(BAKUFU_TEMPLATE_NS, slug)
            assert template.id == expected_id, (
                f"slug={slug}: expected {expected_id}, got {template.id}"
            )

    def test_ids_are_unique(self) -> None:
        """(5) id が全 12 件で一意（衝突なし）。"""
        ids = [t.id for t in WELL_KNOWN_TEMPLATES]
        assert len(ids) == len(set(ids)), "UUID 衝突あり"

    def test_all_description_non_empty(self) -> None:
        """(6) 各テンプレートの description が非空文字列。"""
        for t in WELL_KNOWN_TEMPLATES:
            assert isinstance(t.description, str), f"{t.id}: description is not str"
            assert t.description.strip() != "", f"{t.id}: description is empty"

    def test_all_schema_non_empty(self) -> None:
        """(7) 各テンプレートの schema が非空（MARKDOWN ガイドライン文字列）。"""
        for t in WELL_KNOWN_TEMPLATES:
            assert t.schema, f"{t.id}: schema is empty/falsy"
            if isinstance(t.schema, str):
                assert t.schema.strip() != "", f"{t.id}: schema string is whitespace-only"

    def test_namespace_uuid_is_fixed(self) -> None:
        """§確定 C: BAKUFU_TEMPLATE_NS が変更禁止の固定値であることを物理確認。"""
        assert UUID("ba4a2f00-cafe-1234-dead-beefcafe0001") == BAKUFU_TEMPLATE_NS


class TestPresetRoleTemplateMap:
    """TC-UT-TL-002: PRESET_ROLE_TEMPLATE_MAP の整合。"""

    def test_has_all_four_roles(self) -> None:
        """4 Role が全て存在する。"""
        assert set(PRESET_ROLE_TEMPLATE_MAP.keys()) == {
            Role.LEADER,
            Role.DEVELOPER,
            Role.TESTER,
            Role.REVIEWER,
        }

    def test_no_dangling_references(self) -> None:
        """全 DeliverableTemplateRef.template_id が WELL_KNOWN_TEMPLATES の id セットに含まれる。"""
        known_ids = {t.id for t in WELL_KNOWN_TEMPLATES}
        for role, refs in PRESET_ROLE_TEMPLATE_MAP.items():
            for ref in refs:
                assert ref.template_id in known_ids, (
                    f"Role={role}: dangling reference template_id={ref.template_id}"
                )

    def test_leader_has_3_refs(self) -> None:
        """LEADER に 3 件の ref がある。"""
        assert len(PRESET_ROLE_TEMPLATE_MAP[Role.LEADER]) == 3

    def test_developer_has_5_refs(self) -> None:
        """DEVELOPER に 5 件の ref がある。"""
        assert len(PRESET_ROLE_TEMPLATE_MAP[Role.DEVELOPER]) == 5

    def test_tester_has_3_refs(self) -> None:
        """TESTER に 3 件の ref がある。"""
        assert len(PRESET_ROLE_TEMPLATE_MAP[Role.TESTER]) == 3

    def test_reviewer_has_1_ref(self) -> None:
        """REVIEWER に 1 件の ref がある。"""
        assert len(PRESET_ROLE_TEMPLATE_MAP[Role.REVIEWER]) == 1

    def test_all_minimum_version_1_0_0(self) -> None:
        """全 ref の minimum_version が 1.0.0。"""
        expected = SemVer(major=1, minor=0, patch=0)
        for role, refs in PRESET_ROLE_TEMPLATE_MAP.items():
            for ref in refs:
                assert ref.minimum_version == expected, (
                    f"Role={role}: minimum_version={ref.minimum_version}"
                )
