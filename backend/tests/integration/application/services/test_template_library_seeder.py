"""TemplateLibrarySeeder 結合テスト（TC-IT-TL-001〜009）。

Issue: #124
設計書: docs/features/deliverable-template/template-library/test-design.md
対応要件: REQ-TL-001〜004 / §確定 D / §確定 E / §確定 F / REQ-TL-002

DB: in-memory SQLite 実接続（`tl_session_factory` フィクスチャ）。
TC-IT-TL-007 のみ Bootstrap を使用（Alembic 実行）。
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bakufu.application.services.template_library.definitions import (
    WELL_KNOWN_TEMPLATES,
)
from bakufu.application.services.template_library.seeder import TemplateLibrarySeeder
from bakufu.domain.value_objects.enums import Role
from bakufu.infrastructure.persistence.sqlite.repositories.deliverable_template_repository import (
    SqliteDeliverableTemplateRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.role_profile_repository import (
    SqliteRoleProfileRepository,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories.empire import make_empire

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


async def _find_all_templates(
    session_factory: async_sessionmaker[AsyncSession],
) -> list:
    """別セッションで全テンプレートを取得する（Tx 分離確認用）。"""
    async with session_factory() as session:
        repo = SqliteDeliverableTemplateRepository(session)
        return await repo.find_all()


async def _find_all_role_profiles_by_empire(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: uuid.UUID,
) -> list:
    """別セッションで empire の全 RoleProfile を取得する。"""
    async with session_factory() as session:
        repo = SqliteRoleProfileRepository(session)
        return await repo.find_all_by_empire(empire_id)


async def _create_empire(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Empire を DB に保存し empire_id を返す。

    role_profiles.empire_id FK（empires.id）を満たすために必要。
    """
    emp = make_empire(empire_id=empire_id)
    async with session_factory() as session, session.begin():
        repo = SqliteEmpireRepository(session)
        await repo.save(emp)
    return emp.id


# ---------------------------------------------------------------------------
# TC-IT-TL-001: 初回 seed で 12 件保存
# ---------------------------------------------------------------------------


class TestSeedGlobalTemplatesFirstRun:
    """TC-IT-TL-001: seed_global_templates() 初回で 12 件全件が DB に保存される。"""

    async def test_first_seed_inserts_12_templates(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )
        await seeder.seed_global_templates(tl_session_factory)

        templates = await _find_all_templates(tl_session_factory)
        assert len(templates) == 12

    async def test_all_ids_match_well_known(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )
        await seeder.seed_global_templates(tl_session_factory)

        templates = await _find_all_templates(tl_session_factory)
        db_ids = {t.id for t in templates}
        expected_ids = {t.id for t in WELL_KNOWN_TEMPLATES}
        assert db_ids == expected_ids


# ---------------------------------------------------------------------------
# TC-IT-TL-002: 2 回実行（冪等性）
# ---------------------------------------------------------------------------


class TestSeedGlobalTemplatesIdempotency:
    """TC-IT-TL-002: seed_global_templates() を 2 回呼んでもレコード数が 12 件のまま。"""

    async def test_double_seed_stays_at_12(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )
        await seeder.seed_global_templates(tl_session_factory)
        await seeder.seed_global_templates(tl_session_factory)

        templates = await _find_all_templates(tl_session_factory)
        assert len(templates) == 12


# ---------------------------------------------------------------------------
# TC-IT-TL-003: DB レコードと definitions.py の内容一致
# ---------------------------------------------------------------------------


class TestSeedGlobalTemplatesContentMatch:
    """TC-IT-TL-003: seed 後の DB レコードが WELL_KNOWN_TEMPLATES と全フィールドで一致。"""

    async def test_all_fields_match_definitions(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )
        await seeder.seed_global_templates(tl_session_factory)

        for expected in WELL_KNOWN_TEMPLATES:
            async with tl_session_factory() as session:
                repo = SqliteDeliverableTemplateRepository(session)
                actual = await repo.find_by_id(expected.id)

            assert actual is not None, f"template {expected.id} not found in DB"
            assert actual.name == expected.name
            assert actual.description == expected.description
            assert actual.type == expected.type
            assert actual.version == expected.version
            assert actual.schema == expected.schema
            assert actual.acceptance_criteria == expected.acceptance_criteria


# ---------------------------------------------------------------------------
# TC-IT-TL-004: 初回 Empire RoleProfile 適用（4 件保存）
# ---------------------------------------------------------------------------


class TestSeedRoleProfilesFirstRun:
    """TC-IT-TL-004: seed_role_profiles_for_empire() 初回で 4 件の RoleProfile が保存される。"""

    async def test_first_call_saves_4_profiles(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        empire_id = await _create_empire(tl_session_factory)
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )
        await seeder.seed_role_profiles_for_empire(empire_id, tl_session_factory)

        profiles = await _find_all_role_profiles_by_empire(tl_session_factory, empire_id)
        assert len(profiles) == 4

    async def test_all_four_roles_present(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        empire_id = await _create_empire(tl_session_factory)
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )
        await seeder.seed_role_profiles_for_empire(empire_id, tl_session_factory)

        profiles = await _find_all_role_profiles_by_empire(tl_session_factory, empire_id)
        roles = {p.role for p in profiles}
        assert roles == {Role.LEADER, Role.DEVELOPER, Role.TESTER, Role.REVIEWER}


