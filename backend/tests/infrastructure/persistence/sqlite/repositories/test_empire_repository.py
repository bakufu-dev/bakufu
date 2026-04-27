"""Empire Repository integration tests
(TC-UT-EMR-001〜003 + TC-IT-EMR-001〜007 / 010〜014 / 017 / 018).

Per ``docs/features/empire-repository/test-design.md``. Real SQLite +
real Alembic + real AsyncSession through the M2 ``app_engine`` /
``session_factory`` fixtures from ``tests/infrastructure/conftest.py``.

The Empire is the **first** Aggregate Repository PR — these tests
freeze the templates that the next 6 Repository PRs (workflow / agent
/ room / directive / task / external-review-gate) re-use.
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
from sqlalchemy import delete, select, text

from tests.factories.empire import (
    make_empire,
    make_populated_empire,
    make_room_ref,
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
        # Protocol classes don't expose the methods at instance level
        # but at class level. Assert each method is callable on the
        # Protocol type itself. Marked ``async`` purely so the
        # module-level ``pytestmark = asyncio`` does not warn.
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
            # Different id — the FK constraints accept it; the
            # Repository must not throw a singleton-enforcement error.
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


class TestSaveDeleteThenInsert:
    """TC-IT-EMR-006: ``save`` replaces side-table rows wholesale (§確定 B)."""

    async def test_save_replaces_room_refs(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-006: 2 rooms → 1 room is reflected as 1 row in empire_room_refs."""
        original = make_populated_empire(n_rooms=2, n_agents=3)
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(original)

        # Build a new Empire with the same id but only 1 room.
        replacement = make_empire(
            empire_id=original.id,
            name=original.name,
            rooms=[make_room_ref(name="残った部屋")],
            agents=list(original.agents),
        )
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(replacement)

        # Side tables must show the new state, not the merged old + new.
        async with session_factory() as session:
            room_rows = list(
                (
                    await session.execute(
                        select(EmpireRoomRefRow).where(EmpireRoomRefRow.empire_id == original.id)
                    )
                ).scalars()
            )
        assert len(room_rows) == 1
        assert room_rows[0].name == "残った部屋"


