"""Room Repository: Protocol surface + basic CRUD coverage.

TC-UT-RR-001 / 004 / 005 / 006 — the entry-point behaviors plus the
**4-method Protocol surface** (``find_by_id`` / ``count`` / ``save`` /
``find_by_name``, §確定 R1-A + R1-F).

Per ``docs/features/room-repository/test-design.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.application.ports.room_repository import RoomRepository
from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
    SqliteRoomRepository,
)
from sqlalchemy import event

from tests.factories.room import make_populated_room, make_room
from tests.infrastructure.persistence.sqlite.repositories.test_room_repository.conftest import (
    seed_empire,
    seed_workflow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# REQ-RR-001: Protocol definition + 4-method surface (§確定 R1-A)
# ---------------------------------------------------------------------------
class TestRoomRepositoryProtocol:
    """TC-UT-RR-001: Protocol declares 4 async methods."""

    async def test_protocol_declares_four_async_methods(self) -> None:
        """TC-UT-RR-001: ``RoomRepository`` has find_by_id / count / save / find_by_name."""
        assert hasattr(RoomRepository, "find_by_id")
        assert hasattr(RoomRepository, "count")
        assert hasattr(RoomRepository, "save")
        assert hasattr(RoomRepository, "find_by_name")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-RR-001: ``SqliteRoomRepository`` is assignable to ``RoomRepository``.

        The variable annotation acts as a static-type assertion; pyright
        strict will reject the assignment if any of the 4 Protocol
        methods is missing or has a wrong signature.
        """
        async with session_factory() as session:
            repo: RoomRepository = SqliteRoomRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")
            assert hasattr(repo, "find_by_name")

    async def test_protocol_does_not_expose_count_by_empire(self) -> None:
        """TC-UT-RR-001: ``count_by_empire`` is NOT part of the Protocol (YAGNI).

        §確定 R1-A froze ``count_by_empire`` as YAGNI — the method must not
        appear on the public Protocol surface. A future PR that re-adds it
        must update §確定 R1-A first; otherwise this assertion fires.
        """
        assert not hasattr(RoomRepository, "count_by_empire"), (
            "[FAIL] RoomRepository.count_by_empire must not exist (YAGNI, §確定 R1-A).\n"
            "Next: remove count_by_empire from the Protocol."
        )


