"""Room Repository: save() semantics — delete-then-insert + ORDER BY + Tx boundary.

TC-UT-RR-002 / 003 / 010 / 011 — the §確定 R1-B 3-step save flow contract +
ORDER BY observation + Tx boundary + round-trip equality.

§確定 R1-B 3-step:
    1. ``rooms`` UPSERT (id PK, ON CONFLICT update 5 scalar columns)
    2. ``room_members`` DELETE WHERE room_id = ?
    3. ``room_members`` bulk INSERT (skipped when members is empty)

ORDER BY (§BUG-EMR-001 inherited from day 1):
    ``find_by_id`` must ORDER BY ``agent_id, role`` on room_members so the
    hydrated member list is deterministic across SQLite internal-scan order.

Per ``docs/features/room-repository/test-design.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.value_objects import Role
from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
    SqliteRoomRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.room_members import RoomMemberRow
from sqlalchemy import event, select

from tests.factories.room import (
    make_agent_membership,
    make_leader_membership,
    make_populated_room,
    make_room,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-RR-002: 3-step delete-then-insert SQL order (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestSaveSqlOrder:
    """TC-UT-RR-002: ``save`` issues the §確定 R1-B 3-step DML sequence.

    Observed via ``before_cursor_execute`` listener and asserted:

    1. ``INSERT INTO rooms`` (UPSERT via ON CONFLICT DO UPDATE)
    2. ``DELETE FROM room_members``
    3. ``INSERT INTO room_members``
    """

    async def test_save_emits_upsert_then_delete_insert(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """3-step DML order matches §確定 R1-B."""
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

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            # Build a Room with non-empty members so all 3 DML steps fire.
            # An empty room would skip step 3 (INSERT room_members).
            room = make_populated_room(workflow_id=seeded_workflow_id)
            async with session_factory() as session, session.begin():
                await SqliteRoomRepository(session).save(room, seeded_empire_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        dml = [
            s
            for s in captured
            if any(
                s.upper().startswith(prefix)
                for prefix in (
                    "INSERT INTO ROOMS",
                    "DELETE FROM ROOM_MEMBERS",
                    "INSERT INTO ROOM_MEMBERS",
                )
            )
        ]
        assert len(dml) >= 3, (
            f"[FAIL] save emitted only {len(dml)} DML statements; expected >=3.\n"
            f"Captured DML: {dml}"
        )
        assert dml[0].upper().startswith("INSERT INTO ROOMS"), (
            f"[FAIL] Step 1 must be UPSERT INTO rooms; got: {dml[0]!r}"
        )
        assert dml[1].upper().startswith("DELETE FROM ROOM_MEMBERS"), (
            f"[FAIL] Step 2 must be DELETE FROM room_members; got: {dml[1]!r}"
        )
        assert dml[2].upper().startswith("INSERT INTO ROOM_MEMBERS"), (
            f"[FAIL] Step 3 must be INSERT INTO room_members; got: {dml[2]!r}"
        )

    async def test_save_empty_room_skips_member_insert(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """A Room with no members skips step 3 (INSERT room_members).

        ``save()`` has an explicit ``if member_rows:`` guard (§確定 R1-B).
        An empty INSERT would still be a no-op in SQL, but this confirms
        the short-circuit path — a regression that removes the guard and
        issues an empty INSERT would not be caught by a behavioural test
        alone.
        """
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

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            # Explicitly empty members list.
            room = make_room(members=[], workflow_id=seeded_workflow_id)
            async with session_factory() as session, session.begin():
                await SqliteRoomRepository(session).save(room, seeded_empire_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        room_member_inserts = [
            s for s in captured if s.upper().startswith("INSERT INTO ROOM_MEMBERS")
        ]
        assert room_member_inserts == [], (
            f"[FAIL] save emitted INSERT INTO room_members for empty Room.\n"
            f"Next: the ``if member_rows:`` guard must prevent an empty INSERT.\n"
            f"Captured: {room_member_inserts}"
        )


# ---------------------------------------------------------------------------
# TC-UT-RR-003: ORDER BY contract (§BUG-EMR-001 inherited from day 1)
# ---------------------------------------------------------------------------
class TestFindByIdOrderByContract:
    """TC-UT-RR-003: ``find_by_id`` emits ``ORDER BY agent_id, role`` on room_members.

    The empire-repository BUG-EMR-001 closure froze the ORDER BY
    contract; the Room Repository adopts it from PR #33.  Without
    these clauses, SQLite returns rows in internal-scan order which
    would break ``Room == Room`` round-trip equality (the Aggregate
    compares member list-by-list).
    """

    async def test_find_by_id_emits_order_by_agent_id_role(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``find_by_id`` emits ``ORDER BY room_members.agent_id, room_members.role``."""
        room = make_populated_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        captured: list[str] = []

        def _on_execute(
            _conn: object,
            _cursor: object,
            statement: str,
            _params: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            captured.append(statement)

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            async with session_factory() as session:
                await SqliteRoomRepository(session).find_by_id(room.id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        member_selects = [
            stmt for stmt in captured if "FROM room_members" in stmt and "SELECT" in stmt.upper()
        ]
        assert member_selects, "find_by_id must SELECT from room_members"
        assert any("ORDER BY" in stmt.upper() and "agent_id" in stmt for stmt in member_selects), (
            f"[FAIL] find_by_id missing ``ORDER BY agent_id``.\n"
            f"Captured room_members SELECTs: {member_selects}"
        )
        assert any("ORDER BY" in stmt.upper() and "role" in stmt for stmt in member_selects), (
            f"[FAIL] find_by_id missing ``ORDER BY role``.\n"
            f"Captured room_members SELECTs: {member_selects}"
        )

    async def test_member_list_deterministic_across_saves(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Multiple find_by_id calls return members in the same ORDER BY order.

        Seeds a Room with 3 members (different agent_ids) and verifies
        that two successive find_by_id calls produce identical member
        lists — proving ORDER BY is deterministic across SQLite pages.
        """
        from uuid import UUID as _UUID

        # Three distinct agent IDs; deliberately not in ascending UUIDhex
        # order so we can detect if ORDER BY is absent.
        a1 = _UUID("aaaaaaaa-0000-0000-0000-000000000001")
        a2 = _UUID("aaaaaaaa-0000-0000-0000-000000000002")
        a3 = _UUID("aaaaaaaa-0000-0000-0000-000000000003")

        room = make_room(
            workflow_id=seeded_workflow_id,
            members=[
                make_leader_membership(agent_id=a3),
                make_agent_membership(agent_id=a1, role=Role.DEVELOPER),
                make_agent_membership(agent_id=a2, role=Role.REVIEWER),
            ],
        )
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            first = await SqliteRoomRepository(session).find_by_id(room.id)
        async with session_factory() as session:
            second = await SqliteRoomRepository(session).find_by_id(room.id)

        assert first is not None
        assert second is not None
        assert [m.agent_id for m in first.members] == [m.agent_id for m in second.members], (
            "[FAIL] find_by_id returns members in different orders across calls.\n"
            "Next: ensure ORDER BY agent_id, role is present on the room_members SELECT."
        )


# ---------------------------------------------------------------------------
# TC-UT-RR-002 (delete-then-insert replacement semantics)
# ---------------------------------------------------------------------------
class TestSaveReplacesMemberRows:
    """``save`` replaces room_members wholesale (§確定 R1-B step 2-3)."""

    async def test_save_replaces_member_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Members 2 → 1 reflects as 1 row in room_members (no residue).

        Verifies the DELETE-then-INSERT pattern: a re-save with fewer
        members must not leave stale rows in room_members.
        """
        # Two members initially.
        original = make_room(
            workflow_id=seeded_workflow_id,
            members=[
                make_leader_membership(),
                make_agent_membership(role=Role.DEVELOPER),
            ],
        )
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(original, seeded_empire_id)

        # Re-save with only one member.
        solo_member = make_leader_membership()
        replacement = original.model_copy(update={"members": [solo_member]})
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(replacement, seeded_empire_id)

        async with session_factory() as session:
            rows = list(
                (
                    await session.execute(
                        select(RoomMemberRow).where(RoomMemberRow.room_id == original.id)
                    )
                ).scalars()
            )
        assert len(rows) == 1
        assert rows[0].role == solo_member.role.value


# ---------------------------------------------------------------------------
# TC-UT-RR-011: round-trip equality (_to_row / _from_row via DB)
# ---------------------------------------------------------------------------
class TestRoundTripEquality:
    """TC-UT-RR-011: save → find_by_id round-trip preserves Room identity.

    Note: this test uses default ``prompt_kit.prefix_markdown=''`` (no
    secrets) so masking is a no-op and full ``==`` holds. Secret-bearing
    round-trip is non-equal due to §確定 R1-J §不可逆性 — that path lives
    in :mod:`...test_masking_prompt_kit`.
    """

    async def test_populated_room_round_trips(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Room with 2 members round-trips structurally (ORDER BY aware)."""
        room = make_populated_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            restored = await SqliteRoomRepository(session).find_by_id(room.id)

        assert restored is not None
        assert restored.id == room.id
        assert restored.name == room.name
        assert restored.description == room.description
        assert restored.archived == room.archived
        assert restored.workflow_id == room.workflow_id
        assert restored.prompt_kit == room.prompt_kit
        # Members are returned in ORDER BY (agent_id, role) — compare
        # after sorting by (agent_id, role) on the original side so the
        # assertion is ORDER BY-aware.
        original_sorted = sorted(room.members, key=lambda m: (str(m.agent_id), m.role.value))
        assert len(restored.members) == len(original_sorted)
        for got, want in zip(restored.members, original_sorted, strict=True):
            assert got.agent_id == want.agent_id
            assert got.role == want.role


# ---------------------------------------------------------------------------
# TC-UT-RR-010: Tx boundary responsibility separation (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestTxBoundaryRespectedByRepository:
    """TC-UT-RR-010: Repository never calls commit / rollback (§確定 R1-B)."""

    async def test_commit_path_persists_via_outer_block(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """Outer ``async with session.begin()`` commits the save."""
        room = make_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)
        assert fetched is not None

    async def test_rollback_path_drops_save_atomically(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """An exception inside ``begin()`` rolls back ALL 3 DML steps.

        The Room row + room_members all participate in the same
        caller-managed transaction. A single uncaught exception must
        purge **all** of them.
        """

        class _BoomError(Exception):
            """Synthetic exception used to drive the rollback path."""

        room = make_populated_room(workflow_id=seeded_workflow_id)

        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteRoomRepository(session).save(room, seeded_empire_id)
                raise _BoomError

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)
        assert fetched is None

        # room_members also empty — the §確定 R1-B contract is that the
        # 3-step sequence is one logical operation under the caller's UoW.
        async with session_factory() as session:
            member_rows = (
                await session.execute(select(RoomMemberRow).where(RoomMemberRow.room_id == room.id))
            ).all()
        assert member_rows == []

    async def test_repository_does_not_commit_implicitly(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``save`` outside ``begin()`` does not auto-commit (§確定 R1-B)."""
        room = make_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session:
            await SqliteRoomRepository(session).save(room, seeded_empire_id)
            # AsyncSession's __aexit__ rolls back any in-flight tx.

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)
        assert fetched is None, (
            "[FAIL] Room persisted without an outer commit.\n"
            "Next: SqliteRoomRepository.save() must not call session.commit()."
        )
