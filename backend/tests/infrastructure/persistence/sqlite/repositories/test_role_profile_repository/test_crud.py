"""RoleProfile Repository CRUD + UNIQUE 制約 + A08 防御テスト (Issue #119).

TC-IT-RPR-001〜015:
- Protocol 充足 (001/002)
- find_by_empire_and_role / find_all_by_empire / save 基本 CRUD (003〜009)
- deliverable_template_refs_json A08 防御 §確定 G (010/011)
- UNIQUE(empire_id, role) 制約違反 §確定 H (012/013)
- FK CASCADE DELETE (014)
- 全フィールド構造的等価 §確定 C (015)

§確定 B / C / G / H / I:
  docs/features/deliverable-template/repository/detailed-design.md

前提: role_profiles.empire_id → empires.id FK のため、
      各テストで empire 行を empires テーブルに先行 INSERT すること。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pydantic
import pytest
from bakufu.application.ports.role_profile_repository import RoleProfileRepository
from bakufu.domain.value_objects.enums import Role
from bakufu.domain.value_objects.template_vos import SemVer
from bakufu.infrastructure.persistence.sqlite.repositories.role_profile_repository import (
    SqliteRoleProfileRepository,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.factories.deliverable_template import (
    make_deliverable_template_ref,
    make_role_profile,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# ヘルパ: empire 行を先行 INSERT (role_profiles FK 制約を満たすために必要)
# ---------------------------------------------------------------------------
async def _seed_empire(
    session_factory: async_sessionmaker[AsyncSession],
    empire_id: UUID,
) -> None:
    """empires テーブルに最小限の行を INSERT する。

    role_profiles.empire_id → empires.id FK を満たすために必要。
    """
    async with session_factory() as session, session.begin():
        await session.execute(
            text("INSERT OR IGNORE INTO empires (id, name) VALUES (:id, :name)"),
            {"id": empire_id.hex, "name": "test-empire"},
        )


# ---------------------------------------------------------------------------
# TC-IT-RPR-001/002: Protocol 定義 + 充足 (§確定 A)
# ---------------------------------------------------------------------------
class TestRoleProfileRepositoryProtocol:
    """TC-IT-RPR-001 / 002: Protocol サーフェス + duck typing 充足。"""

    async def test_protocol_declares_three_async_methods(self) -> None:
        """TC-IT-RPR-001: Protocol が 3 メソッドを持つ。"""
        assert hasattr(RoleProfileRepository, "find_by_empire_and_role")
        assert hasattr(RoleProfileRepository, "find_all_by_empire")
        assert hasattr(RoleProfileRepository, "save")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-002: SqliteRoleProfileRepository が Protocol duck typing を満たす。"""
        async with session_factory() as session:
            repo: RoleProfileRepository = SqliteRoleProfileRepository(session)
            assert hasattr(repo, "find_by_empire_and_role")
            assert hasattr(repo, "find_all_by_empire")
            assert hasattr(repo, "save")


# ---------------------------------------------------------------------------
# TC-IT-RPR-003/004: find_by_empire_and_role
# ---------------------------------------------------------------------------
class TestFindByEmpireAndRole:
    """TC-IT-RPR-003 / 004: find_by_empire_and_role は保存済みを返し、不在は None。"""

    async def test_find_by_empire_and_role_returns_saved_profile(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-003: save 後に find_by_empire_and_role で取得できる。"""
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        profile = make_role_profile(empire_id=empire_id, role=Role.DEVELOPER)

        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile)

        async with session_factory() as session:
            restored = await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                empire_id, Role.DEVELOPER
            )

        assert restored is not None
        assert restored.id == profile.id
        assert restored.role == Role.DEVELOPER

    async def test_find_by_empire_and_role_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-004: 不在の (empire_id, role) は None を返す。例外を raise しない。"""
        async with session_factory() as session:
            result = await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                uuid4(), Role.DEVELOPER
            )
        assert result is None


