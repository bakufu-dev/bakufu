"""Directive Repository: find_by_room ORDER BY + ルームスコーピングテスト。

TC-UT-DRR-004 / 004b / 004c / 004d / 004e。

§確定 R1-D: find_by_room は最新優先で Directive を返し、id DESC でタイブレーク
(BUG-EMR-001 規約 — ORDER BY created_at DESC のみは複数の Directive が
同じタイムスタンプを共有する場合、非決定的)。

``docs/features/directive-repository/test-design.md`` 準拠。
Issue #34 — M2 0006。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
    SqliteDirectiveRepository,
)
from sqlalchemy import event

from tests.factories.directive import make_directive
from tests.infrastructure.persistence.sqlite.repositories.test_directive_repository.conftest import (  # noqa: E501
    seed_room,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-DRR-004: ORDER BY created_at DESC, id DESC + SQL log (§確定 R1-D)
# ---------------------------------------------------------------------------
class TestFindByRoomOrderBy:
    """TC-UT-DRR-004: find_by_room returns newest first with id DESC tiebreaker."""

    async def test_find_by_room_returns_directives_newest_first(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Directives are returned newest first (created_at DESC)."""
        oldest = make_directive(
            target_room_id=seeded_room_id,
            created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )
        middle = make_directive(
            target_room_id=seeded_room_id,
            created_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC),
        )
        newest = make_directive(
            target_room_id=seeded_room_id,
            created_at=datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC),
        )
        # save in non-chronological order to prove sorting is not insert-order
        for d in (middle, oldest, newest):
            async with session_factory() as session, session.begin():
                await SqliteDirectiveRepository(session).save(d)

        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)

        assert len(results) == 3
        assert results[0].id == newest.id
        assert results[1].id == middle.id
        assert results[2].id == oldest.id

    async def test_find_by_room_emits_order_by_created_at_and_id_desc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_room_id: UUID,
    ) -> None:
        """SQL log contains ORDER BY created_at DESC, id DESC (§確定 R1-D).

        This is the regression-detection anchor for BUG-EMR-001 規約:
        if the implementation drops ``id DESC``, this test fails.
        """
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

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
                await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        directive_selects = [
            s for s in captured if "FROM directives" in s and "SELECT" in s.upper()
        ]
        assert directive_selects, "find_by_room must SELECT from directives"
        target_stmt = directive_selects[0].lower()
        assert "order by" in target_stmt and "created_at" in target_stmt, (
            f"[FAIL] find_by_room SQL missing ORDER BY created_at.\n"
            f"Captured: {directive_selects[0]!r}"
        )
        assert "id" in target_stmt, (
            f"[FAIL] find_by_room SQL ORDER BY missing id DESC tiebreaker (BUG-EMR-001 規約).\n"
            f"Captured: {directive_selects[0]!r}\n"
            f"Next: add .order_by(DirectiveRow.created_at.desc(), DirectiveRow.id.desc())"
        )

    async def test_find_by_room_count_matches_saved(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """find_by_room returns exactly the number of saved Directives."""
        for _ in range(4):
            async with session_factory() as session, session.begin():
                await SqliteDirectiveRepository(session).save(
                    make_directive(target_room_id=seeded_room_id)
                )

        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)
        assert len(results) == 4