# ---------------------------------------------------------------------------
# REQ-RR-002 (find_by_id basic round-trip)
# ---------------------------------------------------------------------------
class TestFindById:
    """find_by_id retrieves saved Rooms; returns None for unknown."""

    async def test_find_by_id_returns_saved_room(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``find_by_id(room.id)`` returns a structurally-equal Room (no secrets in default).

        Default factory ``prompt_kit.prefix_markdown=''`` contains no
        Schneier-#6 secrets, so masking is a no-op and round-trip
        equality holds. Secret-bearing prefix round-trip lives in
        :mod:`...test_masking_prompt_kit` (§確定 R1-J §不可逆性).
        """
        room = make_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)

        assert fetched is not None
        assert fetched == room

    async def test_find_by_id_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """``find_by_id(uuid4())`` returns ``None`` without raising."""
        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(unknown_id)
        assert fetched is None

    async def test_find_by_id_hydrates_members(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """``find_by_id`` returns a Room with its members hydrated."""
        room = make_populated_room(workflow_id=seeded_workflow_id)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, seeded_empire_id)

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_id(room.id)

        assert fetched is not None
        assert len(fetched.members) == 2  # LEADER + DEVELOPER from make_populated_room


# ---------------------------------------------------------------------------
# TC-UT-RR-004: count() must issue SQL-level COUNT(*)
# ---------------------------------------------------------------------------
class TestCountIssuesScalarCount:
    """TC-UT-RR-004: ``count()`` issues ``SELECT COUNT(*)``, not a full row scan."""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
        seeded_workflow_id: UUID,
    ) -> None:
        """SQL log shows ``SELECT count(*)`` for ``count()``.

        Follows empire-repository §確定 D 補強 contract — ``count()`` must
        never stream full Room rows back to Python, especially once Rooms
        carry large ``prompt_kit_prefix_markdown`` content.
        """
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(
                make_room(workflow_id=seeded_workflow_id), seeded_empire_id
            )
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(
                make_room(workflow_id=seeded_workflow_id), seeded_empire_id
            )

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
            async with session_factory() as session:
                count = await SqliteRoomRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert count == 2
        room_selects = [s for s in captured if "FROM rooms" in s]
        assert room_selects, "count() must issue at least one SELECT against rooms"
        for stmt in room_selects:
            assert "count(" in stmt.lower(), (
                f"[FAIL] count() emitted a non-COUNT SELECT: {stmt!r}\n"
                f"Next: ensure count() uses select(func.count()).select_from(RoomRow)."
            )


# ---------------------------------------------------------------------------
# TC-UT-RR-005: find_by_name Empire-scoped (§確定 R1-F)
# ---------------------------------------------------------------------------
class TestFindByNameEmpireScoped:
    """TC-UT-RR-005: ``find_by_name`` enforces Empire scoping.

    Three orthogonal cases per §確定 R1-F:

    1. **Hit**: Room named ``foo`` inside ``empire_a`` is returned.
    2. **Miss in same Empire**: name ``bar`` under ``empire_a`` returns None.
    3. **Cross-Empire isolation**: name ``foo`` under ``empire_b`` returns None
       even though ``foo`` exists in ``empire_a``. This is the IDOR
       guard — without ``WHERE empire_id=:empire_id`` an attacker
       could read another tenant's Room by guessing the name.
    """

    async def test_find_by_name_returns_room_when_present(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Hit path: name + empire_id pair returns the Room."""
        empire_a = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        room = make_room(name="room_a", workflow_id=wf)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room, empire_a)

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_name(empire_a, "room_a")

        assert fetched is not None
        assert fetched.id == room.id
        assert fetched.name == "room_a"

    async def test_find_by_name_returns_none_when_name_missing(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Miss path: unknown name in known Empire returns None."""
        empire_a = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(
                make_room(name="room_a", workflow_id=wf), empire_a
            )

        async with session_factory() as session:
            fetched = await SqliteRoomRepository(session).find_by_name(empire_a, "nonexistent")
        assert fetched is None

    async def test_find_by_name_isolates_by_empire(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """**IDOR guard**: same name under different Empire returns None.

        This is the test-design.md §確定 R1-F core contract. A regression
        that drops the ``WHERE empire_id`` clause would let an attacker
        read cross-tenant Rooms — this assertion fires loudly in that case.
        """
        empire_a = await seed_empire(session_factory)
        empire_b = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        room_in_a = make_room(name="shared_name", workflow_id=wf)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(room_in_a, empire_a)

        async with session_factory() as session:
            # Look up the same name but in a DIFFERENT empire — must
            # return None even though "shared_name" exists in empire_a.
            fetched = await SqliteRoomRepository(session).find_by_name(empire_b, "shared_name")
        assert fetched is None, (
            "[FAIL] find_by_name leaked a Room across Empire boundaries.\n"
            "Next: verify the SQL contains ``WHERE empire_id = :empire_id`` "
            "(detailed-design.md §確定 R1-F). A missing scope clause is an IDOR."
        )

    async def test_find_by_name_emits_empire_scoped_sql(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """SQL log shows ``WHERE rooms.empire_id = ?`` and ``LIMIT 1``.

        Defense-in-depth on top of the behavioural test above: even if
        the cross-Empire test happens to pass via row-coincidence,
        the SQL itself must carry the scope clause. We attach a
        ``before_cursor_execute`` listener and grep for the empire_id
        predicate.
        """
        empire_a = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(
                make_room(name="room_a", workflow_id=wf), empire_a
            )

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
                await SqliteRoomRepository(session).find_by_name(empire_a, "room_a")
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # Locate the SELECT that hit ``rooms`` to look up the RoomId.
        room_id_selects = [s for s in captured if "FROM rooms" in s and "SELECT" in s.upper()]
        assert room_id_selects, "find_by_name must SELECT from rooms"
        # The SELECT must carry both the empire_id predicate and LIMIT.
        target_stmt = room_id_selects[0]
        assert "empire_id" in target_stmt, (
            f"[FAIL] find_by_name SQL missing empire_id predicate.\nCaptured: {target_stmt!r}"
        )
        assert "LIMIT" in target_stmt.upper(), (
            f"[FAIL] find_by_name SQL missing LIMIT clause.\nCaptured: {target_stmt!r}"
        )


# ---------------------------------------------------------------------------
# TC-UT-RR-006: Lifecycle integration (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """TC-UT-RR-006: full save → lookup → update flow."""

    async def test_full_lifecycle_with_description_update(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Save → find_by_name → find_by_id → update description → save.

        Verifies the 4 Protocol methods cooperate end-to-end and that
        a description update via re-save reaches the DB through the
        UPSERT path (Step 1 of §確定 R1-B 3-step).
        """
        empire_a = await seed_empire(session_factory)
        wf = await seed_workflow(session_factory)
        original = make_room(
            name="lifecycle_room",
            description="初期説明",
            workflow_id=wf,
        )
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(original, empire_a)

        async with session_factory() as session:
            via_name = await SqliteRoomRepository(session).find_by_name(empire_a, "lifecycle_room")
        assert via_name is not None
        assert via_name.description == "初期説明"

        async with session_factory() as session:
            via_id = await SqliteRoomRepository(session).find_by_id(original.id)
        assert via_id is not None
        assert via_id == via_name

        # Update: change description and re-save.
        updated = original.model_copy(update={"description": "更新後の説明"})
        async with session_factory() as session, session.begin():
            await SqliteRoomRepository(session).save(updated, empire_a)

        async with session_factory() as session:
            after = await SqliteRoomRepository(session).find_by_id(original.id)
        assert after is not None
        assert after.description == "更新後の説明"
