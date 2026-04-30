"""DeliverableTemplate Repository schema 判別 + 変換契約テスト (Issue #119).

TC-IT-DTR-010〜019:
- schema type 判別 5 経路 §確定 D (010〜014)
- SemVer TEXT ラウンドトリップ §確定 E (015)
- acceptance_criteria_json / composition_json A08 防御 §確定 F (016〜018)
- 全フィールド構造的等価 §確定 C (019)

§確定 C / D / E / F:
  docs/features/deliverable-template/repository/detailed-design.md
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pydantic
import pytest
from bakufu.domain.deliverable_template.deliverable_template import (
    DeliverableTemplate as _DeliverableTemplate,
)
from bakufu.domain.value_objects.enums import TemplateType
from bakufu.domain.value_objects.template_vos import SemVer
from bakufu.infrastructure.persistence.sqlite.repositories.deliverable_template_repository import (
    SqliteDeliverableTemplateRepository,
)
from sqlalchemy import text

from tests.factories.deliverable_template import (
    ValidStubValidator,
    make_acceptance_criterion,
    make_deliverable_template,
    make_deliverable_template_ref,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-DTR-010〜014: schema type 判別 5 経路 (§確定 D)
# ---------------------------------------------------------------------------
class TestSchemaTypeDiscrimination:
    """TC-IT-DTR-010〜014: 5 TemplateType 全経路で schema ラウンドトリップを物理確認。

    §確定 D: JSON_SCHEMA / OPENAPI → json.dumps/loads、その他 → plain text。
    """

    _JSON_TYPES = frozenset({TemplateType.JSON_SCHEMA, TemplateType.OPENAPI})

    async def _save_and_restore(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        type_: TemplateType,
        schema: dict[str, object] | str,
    ):  # type: ignore[return]
        # §確定 D: JSON_SCHEMA / OPENAPI はドメインのバリデーター設定が必要
        needs_validator = type_ in self._JSON_TYPES
        if needs_validator:
            _DeliverableTemplate._validator = ValidStubValidator()  # pyright: ignore[reportPrivateUsage]
        try:
            template = make_deliverable_template(type_=type_, schema=schema)
            async with session_factory() as session, session.begin():
                await SqliteDeliverableTemplateRepository(session).save(template)
            async with session_factory() as session:
                return await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)
        finally:
            if needs_validator:
                _DeliverableTemplate._validator = None  # type: ignore[assignment]  # pyright: ignore[reportPrivateUsage]

    async def test_json_schema_type_roundtrip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-010: JSON_SCHEMA type → schema が dict でラウンドトリップ。"""
        schema_dict: dict[str, object] = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        restored = await self._save_and_restore(
            session_factory, TemplateType.JSON_SCHEMA, schema_dict
        )
        assert restored is not None
        assert isinstance(restored.schema, dict), (
            f"[FAIL] JSON_SCHEMA: schema が dict でなく {type(restored.schema)}"
        )
        assert restored.schema == schema_dict

    async def test_openapi_type_roundtrip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-011: OPENAPI type → schema が dict でラウンドトリップ。"""
        schema_dict: dict[str, object] = {
            "openapi": "3.0.0",
            "info": {"title": "test-api", "version": "1.0.0"},
        }
        restored = await self._save_and_restore(session_factory, TemplateType.OPENAPI, schema_dict)
        assert restored is not None
        assert isinstance(restored.schema, dict), (
            f"[FAIL] OPENAPI: schema が dict でなく {type(restored.schema)}"
        )
        assert restored.schema == schema_dict

    async def test_markdown_type_roundtrip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-012: MARKDOWN type → schema が plain text str でラウンドトリップ。"""
        schema_str = "# 設計書\n## 概要\nmarkdown テンプレート"
        restored = await self._save_and_restore(session_factory, TemplateType.MARKDOWN, schema_str)
        assert restored is not None
        assert isinstance(restored.schema, str), (
            f"[FAIL] MARKDOWN: schema が str でなく {type(restored.schema)}"
        )
        assert restored.schema == schema_str

    async def test_code_skeleton_type_roundtrip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-013: CODE_SKELETON type → schema が plain text str でラウンドトリップ。"""
        schema_str = "def main() -> None:\n    pass\n"
        restored = await self._save_and_restore(
            session_factory, TemplateType.CODE_SKELETON, schema_str
        )
        assert restored is not None
        assert isinstance(restored.schema, str), (
            f"[FAIL] CODE_SKELETON: schema が str でなく {type(restored.schema)}"
        )
        assert restored.schema == schema_str

    async def test_prompt_type_roundtrip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-014: PROMPT type → schema が plain text str でラウンドトリップ。"""
        schema_str = "あなたは {{role}} としてふるまいます。"
        restored = await self._save_and_restore(session_factory, TemplateType.PROMPT, schema_str)
        assert restored is not None
        assert isinstance(restored.schema, str), (
            f"[FAIL] PROMPT: schema が str でなく {type(restored.schema)}"
        )
        assert restored.schema == schema_str


