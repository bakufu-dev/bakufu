"""Agent Repository: Protocol surface + basic CRUD coverage.

TC-UT-AGR-001 / 004 / 005 — the entry-point behaviors plus the
**4-method Protocol surface** (the agent-repository is the first
Repository to add ``find_by_name`` on top of the empire / workflow
3-method template, §確定 F).

Per ``docs/features/agent-repository/test-design.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.application.ports.agent_repository import AgentRepository
from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
    SqliteAgentRepository,
)
from sqlalchemy import event

from tests.factories.agent import make_agent
from tests.infrastructure.persistence.sqlite.repositories.test_agent_repository.conftest import (
    seed_empire,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# REQ-AGR-001: Protocol definition + 4-method surface (§確定 A + F)
# ---------------------------------------------------------------------------
class TestAgentRepositoryProtocol:
    """TC-UT-AGR-001: Protocol declares 4 async methods incl. ``find_by_name``."""

    async def test_protocol_declares_four_async_methods(self) -> None:
        """TC-UT-AGR-001: ``AgentRepository`` has find_by_id / count / save / find_by_name."""
        # Marked async so module-level pytestmark = asyncio does not warn.
        assert hasattr(AgentRepository, "find_by_id")
        assert hasattr(AgentRepository, "count")
        assert hasattr(AgentRepository, "save")
        # ``find_by_name`` is the 4th method introduced by §確定 F —
        # the first M2 Repository PR to extend the 3-method template.
        assert hasattr(AgentRepository, "find_by_name")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-AGR-001: ``SqliteAgentRepository`` is assignable to ``AgentRepository``.

        The variable annotation acts as a static-type assertion; pyright
        strict will reject the assignment if any of the 4 Protocol
        methods is missing or has a wrong signature.
        """
        async with session_factory() as session:
            repo: AgentRepository = SqliteAgentRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")
            assert hasattr(repo, "find_by_name")


