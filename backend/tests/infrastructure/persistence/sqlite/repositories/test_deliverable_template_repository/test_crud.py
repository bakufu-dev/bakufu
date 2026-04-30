"""DeliverableTemplate Repository CRUD + 変換契約テスト (Issue #119).

TC-IT-DTR-001〜019:
- Protocol 充足 (001/002)
- find_by_id / find_all / save 基本 CRUD (003〜009)
- schema type 判別 5 経路 §確定 D (010〜014)
- SemVer TEXT ラウンドトリップ §確定 E (015)
- acceptance_criteria_json / composition_json A08 防御 §確定 F (016〜018)
- 全フィールド構造的等価 §確定 C (019)

§確定 B / C / D / E / F:
  docs/features/deliverable-template/repository/detailed-design.md
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
import pydantic
from bakufu.application.ports.deliverable_template_repository import (
    DeliverableTemplateRepository,
)
from bakufu.domain.value_objects.enums import TemplateType
from bakufu.domain.value_objects.template_vos import SemVer
from bakufu.infrastructure.persistence.sqlite.repositories.deliverable_template_repository import (
    SqliteDeliverableTemplateRepository,
)
from sqlalchemy import text

from bakufu.domain.deliverable_template.deliverable_template import (
    DeliverableTemplate as _DeliverableTemplate,
)
from tests.factories.deliverable_template import (
    ValidStubValidator,
    make_acceptance_criterion,
    make_deliverable_template,
    make_deliverable_template_ref,
    make_semver,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-DTR-001/002: Protocol 定義 + 充足 (§確定 A)
# ---------------------------------------------------------------------------
class TestDeliverableTemplateRepositoryProtocol:
    """TC-IT-DTR-001 / 002: Protocol サーフェス + duck typing 充足。"""

    async def test_protocol_declares_three_async_methods(self) -> None:
        """TC-IT-DTR-001: Protocol が find_by_id / find_all / save を持つ。"""
        assert hasattr(DeliverableTemplateRepository, "find_by_id")
        assert hasattr(DeliverableTemplateRepository, "find_all")
        assert hasattr(DeliverableTemplateRepository, "save")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-002: SqliteDeliverableTemplateRepository が Protocol duck typing を満たす。"""
        async with session_factory() as session:
            repo: DeliverableTemplateRepository = SqliteDeliverableTemplateRepository(
                session
            )
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "find_all")
            assert hasattr(repo, "save")