# ---------------------------------------------------------------------------
# TC-IT-DTR-015: SemVer TEXT ラウンドトリップ (§確定 E)
# ---------------------------------------------------------------------------
class TestSemVerTextRoundTrip:
    """TC-IT-DTR-015: SemVer が "major.minor.patch" TEXT で格納 → from_str で復元。"""

    async def test_semver_roundtrip_via_text_column(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-015: version カラムが '3.14.159' TEXT かつ SemVer(3,14,159) に復元。

        raw SQL で格納値を確認（§確定 E: "major.minor.patch" TEXT）。
        """
        semver = SemVer(major=3, minor=14, patch=159)
        template = make_deliverable_template(version=semver)

        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        # raw SQL で格納値を確認（§確定 E: "3.14.159" TEXT）
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT version FROM deliverable_templates WHERE id = :id"),
                {"id": str(template.id).replace("-", "")},
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] == "3.14.159", (
            f"[FAIL] version TEXT が '3.14.159' でなく {row[0]!r}。\n"
            "Next: _to_row が str(template.version) を使っているか確認 (§確定 E)。"
        )

        # ORM 経由の復元確認
        async with session_factory() as session:
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)

        assert restored is not None
        assert restored.version == semver, (
            f"[FAIL] SemVer 復元不一致: {restored.version} != {semver}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DTR-016〜018: acceptance_criteria_json / composition_json A08 防御 (§確定 F)
# ---------------------------------------------------------------------------
class TestJsonFieldsA08Defense:
    """TC-IT-DTR-016 / 017 / 018: A08 Unsafe Deserialization — model_validate 経由を物理確認。

    §確定 F: json.loads → list[dict] → model_validate(d) の変換フローを強制。
    生 dict 直渡しは禁止。DB 直 INSERT で壊れた型でも Fail-Fast する。
    """

    async def test_acceptance_criteria_deserializes_via_model_validate(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-016: DB 生 JSON から復元した acceptance_criteria[0].id が UUID 型。

        model_validate 経由なら str → UUID 変換が保証される。
        生 dict 直渡しなら id が str のまま残る ── これが A08 防御の証拠。
        """
        criterion_id = uuid4()
        payload = json.dumps(
            [
                {
                    "id": str(criterion_id),
                    "description": "a08 defense test",
                    "required": True,
                }
            ]
        )
        template_id = uuid4().hex

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO deliverable_templates "
                    "(id, name, description, type, version, schema, "
                    "acceptance_criteria_json, composition_json) "
                    "VALUES (:id, :name, :desc, :type, :ver, :schema, :ac, :comp)"
                ),
                {
                    "id": template_id,
                    "name": "a08-ac-test",
                    "desc": "",
                    "type": "MARKDOWN",
                    "ver": "1.0.0",
                    "schema": "",
                    "ac": payload,
                    "comp": "[]",
                },
            )

        async with session_factory() as session:
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(
                UUID(template_id)
            )

        assert restored is not None
        assert len(restored.acceptance_criteria) == 1
        ac = restored.acceptance_criteria[0]
        assert isinstance(ac.id, UUID), (
            f"[FAIL] acceptance_criteria[0].id が UUID でなく {type(ac.id)}。\n"
            "Next: _from_row が AcceptanceCriterion.model_validate を経由しているか確認"
            " (§確定 F A08)。"
        )
        assert ac.id == criterion_id
        assert ac.description == "a08 defense test"
        assert ac.required is True

    async def test_composition_deserializes_via_model_validate(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-017: DB 生 JSON から復元した composition[0].template_id が UUID 型。"""
        ref_template_id = uuid4()
        payload = json.dumps(
            [
                {
                    "template_id": str(ref_template_id),
                    "minimum_version": {"major": 2, "minor": 1, "patch": 0},
                }
            ]
        )
        template_id = uuid4().hex

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO deliverable_templates "
                    "(id, name, description, type, version, schema, "
                    "acceptance_criteria_json, composition_json) "
                    "VALUES (:id, :name, :desc, :type, :ver, :schema, :ac, :comp)"
                ),
                {
                    "id": template_id,
                    "name": "a08-comp-test",
                    "desc": "",
                    "type": "MARKDOWN",
                    "ver": "1.0.0",
                    "schema": "",
                    "ac": "[]",
                    "comp": payload,
                },
            )

        async with session_factory() as session:
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(
                UUID(template_id)
            )

        assert restored is not None
        assert len(restored.composition) == 1
        ref = restored.composition[0]
        assert isinstance(ref.template_id, UUID), (
            f"[FAIL] composition[0].template_id が UUID でなく {type(ref.template_id)}。\n"
            "Next: _from_row が DeliverableTemplateRef.model_validate を経由しているか確認"
            " (§確定 F A08)。"
        )
        assert ref.template_id == ref_template_id
        assert ref.minimum_version == SemVer(major=2, minor=1, patch=0)

    async def test_invalid_acceptance_criteria_json_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-018: 不正な acceptance_criteria_json で ValidationError (A08 Fail-Fast)。

        template_id が UUID 形式でない壊れたペイロードを直接 INSERT し、
        find_by_id が ValidationError を raise することを確認。
        Repository が Exception を握り潰さない証拠。
        """
        bad_payload = json.dumps([{"id": "not-a-uuid", "description": "bad", "required": True}])
        template_id = uuid4().hex

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO deliverable_templates "
                    "(id, name, description, type, version, schema, "
                    "acceptance_criteria_json, composition_json) "
                    "VALUES (:id, :name, :desc, :type, :ver, :schema, :ac, :comp)"
                ),
                {
                    "id": template_id,
                    "name": "a08-fail-test",
                    "desc": "",
                    "type": "MARKDOWN",
                    "ver": "1.0.0",
                    "schema": "",
                    "ac": bad_payload,
                    "comp": "[]",
                },
            )

        with pytest.raises((pydantic.ValidationError, ValueError)):
            async with session_factory() as session:
                await SqliteDeliverableTemplateRepository(session).find_by_id(UUID(template_id))


