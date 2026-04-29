"""Empire Repository: プロトコルサーフェス + 基本 CRUD カバレッジ。

TC-IT-EMR-001 / 002 / 003 / 004 / 005 / 010 / 018 — すべての Aggregate Repository
が満たさねばならないエントリポイント動作。Norman の500行ルールに従い
元の ``test_empire_repository.py`` から分割
(参照: :mod:`...test_empire_repository.__init__`)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.application.ports.empire_repository import EmpireRepository
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_agent_refs import (
    EmpireAgentRefRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_room_refs import (
    EmpireRoomRefRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.empires import EmpireRow
from sqlalchemy import select

from tests.factories.empire import make_empire, make_populated_empire
from tests.infrastructure.persistence.sqlite.repositories.test_empire_repository.conftest import (
    seed_rooms,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# REQ-EMR-001: Protocol definition + 充足 (確定 A)
# ---------------------------------------------------------------------------
class TestEmpireRepositoryProtocol:
    """TC-IT-EMR-001 / 010: Protocol surface + duck-typing 充足."""

    async def test_protocol_declares_three_async_methods(self) -> None:
        """TC-IT-EMR-001: ``EmpireRepository`` has find_by_id / count / save."""
        # Protocol クラスはメソッドをインスタンスレベルではなく
        # クラスレベルで公開する。各メソッドが Protocol 型自体で
        # callable であることをアサートする。``async`` を付けているのは
        # モジュールレベルの ``pytestmark = asyncio`` が warn しないようにするため。
        assert hasattr(EmpireRepository, "find_by_id")
        assert hasattr(EmpireRepository, "count")
        assert hasattr(EmpireRepository, "save")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-010: ``SqliteEmpireRepository`` is assignable to ``EmpireRepository``.

        The variable annotation acts as a static-type assertion; pyright
        strict will reject the assignment if any Protocol method is
        missing or has a wrong signature. Duck-typing at runtime confirms
        the three methods exist on the instance too.
        """
        async with session_factory() as session:
            repo: EmpireRepository = SqliteEmpireRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")


# ---------------------------------------------------------------------------
# REQ-EMR-002: find_by_id / count / save 基本 CRUD (確定 B)
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-IT-EMR-002 / 003: find_by_id retrieves saved Empires; returns None for unknown."""

    async def test_find_by_id_returns_saved_empire(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-002: ``find_by_id(empire.id)`` returns a structurally-equal Empire."""
        empire = make_empire()
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            fetched = await SqliteEmpireRepository(session).find_by_id(empire.id)

        assert fetched is not None
        assert fetched == empire

    async def test_find_by_id_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-003: ``find_by_id(uuid4())`` returns ``None`` without raising."""
        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteEmpireRepository(session).find_by_id(unknown_id)
        assert fetched is None


class TestCount:
    """TC-IT-EMR-004 / 018: count() reports facts; never enforces singleton."""

    async def test_count_zero_then_one(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-004: ``count()`` reports 0 then 1 after a single ``save``."""
        async with session_factory() as session:
            assert await SqliteEmpireRepository(session).count() == 0

        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(make_empire())

        async with session_factory() as session:
            assert await SqliteEmpireRepository(session).count() == 1

    async def test_repository_does_not_enforce_singleton(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-018: Repository accepts multiple Empire saves (§確定 D).

        Singleton enforcement is the application service's job
        (``EmpireService.create()``); the Repository itself reports
        facts via ``count()`` and never raises just because the
        cardinality grew above 1.
        """
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(make_empire())
        async with session_factory() as session, session.begin():
            # 異なる id — FK 制約は受け入れる;
            # Repository はシングルトン強制エラーを送出してはならない。
            await SqliteEmpireRepository(session).save(make_empire())

        async with session_factory() as session:
            count = await SqliteEmpireRepository(session).count()
        assert count == 2


class TestSaveInsertsAllThreeTables:
    """TC-IT-EMR-005: ``save`` writes ``empires`` + ``empire_room_refs`` + ``empire_agent_refs``."""

    async def test_save_populates_three_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-005: 2 rooms + 3 agents land in their respective side tables."""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        # Alembic 0005 で empire_room_refs.room_id → rooms.id FK が追加された（BUG-EMR-001
        # クローズ）。FK を解決するため save() 前に rooms 行を seed する。
        await seed_rooms(session_factory, empire.id, [r.room_id for r in empire.rooms])
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            empire_count = (
                await session.execute(select(EmpireRow).where(EmpireRow.id == empire.id))
            ).all()
            room_rows = (
                await session.execute(
                    select(EmpireRoomRefRow).where(EmpireRoomRefRow.empire_id == empire.id)
                )
            ).all()
            agent_rows = (
                await session.execute(
                    select(EmpireAgentRefRow).where(EmpireAgentRefRow.empire_id == empire.id)
                )
            ).all()

        assert len(empire_count) == 1
        assert len(room_rows) == 2
        assert len(agent_rows) == 3