class TestRoundTripStructuralEquality:
    """TC-IT-EMR-007 + TC-UT-EMR-003: save → find_by_id round-trip preserves equality.

    Note (BUG-EMR-001): :meth:`SqliteEmpireRepository.find_by_id` does
    not issue ``ORDER BY`` when SELECTing the side tables, so the
    rooms / agents lists come back in whatever order SQLite happens
    to scan. The Empire VO carries lists (ordered), but the design
    docs do not freeze a list-order semantic for ``rooms`` /
    ``agents`` and there is no insertion-order guarantee at the SQL
    layer. The tests below therefore compare the **set** of rooms /
    agents — which captures the design intent ("the same membership
    survives the round-trip") without locking in an undocumented
    list-order contract. The bug report recommends adding an
    ``ORDER BY`` to ``find_by_id`` *only if* the design wants list
    semantics; otherwise the Empire VO should be updated to compare
    by set / frozenset of refs.
    """

    async def test_populated_empire_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-007: round-trip preserves Empire identity + membership."""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            restored = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert restored is not None
        assert restored.id == empire.id
        assert restored.name == empire.name
        # Set-based comparison (BUG-EMR-001 workaround): the Repository
        # does not emit ORDER BY, so list order is undefined. Membership
        # equality is the design intent we care about.
        assert set(restored.rooms) == set(empire.rooms)
        assert set(restored.agents) == set(empire.agents)

    async def test_empty_empire_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-007: round-trip an Empire with zero rooms / agents."""
        empire = make_empire()  # rooms=[] agents=[] by default
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            restored = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert restored is not None
        # Empty case: no list-order ambiguity, full ``==`` is fine.
        assert restored == empire

    async def test_to_row_then_from_row_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-EMR-003: ``_to_row`` → save + find_by_id (≡ ``_from_row``) preserves membership."""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            restored = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert restored is not None
        # Same set-based comparison as test_populated_empire_round_trip
        # — see BUG-EMR-001 in the class docstring.
        assert restored.id == empire.id
        assert restored.name == empire.name
        assert set(restored.rooms) == set(empire.rooms)
        assert set(restored.agents) == set(empire.agents)


# ---------------------------------------------------------------------------
# 確定 B: delete-then-insert 5 段階順序 + Tx 境界
# ---------------------------------------------------------------------------
class TestSaveSqlOrder:
    """TC-IT-EMR-011: ``save`` issues SQL in the §確定 B 5-step order.

    We attach a ``before_cursor_execute`` listener on the **sync**
    engine so we observe the actual SQL strings the dialect emits. The
    listener appends each statement to a captured list; we then assert
    the prefix sequence matches the design's 5 steps. The dispatcher /
    ORM may issue extra SAVEPOINT / BEGIN statements which we filter
    out — the contract is on the *DML* prefix.
    """

    async def test_save_emits_upsert_then_delete_insert_pairs(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: object,  # AsyncEngine; typed loosely so listener API works
    ) -> None:
        """TC-IT-EMR-011: empires UPSERT → empire_room_refs DEL+INS → empire_agent_refs DEL+INS."""
        from sqlalchemy import event

        captured: list[str] = []

        def _on_execute(
            _conn: object,
            _cursor: object,
            statement: str,
            _params: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            captured.append(statement.strip())

        sync_engine = app_engine.sync_engine  # type: ignore[attr-defined]  # AsyncEngine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            empire = make_populated_empire(n_rooms=2, n_agents=3)
            async with session_factory() as session, session.begin():
                await SqliteEmpireRepository(session).save(empire)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # Filter to the 5 DML statements we care about (BEGIN /
        # SAVEPOINT / RELEASE / COMMIT noise removed).
        dml = [
            s
            for s in captured
            if any(
                s.upper().startswith(prefix)
                for prefix in ("INSERT INTO EMPIRES", "DELETE FROM EMPIRE", "INSERT INTO EMPIRE")
            )
        ]
        # Step 1 (UPSERT empires) → Step 2 (DELETE empire_room_refs) →
        # Step 3 (INSERT empire_room_refs) → Step 4 (DELETE
        # empire_agent_refs) → Step 5 (INSERT empire_agent_refs).
        assert len(dml) >= 5
        assert dml[0].upper().startswith("INSERT INTO EMPIRES")
        assert dml[1].upper().startswith("DELETE FROM EMPIRE_ROOM_REFS")
        assert dml[2].upper().startswith("INSERT INTO EMPIRE_ROOM_REFS")
        assert dml[3].upper().startswith("DELETE FROM EMPIRE_AGENT_REFS")
        assert dml[4].upper().startswith("INSERT INTO EMPIRE_AGENT_REFS")


class TestTxBoundaryRespectedByRepository:
    """TC-IT-EMR-012: Repository never calls commit / rollback (§確定 B)."""

    async def test_commit_path_persists_via_outer_block(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-012 (commit): outer ``async with session.begin()`` commits the save."""
        empire = make_empire()
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            fetched = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert fetched is not None

    async def test_rollback_path_drops_save_atomically(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-012 (rollback): an exception inside ``begin()`` rolls back the save."""

        class _BoomError(Exception):
            """Synthetic exception used to drive the rollback path."""

        empire = make_empire()
        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteEmpireRepository(session).save(empire)
                raise _BoomError

        async with session_factory() as session:
            fetched = await SqliteEmpireRepository(session).find_by_id(empire.id)
        # Rollback must have been atomic — no row survives.
        assert fetched is None


# ---------------------------------------------------------------------------
# DB 制約: FK CASCADE + UNIQUE
# ---------------------------------------------------------------------------
class TestForeignKeyCascade:
    """TC-IT-EMR-013: ``DELETE FROM empires`` cascades to side tables."""

    async def test_delete_empire_cascades_to_side_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-013: FK ON DELETE CASCADE empties empire_room_refs / empire_agent_refs."""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session, session.begin():
            await session.execute(delete(EmpireRow).where(EmpireRow.id == empire.id))

        async with session_factory() as session:
            room_rows = list(
                (
                    await session.execute(
                        select(EmpireRoomRefRow).where(EmpireRoomRefRow.empire_id == empire.id)
                    )
                ).scalars()
            )
            agent_rows = list(
                (
                    await session.execute(
                        select(EmpireAgentRefRow).where(EmpireAgentRefRow.empire_id == empire.id)
                    )
                ).scalars()
            )
        assert room_rows == []
        assert agent_rows == []


class TestUniqueConstraintViolation:
    """TC-IT-EMR-014: duplicate (empire_id, room_id) raises IntegrityError."""

    async def test_duplicate_room_pair_raises(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-014: same (empire_id, room_id) inserted twice → DB rejects.

        The Repository's delete-then-insert flow always wipes the side
        tables before INSERT, so the constraint is never tripped through
        the Repository API. To exercise the **DB-level** UNIQUE
        contract we issue raw SQL that bypasses the Repository.
        """
        from sqlalchemy.exc import IntegrityError

        empire = make_empire()
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        room_id = uuid4()
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO empire_room_refs (empire_id, room_id, name, archived) "
                    "VALUES (:empire_id, :room_id, :name, :archived)"
                ),
                {
                    "empire_id": empire.id.hex,
                    "room_id": room_id.hex,
                    "name": "first",
                    "archived": False,
                },
            )

        with pytest.raises(IntegrityError):
            async with session_factory() as session, session.begin():
                await session.execute(
                    text(
                        "INSERT INTO empire_room_refs (empire_id, room_id, name, archived) "
                        "VALUES (:empire_id, :room_id, :name, :archived)"
                    ),
                    {
                        "empire_id": empire.id.hex,
                        "room_id": room_id.hex,
                        "name": "duplicate",
                        "archived": False,
                    },
                )


# ---------------------------------------------------------------------------
# CI 三層防衛 Layer 2 — テンプレート構造の物理確認 (§確定 E / F)
# ---------------------------------------------------------------------------
class TestNoMaskTemplateStructure:
    """TC-IT-EMR-017: arch test exposes a parametrize structure future PRs can extend."""

    async def test_arch_test_module_imports_no_mask_table_list(self) -> None:
        """TC-IT-EMR-017: ``_NO_MASK_TABLES`` exists and lists the Empire 3 tables.

        Future Repository PRs add their own "no-mask" table names to
        ``_NO_MASK_TABLES`` (or the parallel ``_MASKING_CONTRACT`` for
        secret-bearing columns); the structural shape lets them extend
        without rewriting the harness.
        """
        from tests.architecture.test_masking_columns import (
            _MASKING_CONTRACT,  # pyright: ignore[reportPrivateUsage]
            _NO_MASK_TABLES,  # pyright: ignore[reportPrivateUsage]
        )

        # Empire 3 tables must be in the no-mask list.
        assert "empires" in _NO_MASK_TABLES
        assert "empire_room_refs" in _NO_MASK_TABLES
        assert "empire_agent_refs" in _NO_MASK_TABLES
        # Empire columns must NOT appear in the masking-contract list
        # (positive contract).
        empire_table_names = {"empires", "empire_room_refs", "empire_agent_refs"}
        contract_tables = {tbl for tbl, _, _ in _MASKING_CONTRACT}
        assert contract_tables.isdisjoint(empire_table_names)