# ---------------------------------------------------------------------------
# TC-IT-TL-005: RoleProfile skip 冪等性（2 回呼び出し）
# ---------------------------------------------------------------------------


class TestSeedRoleProfilesIdempotency:
    """TC-IT-TL-005: seed_role_profiles_for_empire() 2 回呼んでも件数が増えない（skip 戦略）。"""

    async def test_double_call_stays_at_4(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        empire_id = await _create_empire(tl_session_factory)
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )
        await seeder.seed_role_profiles_for_empire(empire_id, tl_session_factory)
        await seeder.seed_role_profiles_for_empire(empire_id, tl_session_factory)

        profiles = await _find_all_role_profiles_by_empire(tl_session_factory, empire_id)
        assert len(profiles) == 4


# ---------------------------------------------------------------------------
# TC-IT-TL-006: CEO 手動設定 RoleProfile は上書きされない
# ---------------------------------------------------------------------------


class TestSeedRoleProfilesSkipExisting:
    """TC-IT-TL-006: CEO が DEVELOPER RoleProfile を手動設定済みの場合、上書きされない。"""

    async def test_manual_developer_profile_not_overwritten(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        from bakufu.domain.deliverable_template.role_profile import RoleProfile
        from bakufu.domain.value_objects.template_vos import DeliverableTemplateRef, SemVer

        empire_id = await _create_empire(tl_session_factory)
        # CEO 手動設定: DEVELOPER に独自の template_ref（PRESET と異なる UUID）を設定
        custom_template_id = uuid.uuid4()
        custom_ref = DeliverableTemplateRef(
            template_id=custom_template_id,
            minimum_version=SemVer(major=2, minor=0, patch=0),
        )
        profile_id = uuid.uuid4()
        custom_profile = RoleProfile(
            id=profile_id,
            empire_id=empire_id,
            role=Role.DEVELOPER,
            deliverable_template_refs=(custom_ref,),
        )

        async with tl_session_factory() as session, session.begin():
            repo = SqliteRoleProfileRepository(session)
            await repo.save(custom_profile)

        # seed を呼ぶ → DEVELOPER は既存のため skip
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )
        await seeder.seed_role_profiles_for_empire(empire_id, tl_session_factory)

        # DEVELOPER は手動設定値のまま
        async with tl_session_factory() as session:
            repo = SqliteRoleProfileRepository(session)
            actual = await repo.find_by_empire_and_role(empire_id, Role.DEVELOPER)

        assert actual is not None
        assert len(actual.deliverable_template_refs) == 1
        assert actual.deliverable_template_refs[0].template_id == custom_template_id
        assert actual.deliverable_template_refs[0].minimum_version.major == 2


# ---------------------------------------------------------------------------
# TC-IT-TL-007: Bootstrap Stage 3b の実行順序
# ---------------------------------------------------------------------------


class TestBootstrapStage3bOrder:
    """TC-IT-TL-007: Bootstrap.run() で Stage 3b が Stage 3 後・Stage 4 前に実行される。"""

    async def test_stage_3b_runs_between_stage_3_and_stage_4(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        _reset_data_dir: None,
        _clear_handler_registry: None,
    ) -> None:
        from bakufu.infrastructure.bootstrap import Bootstrap
        from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head

        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))

        # TemplateLibrarySeeder.seed_global_templates を AsyncMock でスタブ化
        # 実際の DB 書き込みは本 TC の関心外
        with patch(
            "bakufu.application.services.template_library.seeder.TemplateLibrarySeeder"
            ".seed_global_templates",
            new_callable=AsyncMock,
            return_value=12,
        ):
            boot = Bootstrap(migration_runner=run_upgrade_head)
            with caplog.at_level(logging.INFO):
                await boot.run()

            try:
                info_messages = [
                    r.getMessage() for r in caplog.records if r.levelname in ("INFO", "WARNING")
                ]

                # (1) stage 3b がログに存在する
                stage_3b_msgs = [m for m in info_messages if "stage 3b" in m]
                assert stage_3b_msgs, "stage 3b のログが存在しない"

                # (2) stage 3 → stage 3b → stage 4 の順序確認
                def _first_index(keyword: str) -> int:
                    for i, m in enumerate(info_messages):
                        if keyword in m:
                            return i
                    return -1

                idx_3 = _first_index("stage 3/8")
                idx_3b = _first_index("stage 3b")
                idx_4 = _first_index("stage 4/8")

                assert idx_3 != -1, "stage 3/8 のログが存在しない"
                assert idx_3b != -1, "stage 3b のログが存在しない"
                assert idx_4 != -1, "stage 4/8 のログが存在しない"

                assert idx_3 < idx_3b, (
                    f"stage 3({idx_3}) は stage 3b({idx_3b}) より前に実行されるべき"
                )
                assert idx_3b < idx_4, (
                    f"stage 3b({idx_3b}) は stage 4({idx_4}) より前に実行されるべき"
                )

            finally:
                if boot.app_engine is not None:
                    await boot.app_engine.dispose()


