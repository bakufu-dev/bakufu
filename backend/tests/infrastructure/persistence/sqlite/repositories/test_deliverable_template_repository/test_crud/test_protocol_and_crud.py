"""DeliverableTemplate Repository Protocol + 基本 CRUD + Tx 境界テスト (Issue #119).

TC-IT-DTR-001〜009:
- Protocol 充足 (001/002)
- find_by_id (003/004)
- find_all ORDER BY name ASC (005/006)
- save UPSERT (007/008)
- Tx 境界 commit / rollback / 暗黙 commit 禁止 (009a/b/c)

§確定 A / B / I:
  docs/features/deliverable-template/repository/detailed-design.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.application.ports.deliverable_template_repository import (
    DeliverableTemplateRepository,
)
from bakufu.infrastructure.persistence.sqlite.repositories.deliverable_template_repository import (
    SqliteDeliverableTemplateRepository,
)
from sqlalchemy import text

from tests.factories.deliverable_template import make_deliverable_template

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
        """TC-IT-DTR-002: SqliteDeliverableTemplateRepository が Protocol を満たす。"""
        async with session_factory() as session:
            repo: DeliverableTemplateRepository = SqliteDeliverableTemplateRepository(session)
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
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)

        assert restored is not None
        assert restored.id == template.id
        assert restored.name == "test-template"

    async def test_find_by_id_returns_none_for_unknown_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-004: 未知の id は None を返す。例外を raise しない。"""
        async with session_factory() as session:
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(uuid4())
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
        """TC-IT-DTR-008: 同 id を更新 name で再 save → find_by_id が新 name を返す。"""
        template = make_deliverable_template(name="original-name")

        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        updated = make_deliverable_template(template_id=template.id, name="updated-name")
        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)

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
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)
        assert result is not None

    async def test_rollback_path_drops_template(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-009b: begin() ブロック内例外で rollback → 行が消える。"""

        class _BoomError(Exception):
            pass

        template = make_deliverable_template()

        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteDeliverableTemplateRepository(session).save(template)
                raise _BoomError

        async with session_factory() as session:
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)
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
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)
        assert result is None, (
            "[FAIL] 暗黙 commit で template 行が永続化された。"
            "Repository は session.commit() を呼ばないこと (§確定 B)。"
        )


# ---------------------------------------------------------------------------
# TC-IT-DTR-021/022: Repository.delete() 物理確認 (§確定E)
# ---------------------------------------------------------------------------
class TestDeleteMethod:
    """TC-IT-DTR-021 / 022: SqliteDeliverableTemplateRepository.delete() (§確定E)。"""

    async def test_delete_removes_existing_template(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-021: 存在する id を delete → find_by_id が None を返す。"""
        template = make_deliverable_template()

        # INSERT
        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).save(template)

        # DELETE
        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).delete(template.id)

        # 物理削除確認
        async with session_factory() as session:
            result = await SqliteDeliverableTemplateRepository(session).find_by_id(template.id)
        assert result is None, (
            "[FAIL] delete() 後も template 行が残存。物理削除が機能していない (§確定 E)。"
        )

    async def test_delete_noop_on_unknown_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-DTR-022: 存在しない id を delete → 例外なし（no-op）。"""
        unknown_id = uuid4()

        # 存在しない id に対して delete → 例外が発生してはならない
        async with session_factory() as session, session.begin():
            await SqliteDeliverableTemplateRepository(session).delete(unknown_id)
        # 到達できれば no-op が正常に機能している