# ---------------------------------------------------------------------------
# TC-IT-RPR-005/006: find_all_by_empire ORDER BY role ASC (§確定 I)
# ---------------------------------------------------------------------------
class TestFindAllByEmpire:
    """TC-IT-RPR-005 / 006: find_all_by_empire は ORDER BY role ASC。別 empire 行は除外。"""

    async def test_find_all_by_empire_returns_order_by_role_asc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-005: 3 Role を role 昇順で返す (§確定 I)。"""
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        p_tester = make_role_profile(empire_id=empire_id, role=Role.TESTER)
        p_developer = make_role_profile(empire_id=empire_id, role=Role.DEVELOPER)
        p_reviewer = make_role_profile(empire_id=empire_id, role=Role.REVIEWER)

        async with session_factory() as session, session.begin():
            repo = SqliteRoleProfileRepository(session)
            await repo.save(p_tester)
            await repo.save(p_developer)
            await repo.save(p_reviewer)

        async with session_factory() as session:
            results = await SqliteRoleProfileRepository(session).find_all_by_empire(empire_id)

        assert len(results) == 3
        # Role StrEnum: "DEVELOPER" < "REVIEWER" < "TESTER" (ASCII 昇順)
        assert [r.role for r in results] == [
            Role.DEVELOPER,
            Role.REVIEWER,
            Role.TESTER,
        ]

    async def test_find_all_by_empire_excludes_other_empire_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-006: 別 empire の行は含まれない。"""
        empire_a = uuid4()
        empire_b = uuid4()
        await _seed_empire(session_factory, empire_a)
        await _seed_empire(session_factory, empire_b)

        p_a = make_role_profile(empire_id=empire_a, role=Role.DEVELOPER)
        p_b = make_role_profile(empire_id=empire_b, role=Role.DEVELOPER)

        async with session_factory() as session, session.begin():
            repo = SqliteRoleProfileRepository(session)
            await repo.save(p_a)
            await repo.save(p_b)

        async with session_factory() as session:
            results = await SqliteRoleProfileRepository(session).find_all_by_empire(empire_a)

        assert len(results) == 1
        assert results[0].id == p_a.id


# ---------------------------------------------------------------------------
# TC-IT-RPR-007/008: save UPSERT (§確定 B)
# ---------------------------------------------------------------------------
class TestRoleProfileSaveUpsert:
    """TC-IT-RPR-007 / 008: save は新規 INSERT と既存上書き UPSERT を正しく行う。"""

    async def test_save_inserts_new_row(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-007: save 後に raw SQL で行の存在と role を確認。"""
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        profile = make_role_profile(empire_id=empire_id, role=Role.TESTER)

        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile)

        async with session_factory() as session:
            result = await session.execute(
                text("SELECT role FROM role_profiles WHERE id = :id"),
                {"id": str(profile.id).replace("-", "")},
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] == "TESTER"

    async def test_save_upserts_existing_row(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-008: 同 id に新 deliverable_template_refs で再 save。

        更新された refs が返ること (UPSERT 上書き確認、§確定 B)。
        """
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        profile = make_role_profile(
            empire_id=empire_id,
            role=Role.REVIEWER,
            deliverable_template_refs=(),
        )

        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile)

        ref = make_deliverable_template_ref()
        updated = make_role_profile(
            profile_id=profile.id,
            empire_id=empire_id,
            role=Role.REVIEWER,
            deliverable_template_refs=(ref,),
        )
        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                empire_id, Role.REVIEWER
            )

        assert restored is not None
        assert len(restored.deliverable_template_refs) == 1
        assert restored.deliverable_template_refs[0].template_id == ref.template_id