# ---------------------------------------------------------------------------
# TC-UT-DRR-004b: empty Room returns [] (not None)
# ---------------------------------------------------------------------------
class TestFindByRoomEmpty:
    """TC-UT-DRR-004b: find_by_room returns [] for a Room with no Directives."""

    async def test_find_by_room_empty_room_returns_empty_list(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """A Room with zero Directives → [] (empty list, not None)."""
        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)
        assert results == [], (
            f"[FAIL] find_by_room returned {results!r} instead of [] for empty Room.\n"
            "Next: ensure find_by_room returns [] not None when no rows found."
        )

    async def test_find_by_room_unknown_room_returns_empty_list(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """An unknown room_id (no rows exist) → [] (not None, not an error)."""
        unknown_room_id = uuid4()
        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(unknown_room_id)
        assert results == []


# ---------------------------------------------------------------------------
# TC-UT-DRR-004c: Room scope isolation (IDOR guard)
# ---------------------------------------------------------------------------
class TestFindByRoomScopeIsolation:
    """TC-UT-DRR-004c: find_by_room strictly applies Room scope."""

    async def test_find_by_room_isolates_directives_by_room(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Directives from room_a are NOT returned when querying room_b.

        Cross-Room isolation: without WHERE target_room_id = :room_id
        scoping, room_a's Directives could leak into room_b's query.
        """
        room_a = await seed_room(session_factory)
        room_b = await seed_room(session_factory)

        d_in_a = make_directive(target_room_id=room_a)
        d_in_b = make_directive(target_room_id=room_b)

        async with session_factory() as session, session.begin():
            repo = SqliteDirectiveRepository(session)
            await repo.save(d_in_a)
            await repo.save(d_in_b)

        async with session_factory() as session:
            results_a = await SqliteDirectiveRepository(session).find_by_room(room_a)

        ids_in_a = {d.id for d in results_a}
        assert d_in_a.id in ids_in_a
        assert d_in_b.id not in ids_in_a, (
            "[FAIL] find_by_room leaked a Directive from room_b into room_a query.\n"
            "Next: verify WHERE target_room_id = :room_id is in the SELECT."
        )


# ---------------------------------------------------------------------------
# TC-UT-DRR-004d: _from_row full attribute restoration
# ---------------------------------------------------------------------------
class TestFindByRoomFromRowRestoration:
    """TC-UT-DRR-004d: find_by_room hydrates Directives via _from_row correctly."""

    async def test_find_by_room_restores_all_attributes(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """All Directive attributes (id/text/target_room_id/created_at/task_id) restored."""
        directive = make_directive(
            target_room_id=seeded_room_id,
            text="テスト用ディレクティブ",
            task_id=None,
        )
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)

        assert len(results) == 1
        restored = results[0]
        assert restored.id == directive.id
        assert restored.text == directive.text
        assert restored.target_room_id == directive.target_room_id
        assert restored.task_id == directive.task_id
        assert restored.created_at.tzinfo is not None, (
            "[FAIL] created_at lost timezone info in find_by_room _from_row restoration."
        )


# ---------------------------------------------------------------------------
# TC-UT-DRR-004e: id DESC tiebreaker — same created_at (BUG-EMR-001 規約)
# ---------------------------------------------------------------------------
class TestFindByRoomTiebreaker:
    """TC-UT-DRR-004e: id DESC tiebreaker when created_at is identical.

    BUG-EMR-001 規約: ORDER BY created_at DESC alone is non-deterministic
    when multiple Directives share the same timestamp. id DESC (PK, UUID)
    must be the tiebreaker.

    This test is the **regression-detection path**: if the implementation
    removes ``id DESC`` from the ORDER BY clause, this test will fail
    because the returned order becomes engine-dependent (arbitrary).
    """

    async def test_same_created_at_ordered_by_id_desc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """3 Directives with identical created_at → returned in id DESC order.

        UUID strings (hex form) compare lexicographically. We save 3
        Directives with the exact same created_at timestamp and verify
        the result order matches id DESC — proving the tiebreaker is
        active. If id DESC is removed, the order becomes unpredictable
        and this assertion will intermittently fail.
        """
        # Use a fixed identical timestamp so created_at cannot differentiate.
        shared_ts = datetime(9999, 1, 1, 0, 0, 0, tzinfo=UTC)

        d1 = make_directive(target_room_id=seeded_room_id, created_at=shared_ts)
        d2 = make_directive(target_room_id=seeded_room_id, created_at=shared_ts)
        d3 = make_directive(target_room_id=seeded_room_id, created_at=shared_ts)

        async with session_factory() as session, session.begin():
            repo = SqliteDirectiveRepository(session)
            await repo.save(d1)
            await repo.save(d2)
            await repo.save(d3)

        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)

        assert len(results) == 3

        # Build expected order: id DESC (UUID hex string descending)
        ids = [d1.id, d2.id, d3.id]
        expected_order = sorted(ids, key=lambda uid: uid.hex, reverse=True)
        actual_order = [r.id for r in results]

        assert actual_order == expected_order, (
            f"[FAIL] find_by_room did not apply id DESC tiebreaker (BUG-EMR-001 規約).\n"
            f"All 3 Directives have identical created_at={shared_ts.isoformat()}.\n"
            f"Expected id order (desc): {[uid.hex for uid in expected_order]}\n"
            f"Actual id order:          {[uid.hex for uid in actual_order]}\n"
            f"Next: add .order_by(DirectiveRow.created_at.desc(), DirectiveRow.id.desc())"
        )
