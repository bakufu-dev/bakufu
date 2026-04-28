"""Directive Repository: Protocol surface + basic CRUD + Lifecycle coverage.

TC-UT-DRR-001〜009 + TC-IT-DRR-LIFECYCLE.

REQ-DRR-001 / REQ-DRR-002 — 4-method Protocol surface (§確定 R1-A) +
basic CRUD (find_by_id / count / save / Tx boundary) + Lifecycle.

Per ``docs/features/directive-repository/test-design.md``.
Issue #34 — M2 0006.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.application.ports.directive_repository import DirectiveRepository
from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
    SqliteDirectiveRepository,
)
from sqlalchemy import event

from tests.factories.directive import make_directive, make_linked_directive
from tests.infrastructure.persistence.sqlite.repositories.test_directive_repository.conftest import (
    seed_room,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-DRR-001: Protocol definition + 4-method surface (§確定 R1-A)
# ---------------------------------------------------------------------------
class TestDirectiveRepositoryProtocol:
    """TC-UT-DRR-001: Protocol declares 4 async methods (§確定 R1-A)."""

    async def test_protocol_declares_four_async_methods(self) -> None:
        """TC-UT-DRR-001: DirectiveRepository has find_by_id/count/save/find_by_room."""
        assert hasattr(DirectiveRepository, "find_by_id")
        assert hasattr(DirectiveRepository, "count")
        assert hasattr(DirectiveRepository, "save")
        assert hasattr(DirectiveRepository, "find_by_room")

    async def test_protocol_does_not_have_find_by_task_id(self) -> None:
        """TC-UT-DRR-001: find_by_task_id is NOT part of the Protocol (YAGNI).

        §確定 R1-D 後続申し送り: find_by_task_id is deferred to the
        task-repository PR (method + INDEX + FK closure simultaneously).
        If it reappears here, the YAGNI decision in detailed-design.md
        was reversed without updating the design doc first.
        """
        assert not hasattr(DirectiveRepository, "find_by_task_id"), (
            "[FAIL] DirectiveRepository.find_by_task_id must not exist (YAGNI).\n"
            "Next: remove find_by_task_id from the Protocol, or update "
            "detailed-design.md §確定 R1-D 後続申し送り first."
        )

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-DRR-001: SqliteDirectiveRepository satisfies DirectiveRepository.

        The variable annotation acts as a static-type assertion; pyright
        strict will reject the assignment if any of the 4 Protocol
        methods is missing or has a wrong signature.
        """
        async with session_factory() as session:
            repo: DirectiveRepository = SqliteDirectiveRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")
            assert hasattr(repo, "find_by_room")

    async def test_sqlite_repository_duck_typing_4_methods(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-DRR-001: duck-typing confirms all 4 methods present on the impl."""
        async with session_factory() as session:
            repo = SqliteDirectiveRepository(session)
            for method_name in ("find_by_id", "count", "save", "find_by_room"):
                assert hasattr(repo, method_name), (
                    f"[FAIL] SqliteDirectiveRepository.{method_name} missing.\n"
                    f"Protocol requires exactly 4 methods (§確定 R1-A)."
                )


# ---------------------------------------------------------------------------
# TC-UT-DRR-002: find_by_id (REQ-DRR-002, 受入基準 3)
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-UT-DRR-002: find_by_id retrieves saved Directives; None for unknown."""

    async def test_find_by_id_returns_saved_directive(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """find_by_id(directive.id) returns the saved Directive."""
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert fetched is not None
        assert fetched.id == directive.id
        assert fetched.text == directive.text

    async def test_find_by_id_returns_none_for_unknown_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """find_by_id(uuid4()) returns None without raising."""
        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(uuid4())
        assert fetched is None


# ---------------------------------------------------------------------------
# TC-UT-DRR-003: save round-trip equality (REQ-DRR-002, 受入基準 4, §確定 R1-G)
# ---------------------------------------------------------------------------
class TestSaveRoundTrip:
    """TC-UT-DRR-003: save → find_by_id round-trip preserves all attributes."""

    async def test_save_find_by_id_round_trip_all_attributes(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """All attributes (id/text/target_room_id/created_at/task_id) survive round-trip.

        §確定 R1-G: created_at must remain UTC tz-aware after SQLite storage.
        """
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert restored is not None
        assert restored.id == directive.id
        assert restored.text == directive.text
        assert restored.target_room_id == directive.target_room_id
        assert restored.task_id == directive.task_id

    async def test_created_at_is_utc_timezone_aware_after_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """§確定 R1-G: created_at survives round-trip as UTC tz-aware datetime."""
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert restored is not None
        assert restored.created_at.tzinfo is not None, (
            "[FAIL] created_at lost timezone info after round-trip.\n"
            "Next: verify UTCDateTime TypeDecorator returns tz-aware datetime."
        )

    async def test_task_id_none_survives_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """§確定 R1-G: task_id=None round-trips correctly."""
        directive = make_directive(target_room_id=seeded_room_id, task_id=None)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(directive.id)

        assert restored is not None
        assert restored.task_id is None


# ---------------------------------------------------------------------------
# TC-UT-DRR-006: count() SQL COUNT(*) contract (受入基準 8, §確定 R1-A D補強)
# ---------------------------------------------------------------------------
class TestCountIssuesScalarCount:
    """TC-UT-DRR-006: count() issues SELECT COUNT(*), not a full row scan."""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_room_id: UUID,
    ) -> None:
        """SQL log shows SELECT count(*) FROM directives for count().

        empire-repository §確定 D 補強 contract: count() must never
        stream full Directive rows back to Python.
        """
        for _ in range(2):
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
            captured.append(statement.strip())

        sync_engine = app_engine.sync_engine
        event.listen(sync_engine, "before_cursor_execute", _on_execute)
        try:
            async with session_factory() as session:
                count = await SqliteDirectiveRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert count == 2
        directive_selects = [s for s in captured if "FROM directives" in s]
        assert directive_selects, "count() must issue at least one SELECT against directives"
        for stmt in directive_selects:
            assert "count(" in stmt.lower(), (
                f"[FAIL] count() emitted a non-COUNT SELECT: {stmt!r}\n"
                f"Next: ensure count() uses select(func.count()).select_from(DirectiveRow)."
            )


# ---------------------------------------------------------------------------
# TC-UT-DRR-007: save UPSERT update semantics (受入基準 4)
# ---------------------------------------------------------------------------
class TestSaveUpsertSemantics:
    """TC-UT-DRR-007: re-save with same id updates the row (UPSERT)."""

    async def test_resave_updates_text(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """Same directive.id with changed text → latest text returned."""
        original = make_directive(target_room_id=seeded_room_id, text="初期テキスト")
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(original)

        updated = original.model_copy(update={"text": "更新後テキスト"})
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(original.id)

        assert restored is not None
        assert restored.text == "更新後テキスト", (
            "[FAIL] UPSERT did not update text on re-save.\n"
            "Next: verify on_conflict_do_update sets text in the update set."
        )

    async def test_resave_does_not_duplicate_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """UPSERT ensures count stays 1 after multiple saves of same id."""
        directive = make_directive(target_room_id=seeded_room_id)
        for _ in range(3):
            async with session_factory() as session, session.begin():
                await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            count = await SqliteDirectiveRepository(session).count()
        assert count == 1


# ---------------------------------------------------------------------------
# TC-UT-DRR-008: save after link_task — task_id update (§確定 R1-G)
# ---------------------------------------------------------------------------
class TestSaveAfterLinkTask:
    """TC-UT-DRR-008: link_task → re-save updates task_id column."""

    async def test_link_task_and_resave_updates_task_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """directive.link_task(task_id) → save → find_by_id returns updated task_id."""
        original = make_directive(target_room_id=seeded_room_id, task_id=None)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(original)

        new_task_id = uuid4()
        updated = original.link_task(new_task_id)  # type: ignore[arg-type]
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteDirectiveRepository(session).find_by_id(original.id)

        assert restored is not None
        assert restored.task_id is not None
        assert restored.task_id == new_task_id, (
            f"[FAIL] task_id not updated after link_task → re-save.\n"
            f"Expected: {new_task_id}, Got: {restored.task_id}"
        )


# ---------------------------------------------------------------------------
# TC-UT-DRR-009: Tx boundary (§確定 R1-B, empire §確定 B 踏襲)
# ---------------------------------------------------------------------------
class TestTxBoundary:
    """TC-UT-DRR-009: Repository does not auto-commit; caller owns UoW boundary."""

    async def test_save_within_begin_persists(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """save inside async with session.begin() persists the row."""
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(directive.id)
        assert fetched is not None

    async def test_save_without_begin_does_not_persist(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """save without session.begin() leaves row absent after session close.

        Without begin(), SQLAlchemy async session defaults to autobegin
        but does NOT auto-commit on session exit. The implicit transaction
        rolls back when the session context manager exits without commit.
        """
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session:
            # No session.begin() → auto-rollback on __aexit__
            await SqliteDirectiveRepository(session).save(directive)
            # Do NOT commit

        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(directive.id)
        assert fetched is None, (
            "[FAIL] Repository auto-committed without session.begin().\n"
            "Next: verify save() does not call session.commit() (empire §確定 B 踏襲)."
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-LIFECYCLE: 4-method full lifecycle (§確定 R1-F + R1-G)
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """TC-IT-DRR-LIFECYCLE: save → find_by_room → save(update) → count → find_by_id."""

    async def test_full_lifecycle_4_method(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """4-method full lifecycle: save×3 → find_by_room → link_task+resave → count → find_by_id.

        Validates §確定 R1-F (save 1引数) and §確定 R1-G (task_id update)
        in a real end-to-end sequence without any mocking.
        """
        # Step 1: save 3 directives
        now = datetime.now(UTC)
        d1 = make_directive(
            target_room_id=seeded_room_id,
            text="ディレクティブ1",
            created_at=now,
        )
        import asyncio
        await asyncio.sleep(0)  # yield to ensure ordering
        d2 = make_directive(
            target_room_id=seeded_room_id,
            text="ディレクティブ2",
            created_at=now,
        )
        d3 = make_directive(
            target_room_id=seeded_room_id,
            text="ディレクティブ3",
            created_at=now,
        )

        async with session_factory() as session, session.begin():
            repo = SqliteDirectiveRepository(session)
            await repo.save(d1)
            await repo.save(d2)
            await repo.save(d3)

        # Step 2: find_by_room returns 3 directives
        async with session_factory() as session:
            results = await SqliteDirectiveRepository(session).find_by_room(seeded_room_id)
        assert len(results) == 3

        # Step 3: link_task → re-save
        new_task_id = uuid4()
        d1_updated = d1.link_task(new_task_id)  # type: ignore[arg-type]
        async with session_factory() as session, session.begin():
            await SqliteDirectiveRepository(session).save(d1_updated)

        # Step 4: count → 3 (re-save is UPSERT, not INSERT)
        async with session_factory() as session:
            count = await SqliteDirectiveRepository(session).count()
        assert count == 3

        # Step 5: find_by_id(d2.id) → d2 attributes
        async with session_factory() as session:
            via_id = await SqliteDirectiveRepository(session).find_by_id(d2.id)
        assert via_id is not None
        assert via_id.text == d2.text

        # Step 6: d1_updated has task_id set
        async with session_factory() as session:
            d1_restored = await SqliteDirectiveRepository(session).find_by_id(d1.id)
        assert d1_restored is not None
        assert d1_restored.task_id == new_task_id

    async def test_save_directive_resolves_fk_from_directive_target_room_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_room_id: UUID,
    ) -> None:
        """§確定 R1-F: save(directive) reads FK from directive.target_room_id.

        The 1-argument save pattern: Directive carries target_room_id
        as its own attribute, so the Repository reads it directly.
        Saving should succeed without an extra empire_id argument.
        """
        directive = make_directive(target_room_id=seeded_room_id)
        async with session_factory() as session, session.begin():
            # No second argument needed — §確定 R1-F standard pattern
            await SqliteDirectiveRepository(session).save(directive)

        async with session_factory() as session:
            fetched = await SqliteDirectiveRepository(session).find_by_id(directive.id)
        assert fetched is not None
        assert fetched.target_room_id == seeded_room_id