# ---------------------------------------------------------------------------
# TC-IT-RPR-009: Tx 境界 (§確定 B)
# ---------------------------------------------------------------------------
class TestRoleProfileTxBoundary:
    """TC-IT-RPR-009: commit / rollback 両経路。Repository は明示 commit/rollback しない。"""

    async def test_commit_path_persists_profile(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-009a: begin() ブロック退出で commit → 永続化される。"""
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)
        profile = make_role_profile(empire_id=empire_id)

        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile)

        async with session_factory() as session:
            result = await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                empire_id, profile.role
            )
        assert result is not None

    async def test_rollback_path_drops_profile(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-009b: begin() ブロック内例外で rollback → 行が消える。"""

        class _BoomError(Exception):
            pass

        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)
        profile = make_role_profile(empire_id=empire_id)

        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteRoleProfileRepository(session).save(profile)
                raise _BoomError

        async with session_factory() as session:
            result = await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                empire_id, profile.role
            )
        assert result is None, (
            "[FAIL] Rollback 経路で role_profile 行が残存。"
            "Repository は session.commit() を呼ばないこと (§確定 B)。"
        )


# ---------------------------------------------------------------------------
# TC-IT-RPR-010/011: deliverable_template_refs_json A08 防御 (§確定 G)
# ---------------------------------------------------------------------------
class TestDeliverableTemplateRefsA08Defense:
    """TC-IT-RPR-010 / 011: A08 防御 — model_validate 経由を物理確認 + Fail-Fast。"""

    async def test_refs_deserialize_via_model_validate(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-010: DB 生 JSON から復元した refs[0].template_id が UUID 型。"""
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        ref_template_id = uuid4()
        payload = json.dumps(
            [
                {
                    "template_id": str(ref_template_id),
                    "minimum_version": {"major": 2, "minor": 1, "patch": 0},
                }
            ]
        )
        profile_id = uuid4().hex

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO role_profiles "
                    "(id, empire_id, role, deliverable_template_refs_json) "
                    "VALUES (:id, :empire_id, :role, :refs)"
                ),
                {
                    "id": profile_id,
                    "empire_id": empire_id.hex,
                    "role": "DEVELOPER",
                    "refs": payload,
                },
            )

        async with session_factory() as session:
            restored = await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                empire_id, Role.DEVELOPER
            )

        assert restored is not None
        assert len(restored.deliverable_template_refs) == 1
        ref = restored.deliverable_template_refs[0]
        assert isinstance(ref.template_id, UUID), (
            f"[FAIL] refs[0].template_id が UUID でなく {type(ref.template_id)}。\n"
            "Next: _from_row が DeliverableTemplateRef.model_validate を経由しているか確認"
            " (§確定 G A08)。"
        )
        assert ref.template_id == ref_template_id
        assert ref.minimum_version == SemVer(major=2, minor=1, patch=0)

    async def test_invalid_refs_json_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-011: 不正な deliverable_template_refs_json で ValidationError。

        A08 Fail-Fast 防御 (§確定 G): UUID 形式でないペイロードで raise を確認。
        """
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        bad_payload = json.dumps(
            [
                {
                    "template_id": "not-a-uuid",
                    "minimum_version": {"major": 1, "minor": 0, "patch": 0},
                }
            ]
        )
        profile_id = uuid4().hex

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO role_profiles "
                    "(id, empire_id, role, deliverable_template_refs_json) "
                    "VALUES (:id, :empire_id, :role, :refs)"
                ),
                {
                    "id": profile_id,
                    "empire_id": empire_id.hex,
                    "role": "REVIEWER",
                    "refs": bad_payload,
                },
            )

        with pytest.raises((pydantic.ValidationError, ValueError)):
            async with session_factory() as session:
                await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                    empire_id, Role.REVIEWER
                )