# ---------------------------------------------------------------------------
# TC-IT-DTR-003/004: find_by_id
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-IT-DTR-003 / 004: find_by_id は保存済みを返し、不在は None を返す。"""

    async def test_find_by_id_returns_saved_template(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-003: save 後に find_by_id で取得できる。"""
        template = make_deliverable_template(name="test-template")

        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        async with session_factory() as session:
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(
                template.id
            )

        assert restored is not None
        assert restored.id == template.id
        assert restored.name == "test-template"

    async def test_find_by_id_returns_none_for_unknown_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-004: 未知の id は None を返す。例外を raise しない。"""
        async with session_factory() as session:
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(
                uuid4()
            )
        assert result is None


# ---------------------------------------------------------------------------
# TC-IT-DTR-005/006: find_all ORDER BY name ASC (§確定 I)
# ---------------------------------------------------------------------------
class TestFindAll:
    """TC-IT-DTR-005 / 006: find_all は ORDER BY name ASC で返す。0 件は空リスト。"""

    async def test_find_all_returns_order_by_name_asc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-005: 3 件を name 昇順で返す (§確定 I)。"""
        t_z = make_deliverable_template(name="Z-template")
        t_a = make_deliverable_template(name="A-template")
        t_m = make_deliverable_template(name="M-template")

        async with session_factory() as session, session.begin():
            repo = SqliteDeliverableTemplateRepository(session)
            await repo.save(t_z)
            await repo.save(t_a)
            await repo.save(t_m)

        async with session_factory() as session:
            results = await SqliteDeliverableTemplateRepository(session).find_all()

        assert len(results) == 3
        assert [r.name for r in results] == ["A-template", "M-template", "Z-template"]

    async def test_find_all_returns_empty_list_when_db_empty(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-006: DB 空なら空リストを返す。例外を raise しない。"""
        async with session_factory() as session:
            results = await SqliteDeliverableTemplateRepository(session).find_all()
        assert results == []


# ---------------------------------------------------------------------------
# TC-IT-DTR-007/008: save UPSERT (§確定 B)
# ---------------------------------------------------------------------------
class TestSaveUpsert:
    """TC-IT-DTR-007 / 008: save は新規 INSERT と既存上書き UPSERT を正しく行う。"""

    async def test_save_inserts_new_row(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-007: save 後に raw SQL で行の存在と name を確認。"""
        template = make_deliverable_template(name="insert-test")

        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        async with session_factory() as session:
            result = await session.execute(
                text("SELECT name FROM deliverable_templates WHERE id = :id"),
                {"id": str(template.id).replace("-", "")},
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] == "insert-test"

    async def test_save_upserts_existing_row(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-008: 同 id の template を更新 name で再 save → find_by_id が新 name を返す。"""
        template = make_deliverable_template(name="original-name")

        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        updated = make_deliverable_template(
            template_id=template.id, name="updated-name"
        )
        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(
                template.id
            )

        assert restored is not None
        assert restored.name == "updated-name"


# ---------------------------------------------------------------------------
# TC-IT-DTR-009: Tx 境界 (§確定 B)
# ---------------------------------------------------------------------------
class TestTxBoundary:
    """TC-IT-DTR-009: commit / rollback 両経路。Repository は明示 commit/rollback しない。"""

    async def test_commit_path_persists_template(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-009a: session.begin() ブロック退出で commit → 永続化される。"""
        template = make_deliverable_template()

        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        async with session_factory() as session:
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(
                template.id
            )
        assert result is not None

    async def test_rollback_path_drops_template(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-009b: begin() ブロック内例外で rollback → 行が消える。"""

        class _Boom(Exception):
            pass

        template = make_deliverable_template()

        with pytest.raises(_Boom):
            async with session_factory() as session, session.begin():
                await SqliteDeliverableTemplateRepository(session).save(template)
                raise _Boom

        async with session_factory() as session:
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(
                template.id
            )
        assert result is None, (
            "[FAIL] Rollback 経路で template 行が残存。\n"
            "Next: SqliteDeliverableTemplateRepository.save() は "
            "session.commit() を呼んではならない (§確定 B)。"
        )

    async def test_repository_does_not_commit_implicitly(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-009c: begin() なし save は永続化されない（暗黙 commit 禁止）。"""
        template = make_deliverable_template()

        async with session_factory() as session:
            await SqliteDeliverableTemplateRepository(session).save(template)
            # commit() を呼ばずに退出 → AsyncSession.__aexit__ が rollback

        async with session_factory() as session:
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(
                template.id
            )
        assert result is None, (
            "[FAIL] 暗黙 commit で template 行が永続化された。"
            "Repository は session.commit() を呼ばないこと (§確定 B)。"
        )


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
            _DeliverableTemplate._validator = ValidStubValidator()
        try:
            template = make_deliverable_template(type_=type_, schema=schema)
            async with session_factory() as session, session.begin():
                await SqliteDeliverableTemplateRepository(session).save(template)
            async with session_factory() as session:
                return await SqliteDeliverableTemplateRepository(session).find_by_id(
                    template.id
                )
        finally:
            if needs_validator:
                _DeliverableTemplate._validator = None  # type: ignore[assignment]

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
        restored = await self._save_and_restore(
            session_factory, TemplateType.OPENAPI, schema_dict
        )
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
        restored = await self._save_and_restore(
            session_factory, TemplateType.MARKDOWN, schema_str
        )
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
        restored = await self._save_and_restore(
            session_factory, TemplateType.PROMPT, schema_str
        )
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
        """TC-IT-DTR-015: raw SQL で version カラムが '3.14.159' 文字列であることと
        find_by_id で SemVer(3,14,159) に復元されることを物理確認。
        """
        semver = SemVer(major=3, minor=14, patch=159)
        template = make_deliverable_template(version=semver)

        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        # raw SQL で格納値を確認（§確定 E: "3.14.159" TEXT）
        async with session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT version FROM deliverable_templates WHERE id = :id"
                ),
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
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(
                template.id
            )

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
        """TC-IT-DTR-018: 不正な acceptance_criteria_json で ValidationError / ValueError (A08 Fail-Fast)。

        template_id が UUID 形式でない壊れたペイロードを直接 INSERT し、
        find_by_id が ValidationError を raise することを確認。
        Repository が Exception を握り潰さない証拠。
        """
        bad_payload = json.dumps(
            [{"id": "not-a-uuid", "description": "bad", "required": True}]
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
                await SqliteDeliverableTemplateRepository(session).find_by_id(
                    UUID(template_id)
                )


# ---------------------------------------------------------------------------
# TC-IT-DTR-019: 全フィールド構造的等価 §確定 C ラウンドトリップ
# ---------------------------------------------------------------------------
class TestFullRoundTrip:
    """TC-IT-DTR-019: save → find_by_id で全フィールド構造的等価。"""

    async def test_full_round_trip_structural_equality(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-019: acceptance_criteria 2 件 + composition 1 件の template が同値でラウンドトリップ。"""
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
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(
                template.id
            )

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