# ---------------------------------------------------------------------------
# TC-IT-TL-008: seed 失敗時の全件ロールバック（all-or-nothing）
# ---------------------------------------------------------------------------


class TestSeedGlobalTemplatesRollback:
    """TC-IT-TL-008: UPSERT 途中でエラーが発生した場合に全件ロールバック。"""

    async def test_partial_failure_rolls_back_all(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """7 件目の save() で SQLAlchemyError → 全件ロールバック。別セッションで 0 件確認。"""
        call_count = 0
        original_save = SqliteDeliverableTemplateRepository.save

        async def _save_with_fail_on_7th(
            self_repo: SqliteDeliverableTemplateRepository, template: object
        ) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 7:
                raise SQLAlchemyError("TC-IT-TL-008: 意図的な 7 件目エラー")
            await original_save(self_repo, template)  # type: ignore[arg-type]

        with patch.object(
            SqliteDeliverableTemplateRepository,
            "save",
            new=_save_with_fail_on_7th,
        ):
            seeder = TemplateLibrarySeeder(
                SqliteDeliverableTemplateRepository,
                SqliteRoleProfileRepository,
            )
            with pytest.raises(SQLAlchemyError):
                await seeder.seed_global_templates(tl_session_factory)

        # Tx ロールバックにより 1〜6 件目の書き込みも全件消える
        templates = await _find_all_templates(tl_session_factory)
        assert len(templates) == 0, f"ロールバック後に {len(templates)} 件残存（期待: 0 件）"

    async def test_error_propagates_as_sqlalchemy_error(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """SQLAlchemyError が呼び出し元に伝播する（BakufuConfigError ラップなし）。"""

        async def _always_fail(
            self_repo: SqliteDeliverableTemplateRepository, template: object
        ) -> None:
            raise SQLAlchemyError("TC-IT-TL-008: 即時エラー")

        with patch.object(
            SqliteDeliverableTemplateRepository,
            "save",
            new=_always_fail,
        ):
            seeder = TemplateLibrarySeeder(
                SqliteDeliverableTemplateRepository,
                SqliteRoleProfileRepository,
            )
            with pytest.raises(SQLAlchemyError):
                await seeder.seed_global_templates(tl_session_factory)


# ---------------------------------------------------------------------------
# TC-IT-TL-009: §確定 D — 再 seed で手動編集内容が上書きされる
# ---------------------------------------------------------------------------


class TestSeedGlobalTemplatesOverrideManualEdit:
    """TC-IT-TL-009: §確定 D — 手動編集済みテンプレートが再 seed で definitions.py 定義に戻る。"""

    async def test_manual_edit_overwritten_by_reseed(
        self,
        tl_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        seeder = TemplateLibrarySeeder(
            SqliteDeliverableTemplateRepository,
            SqliteRoleProfileRepository,
        )

        # (1) 初回 seed
        await seeder.seed_global_templates(tl_session_factory)

        # (2) 最初のテンプレートを手動で書き換え（CEO が直接 DB 編集した想定）
        target = WELL_KNOWN_TEMPLATES[0]
        async with tl_session_factory() as session, session.begin():
            repo = SqliteDeliverableTemplateRepository(session)
            fetched = await repo.find_by_id(target.id)
            assert fetched is not None

            # model_validate で name / schema を改ざん
            from bakufu.domain.deliverable_template.deliverable_template import (
                DeliverableTemplate,
            )

            tampered = DeliverableTemplate.model_validate(
                {
                    "id": fetched.id,
                    "name": "手動改ざん名",
                    "description": fetched.description,
                    "type": fetched.type,
                    "schema": "手動改ざんスキーマ",
                    "acceptance_criteria": [],
                    "version": {
                        "major": fetched.version.major,
                        "minor": fetched.version.minor,
                        "patch": fetched.version.patch,
                    },
                    "composition": [],
                }
            )
            await repo.save(tampered)

        # 手動編集が反映されていることを確認
        async with tl_session_factory() as session:
            repo = SqliteDeliverableTemplateRepository(session)
            after_edit = await repo.find_by_id(target.id)
        assert after_edit is not None
        assert after_edit.name == "手動改ざん名"
        assert after_edit.schema == "手動改ざんスキーマ"

        # (3) 再 seed（アプリ再起動模倣）
        await seeder.seed_global_templates(tl_session_factory)

        # (4) definitions.py 定義に戻っていることを確認（§確定 D）
        async with tl_session_factory() as session:
            repo = SqliteDeliverableTemplateRepository(session)
            after_reseed = await repo.find_by_id(target.id)

        assert after_reseed is not None
        assert after_reseed.name == target.name, (
            f"reseed 後の name が定義値に戻っていない: {after_reseed.name!r} != {target.name!r}"
        )
        assert after_reseed.schema == target.schema, "reseed 後の schema が定義値に戻っていない"