# ---------------------------------------------------------------------------
# TC-IT-DTR-019: 全フィールド構造的等価 §確定 C ラウンドトリップ
# ---------------------------------------------------------------------------
class TestFullRoundTrip:
    """TC-IT-DTR-019: save → find_by_id で全フィールド構造的等価。"""

    async def test_full_round_trip_structural_equality(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-019: acceptance_criteria 2 件 + composition 1 件の template が同値。

        save → find_by_id で全フィールド構造的等価 (§確定 C)。
        """
        ac1 = make_acceptance_criterion(description="受入条件1", required=True)
        ac2 = make_acceptance_criterion(description="受入条件2", required=False)
        ref1 = make_deliverable_template_ref()
        version = SemVer(major=2, minor=3, patch=4)

        template = make_deliverable_template(
            name="roundtrip-template",
            description="テスト用の説明文",
            type_=TemplateType.MARKDOWN,
            schema="## テストスキーマ",
            acceptance_criteria=(ac1, ac2),
            composition=(ref1,),
            version=version,
        )

        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        async with session_factory() as session:
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)

        assert restored is not None
        assert restored.id == template.id
        assert restored.name == template.name
        assert restored.description == template.description
        assert restored.type == TemplateType.MARKDOWN
        assert restored.schema == "## テストスキーマ"
        assert restored.version == SemVer(major=2, minor=3, patch=4)
        assert len(restored.acceptance_criteria) == 2
        assert restored.acceptance_criteria[0].id == ac1.id
        assert restored.acceptance_criteria[0].description == "受入条件1"
        assert restored.acceptance_criteria[0].required is True
        assert restored.acceptance_criteria[1].id == ac2.id
        assert restored.acceptance_criteria[1].description == "受入条件2"
        assert restored.acceptance_criteria[1].required is False
        assert len(restored.composition) == 1
        assert restored.composition[0].template_id == ref1.template_id
        assert restored.composition[0].minimum_version == ref1.minimum_version