# ---------------------------------------------------------------------------
# REQ-AGR-002 (find_by_id basic round-trip)
# ---------------------------------------------------------------------------
class TestFindById:
    """find_by_id retrieves saved Agents; returns None for unknown."""

    async def test_find_by_id_returns_saved_agent(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """``find_by_id(agent.id)`` returns a structurally-equal Agent (no secrets in default)."""
        # Default factory ``prompt_body='You are a thorough reviewer.'``
        # contains no Schneier-#6 secrets, so masking is a no-op and
        # round-trip equality holds. Secret-bearing prompt round-trip
        # lives in :mod:`...test_masking_persona` (§確定 H §不可逆性).
        agent = make_agent(empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_id(agent.id)

        assert fetched is not None
        assert fetched == agent

    async def test_find_by_id_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """``find_by_id(uuid4())`` returns ``None`` without raising."""
        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_id(unknown_id)
        assert fetched is None


# ---------------------------------------------------------------------------
# TC-UT-AGR-004: count() must issue SQL-level COUNT(*)
# ---------------------------------------------------------------------------
class TestCountIssuesScalarCount:
    """TC-UT-AGR-004: ``count()`` issues ``SELECT COUNT(*)``, not a full row scan."""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
    ) -> None:
        """SQL log shows ``SELECT count(*)`` for ``count()``.

        The empire-repository §確定 D 補強 contract continued — Agent
        provider / skill rows can hold hundreds of records once the
        preset library lands, so the COUNT(*) pattern matters even
        more than for Empire.
        """
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(make_agent(empire_id=seeded_empire_id))
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(make_agent(empire_id=seeded_empire_id))

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
                count = await SqliteAgentRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert count == 2
        agent_selects = [s for s in captured if "FROM agents" in s]
        assert agent_selects, "count() must issue at least one SELECT against agents"
        for stmt in agent_selects:
            assert "count(" in stmt.lower(), (
                f"[FAIL] count() emitted a non-COUNT SELECT: {stmt!r}\n"
                f"Next: ensure count() uses select(func.count()).select_from(AgentRow)."
            )


# ---------------------------------------------------------------------------
# TC-UT-AGR-005: find_by_name Empire-scoped (§確定 F)
# ---------------------------------------------------------------------------
class TestFindByNameEmpireScoped:
    """TC-UT-AGR-005: ``find_by_name`` enforces Empire scoping.

    Three orthogonal cases per §確定 F:

    1. **Hit**: Agent named ``foo`` inside ``empire_a`` is returned.
    2. **Miss in same Empire**: name ``bar`` under ``empire_a`` returns None.
    3. **Cross-Empire isolation**: name ``foo`` under ``empire_b`` returns None
       even though ``foo`` exists in ``empire_a``. This is the IDOR
       guard — without ``WHERE empire_id=:empire_id`` an attacker
       could read another tenant's Agent by guessing the name.
    """

    async def test_find_by_name_returns_agent_when_present(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Hit path: name + empire_id pair returns the Agent."""
        empire_a = await seed_empire(session_factory)
        agent = make_agent(empire_id=empire_a, name="agent_a")
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_name(empire_a, "agent_a")

        assert fetched is not None
        assert fetched.id == agent.id
        assert fetched.empire_id == empire_a
        assert fetched.name == "agent_a"

    async def test_find_by_name_returns_none_when_name_missing(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Miss path: unknown name in known Empire returns None."""
        empire_a = await seed_empire(session_factory)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(
                make_agent(empire_id=empire_a, name="agent_a")
            )

        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_name(empire_a, "nonexistent")
        assert fetched is None

    async def test_find_by_name_isolates_by_empire(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """**IDOR guard**: same name under different Empire returns None.

        This is the test-design.md §確定 F core contract. A regression
        that drops the ``WHERE empire_id`` clause (e.g. by globally
        searching by name) would let an attacker read cross-tenant
        Agents — this assertion fires loudly in that case.
        """
        empire_a = await seed_empire(session_factory)
        empire_b = await seed_empire(session_factory)
        agent_in_a = make_agent(empire_id=empire_a, name="shared_name")
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent_in_a)

        async with session_factory() as session:
            # Look up the same name but in a DIFFERENT empire — must
            # return None even though "shared_name" exists in empire_a.
            fetched = await SqliteAgentRepository(session).find_by_name(empire_b, "shared_name")
        assert fetched is None, (
            "[FAIL] find_by_name leaked an Agent across Empire boundaries.\n"
            "Next: verify the SQL contains ``WHERE empire_id = :empire_id`` "
            "(detailed-design.md §確定 F). A missing scope clause is an IDOR."
        )

    async def test_find_by_name_emits_empire_scoped_sql(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """SQL log shows ``WHERE agents.empire_id = ?`` and ``LIMIT 1``.

        Defense-in-depth on top of the behavioural test above: even if
        the cross-Empire test happens to pass via row-coincidence
        (e.g. name conflict in seed data), the SQL itself must carry
        the scope clause. We attach a ``before_cursor_execute``
        listener and grep for the empire_id predicate.
        """
        empire_a = await seed_empire(session_factory)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(
                make_agent(empire_id=empire_a, name="agent_a")
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
                await SqliteAgentRepository(session).find_by_name(empire_a, "agent_a")
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # Locate the SELECT that hit ``agents`` to look up the AgentId.
        agent_id_selects = [s for s in captured if "FROM agents" in s and "SELECT" in s.upper()]
        assert agent_id_selects, "find_by_name must SELECT from agents"
        # The first such SELECT must carry both the empire_id predicate
        # and a LIMIT clause to avoid full-table scans.
        target_stmt = agent_id_selects[0]
        assert "empire_id" in target_stmt, (
            f"[FAIL] find_by_name SQL missing empire_id predicate.\nCaptured: {target_stmt!r}"
        )
        assert "LIMIT" in target_stmt.upper(), (
            f"[FAIL] find_by_name SQL missing LIMIT clause.\nCaptured: {target_stmt!r}"
        )


# ---------------------------------------------------------------------------
# Lifecycle integration: save → find_by_name → find_by_id → save (update)
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """TC-IT-AGR-LIFECYCLE: full save → lookup → update flow."""

    async def test_full_lifecycle_with_persona_update(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Save → find_by_name → find_by_id → update persona → save.

        Verifies the 4 Protocol methods cooperate end-to-end and that
        a persona update via re-save reaches the DB through the
        UPSERT path (Step 1 of §確定 B 5-step).
        """
        from bakufu.domain.agent import Persona

        empire_a = await seed_empire(session_factory)
        original = make_agent(
            empire_id=empire_a,
            name="lifecycle_agent",
            persona=Persona(
                display_name="初期",
                archetype="review-focused",
                prompt_body="You are a reviewer.",
            ),
        )
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(original)

        async with session_factory() as session:
            via_name = await SqliteAgentRepository(session).find_by_name(
                empire_a, "lifecycle_agent"
            )
        assert via_name is not None
        assert via_name.persona.display_name == "初期"

        async with session_factory() as session:
            via_id = await SqliteAgentRepository(session).find_by_id(original.id)
        assert via_id is not None
        assert via_id == via_name

        # Update: change the persona display_name and re-save.
        updated = original.model_copy(
            update={
                "persona": Persona(
                    display_name="更新後",
                    archetype=original.persona.archetype,
                    prompt_body=original.persona.prompt_body,
                ),
            }
        )
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(updated)

        async with session_factory() as session:
            after = await SqliteAgentRepository(session).find_by_id(original.id)
        assert after is not None
        assert after.persona.display_name == "更新後"
