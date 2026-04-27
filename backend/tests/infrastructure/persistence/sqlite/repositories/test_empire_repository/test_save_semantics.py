"""Empire Repository: save() semantics — delete-then-insert + Tx boundary.

TC-IT-EMR-006 / 007 / 011 / 012 + TC-UT-EMR-003 — the §確定 B
contract that backs the ``save()`` flow plus round-trip equality.
Split out from the original ``test_empire_repository.py`` per
Norman's 500-line rule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
    SqliteEmpireRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_room_refs import (
    EmpireRoomRefRow,
)
from sqlalchemy import select

from tests.factories.empire import make_empire, make_populated_empire, make_room_ref

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


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

    BUG-EMR-001 closure: :meth:`SqliteEmpireRepository.find_by_id` now
    issues ``ORDER BY room_id`` / ``ORDER BY agent_id`` per
    ``basic-design.md`` L127-128 and ``detailed-design.md`` §クラス設計.
    The hydrated lists are deterministic, so the previous set-based
    workaround is removed and replaced with the contracted list-order
    comparison.

    Test contract (ORDER BY 物理保証): the Repository's
    ``ORDER BY room_id`` / ``ORDER BY agent_id`` design contract is
    asserted by sorting the input Empire's collections by the same
    key and demanding list equality. Failing this assertion means
    the SQL contract regressed (either the ``ORDER BY`` was dropped
    or the column changed).
    """

    async def test_populated_empire_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-EMR-007: round-trip preserves Empire identity + membership in ORDER BY order."""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            restored = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert restored is not None
        assert restored.id == empire.id
        assert restored.name == empire.name
        # ORDER BY room_id / agent_id 物理保証: restored side-table
        # lists are deterministic, so list-order equality is the
        # contract. The expected lists are sorted by the same key
        # the Repository used in its ``ORDER BY``.
        assert restored.rooms == sorted(empire.rooms, key=lambda r: r.room_id)
        assert restored.agents == sorted(empire.agents, key=lambda a: a.agent_id)

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
        """TC-UT-EMR-003: ``_to_row`` → save + find_by_id (≡ ``_from_row``) preserves equality."""
        empire = make_populated_empire(n_rooms=2, n_agents=3)
        async with session_factory() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)

        async with session_factory() as session:
            restored = await SqliteEmpireRepository(session).find_by_id(empire.id)
        assert restored is not None
        assert restored.id == empire.id
        assert restored.name == empire.name
        # Same ORDER BY-aware list comparison as
        # test_populated_empire_round_trip — see class docstring for
        # the BUG-EMR-001 closure rationale.
        assert restored.rooms == sorted(empire.rooms, key=lambda r: r.room_id)
        assert restored.agents == sorted(empire.agents, key=lambda a: a.agent_id)


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