# ---------------------------------------------------------------------------
# TC-IT-RPR-012/013: UNIQUE(empire_id, role) 制約 (§確定 H)
# ---------------------------------------------------------------------------
class TestUniqueEmpireRoleConstraint:
    """TC-IT-RPR-012 / 013: UNIQUE(empire_id, role) 違反経路と正常 UPSERT を物理確認。"""

    async def test_duplicate_empire_role_with_different_id_raises_integrity_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-012: 同一 (empire_id, role) 別 id の save が IntegrityError を raise する。

        DB の UNIQUE(empire_id, role) 制約が最終防衛線として機能することを物理確認
        (§確定 H)。
        """
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        # 1 件目 (id=A, empire_id, role=DEVELOPER)
        profile_a = make_role_profile(empire_id=empire_id, role=Role.DEVELOPER)
        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile_a)

        # 2 件目 (**別 id**, 同 empire_id, 同 role) → UNIQUE 違反
        profile_b = make_role_profile(empire_id=empire_id, role=Role.DEVELOPER)
        assert profile_b.id != profile_a.id  # 別 id であることを保証

        with pytest.raises(IntegrityError, match="UNIQUE"):
            async with session_factory() as session, session.begin():
                await SqliteRoleProfileRepository(session).save(profile_b)

    async def test_same_id_upsert_does_not_raise(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-013: 同一 id の UPSERT 再呼び出しは IntegrityError しない (§確定 B)。"""
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        profile = make_role_profile(empire_id=empire_id, role=Role.UX)
        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile)

        # 同 id 再 save (UPSERT) → 例外なし
        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile)

        async with session_factory() as session:
            result = await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                empire_id, Role.UX
            )
        assert result is not None
        assert result.id == profile.id


# ---------------------------------------------------------------------------
# TC-IT-RPR-014: FK CASCADE DELETE
# ---------------------------------------------------------------------------
class TestFkCascadeDelete:
    """TC-IT-RPR-014: empires 行削除で role_profiles が CASCADE 削除される。"""

    async def test_empire_delete_cascades_to_role_profiles(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-014: DELETE FROM empires で role_profiles が CASCADE 削除される。

        role_profiles.empire_id → empires.id ON DELETE CASCADE の物理確認。
        """
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        profile = make_role_profile(empire_id=empire_id, role=Role.SECURITY)
        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile)

        # empire 行を削除
        async with session_factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM empires WHERE id = :id"),
                {"id": empire_id.hex},
            )

        # role_profiles 行が CASCADE で消えているはず
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT id FROM role_profiles WHERE empire_id = :empire_id"),
                {"empire_id": empire_id.hex},
            )
            rows = result.fetchall()

        assert rows == [], (
            f"[FAIL] empires 削除後も role_profiles 行が残存: {rows}。\n"
            "Next: role_profiles.empire_id FK に ON DELETE CASCADE が設定されているか確認。"
        )


# ---------------------------------------------------------------------------
# TC-IT-RPR-015: 全フィールド構造的等価 §確定 C ラウンドトリップ
# ---------------------------------------------------------------------------
class TestRoleProfileFullRoundTrip:
    """TC-IT-RPR-015: save → find_by_empire_and_role で全フィールド構造的等価。"""

    async def test_full_round_trip_structural_equality(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-RPR-015: deliverable_template_refs 2 件の RoleProfile が同値でラウンドトリップ。"""
        empire_id = uuid4()
        await _seed_empire(session_factory, empire_id)

        ref1 = make_deliverable_template_ref(minimum_version=SemVer(major=1, minor=2, patch=3))
        ref2 = make_deliverable_template_ref(minimum_version=SemVer(major=2, minor=0, patch=0))

        profile = make_role_profile(
            empire_id=empire_id,
            role=Role.REVIEWER,
            deliverable_template_refs=(ref1, ref2),
        )

        async with session_factory() as session, session.begin():
            await SqliteRoleProfileRepository(session).save(profile)

        async with session_factory() as session:
            restored = await SqliteRoleProfileRepository(session).find_by_empire_and_role(
                empire_id, Role.REVIEWER
            )

        assert restored is not None
        assert restored.id == profile.id
        assert restored.empire_id == profile.empire_id
        assert restored.role == Role.REVIEWER
        assert len(restored.deliverable_template_refs) == 2

        # template_id で引き当て（順序保証のため dict）
        restored_by_id = {r.template_id: r for r in restored.deliverable_template_refs}
        assert restored_by_id[ref1.template_id].minimum_version == SemVer(major=1, minor=2, patch=3)
        assert restored_by_id[ref2.template_id].minimum_version == SemVer(major=2, minor=0, patch=0)
