"""Agent Repository: save() semantics — delete-then-insert + ORDER BY + Tx boundary.

TC-UT-AGR-002 / 003 / 010 / 011 — the §確定 B / §BUG-EMR-001 inheritance
contracts that back the ``save()`` flow + ORDER BY observation +
Tx boundary + round-trip equality.

Per ``docs/features/agent-repository/test-design.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from bakufu.domain.value_objects import ProviderKind
from bakufu.infrastructure.persistence.sqlite.repositories.agent_repository import (
    SqliteAgentRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.agent_providers import (
    AgentProviderRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.agent_skills import (
    AgentSkillRow,
)
from sqlalchemy import event, select

from tests.factories.agent import (
    make_agent,
    make_provider_config,
    make_skill_ref,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-AGR-002: 5-step delete-then-insert SQL order (§確定 B)
# ---------------------------------------------------------------------------
class TestSaveSqlOrder:
    """TC-UT-AGR-002: ``save`` issues the §確定 B 5-step DML sequence.

    Same harness as empire-repository TC-IT-EMR-011 / workflow-
    repository TC-IT-WFR-010 — observe SQL via
    ``before_cursor_execute`` listener and assert prefixes:

    1. ``INSERT INTO agents`` (UPSERT)
    2. ``DELETE FROM agent_providers``
    3. ``INSERT INTO agent_providers``
    4. ``DELETE FROM agent_skills``
    5. ``INSERT INTO agent_skills``
    """

    async def test_save_emits_upsert_then_delete_insert_pairs(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
    ) -> None:
        """5-step DML order matches §確定 B."""
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
            # Build an Agent with non-empty providers + skills so all
            # 5 DML statements actually fire (empty side-tables would
            # skip the INSERT).
            agent = make_agent(
                empire_id=seeded_empire_id,
                providers=[make_provider_config()],
                skills=[make_skill_ref()],
            )
            async with session_factory() as session, session.begin():
                await SqliteAgentRepository(session).save(agent)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        dml = [
            s
            for s in captured
            if any(
                s.upper().startswith(prefix)
                for prefix in (
                    "INSERT INTO AGENTS",
                    "DELETE FROM AGENT_",
                    "INSERT INTO AGENT_",
                )
            )
        ]
        assert len(dml) >= 5, (
            f"[FAIL] save emitted only {len(dml)} DML statements; expected >=5.\n"
            f"Captured DML: {dml}"
        )
        assert dml[0].upper().startswith("INSERT INTO AGENTS")
        assert dml[1].upper().startswith("DELETE FROM AGENT_PROVIDERS")
        assert dml[2].upper().startswith("INSERT INTO AGENT_PROVIDERS")
        assert dml[3].upper().startswith("DELETE FROM AGENT_SKILLS")
        assert dml[4].upper().startswith("INSERT INTO AGENT_SKILLS")


# ---------------------------------------------------------------------------
# TC-UT-AGR-003: ORDER BY contract (§BUG-EMR-001 inherited from day 1)
# ---------------------------------------------------------------------------
class TestFindByIdOrderByContract:
    """TC-UT-AGR-003: ``ORDER BY provider_kind`` / ``ORDER BY skill_id`` are emitted.

    The empire-repository BUG-EMR-001 closure froze the ORDER BY
    contract; the agent Repository adopts it from PR #1. Without
    these clauses, SQLite returns rows in internal-scan order which
    would break ``Agent == Agent`` round-trip equality (the
    Aggregate compares list-by-list).
    """

    async def test_find_by_id_emits_order_by_provider_kind(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
    ) -> None:
        """``find_by_id`` emits ``ORDER BY agent_providers.provider_kind``."""
        agent = make_agent(
            empire_id=seeded_empire_id,
            providers=[
                make_provider_config(provider_kind=ProviderKind.CLAUDE_CODE, is_default=True),
            ],
            skills=[make_skill_ref()],
        )
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

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
                await SqliteAgentRepository(session).find_by_id(agent.id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        provider_selects = [
            stmt for stmt in captured if "FROM agent_providers" in stmt and "SELECT" in stmt.upper()
        ]
        assert provider_selects, "find_by_id must SELECT from agent_providers"
        assert any(
            "ORDER BY" in stmt.upper() and "provider_kind" in stmt for stmt in provider_selects
        ), (
            f"[FAIL] find_by_id missing ``ORDER BY provider_kind``.\n"
            f"Captured provider SELECTs: {provider_selects}"
        )

    async def test_find_by_id_emits_order_by_skill_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
    ) -> None:
        """``find_by_id`` emits ``ORDER BY agent_skills.skill_id``."""
        agent = make_agent(
            empire_id=seeded_empire_id,
            providers=[make_provider_config()],
            skills=[make_skill_ref()],
        )
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

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
                await SqliteAgentRepository(session).find_by_id(agent.id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        skill_selects = [
            stmt for stmt in captured if "FROM agent_skills" in stmt and "SELECT" in stmt.upper()
        ]
        assert skill_selects, "find_by_id must SELECT from agent_skills"
        assert any("ORDER BY" in stmt.upper() and "skill_id" in stmt for stmt in skill_selects), (
            f"[FAIL] find_by_id missing ``ORDER BY skill_id``.\n"
            f"Captured skill SELECTs: {skill_selects}"
        )


# ---------------------------------------------------------------------------
# TC-UT-AGR-002 (delete-then-insert replacement semantics)
# ---------------------------------------------------------------------------
class TestSaveReplacesSideTableRows:
    """``save`` replaces side-table rows wholesale (§確定 B)."""

    async def test_save_replaces_skill_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Skills 2 → 1 reflects as 1 row in agent_skills (no residue)."""
        # Two skills initially.
        original = make_agent(
            empire_id=seeded_empire_id,
            skills=[make_skill_ref(name="skill_a"), make_skill_ref(name="skill_b")],
        )
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(original)

        # Re-save with one skill — same agent_id.
        replacement = make_agent(
            agent_id=original.id,
            empire_id=original.empire_id,
            name=original.name,
            persona=original.persona,
            providers=list(original.providers),
            skills=[make_skill_ref(name="残ったスキル")],
        )
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(replacement)

        async with session_factory() as session:
            rows = list(
                (
                    await session.execute(
                        select(AgentSkillRow).where(AgentSkillRow.agent_id == original.id)
                    )
                ).scalars()
            )
        assert len(rows) == 1
        assert rows[0].name == "残ったスキル"


# ---------------------------------------------------------------------------
# TC-UT-AGR-011: round-trip equality (_to_row / _from_row via DB)
# ---------------------------------------------------------------------------
class TestRoundTripEquality:
    """TC-UT-AGR-011: save → find_by_id round-trip preserves Agent identity.

    Note: this test uses default ``prompt_body`` (no secrets) so
    masking is a no-op and full ``==`` holds. Secret-bearing
    round-trip is non-equal due to §確定 H §不可逆性 — that path lives
    in :mod:`...test_masking_persona`.
    """

    async def test_agent_with_providers_and_skills_round_trips(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Agent with 1 provider + 1 skill round-trips structurally."""
        agent = make_agent(
            empire_id=seeded_empire_id,
            providers=[make_provider_config()],
            skills=[make_skill_ref()],
        )
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        async with session_factory() as session:
            restored = await SqliteAgentRepository(session).find_by_id(agent.id)

        assert restored is not None
        assert restored.id == agent.id
        assert restored.empire_id == agent.empire_id
        assert restored.name == agent.name
        assert restored.role == agent.role
        # ORDER BY-aware comparisons (single-element here, but the
        # contract is "list order matches the SQL ORDER BY key").
        assert restored.providers == sorted(agent.providers, key=lambda p: p.provider_kind.value)
        assert restored.skills == sorted(agent.skills, key=lambda s: s.skill_id)


# ---------------------------------------------------------------------------
# TC-UT-AGR-010: Tx boundary responsibility separation (§確定 B)
# ---------------------------------------------------------------------------
class TestTxBoundaryRespectedByRepository:
    """TC-UT-AGR-010: Repository never calls commit / rollback (§確定 B)."""

    async def test_commit_path_persists_via_outer_block(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """Outer ``async with session.begin()`` commits the save."""
        agent = make_agent(empire_id=seeded_empire_id)
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent)

        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_id(agent.id)
        assert fetched is not None

    async def test_rollback_path_drops_save_atomically(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """An exception inside ``begin()`` rolls back ALL 5 DML steps.

        The Agent row + providers + skills all participate in the
        same caller-managed transaction. A single uncaught exception
        inside the ``begin()`` block must purge **all** of them.
        """

        class _BoomError(Exception):
            """Synthetic exception used to drive the rollback path."""

        agent = make_agent(
            empire_id=seeded_empire_id,
            providers=[make_provider_config()],
            skills=[make_skill_ref()],
        )

        with pytest.raises(_BoomError):
            async with session_factory() as session, session.begin():
                await SqliteAgentRepository(session).save(agent)
                raise _BoomError

        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_id(agent.id)
        assert fetched is None

        # Side tables also empty — the §確定 B contract is that the
        # 5-step sequence is **one** logical operation under the
        # caller's UoW.
        async with session_factory() as session:
            provider_rows = (
                await session.execute(
                    select(AgentProviderRow).where(AgentProviderRow.agent_id == agent.id)
                )
            ).all()
            skill_rows = (
                await session.execute(
                    select(AgentSkillRow).where(AgentSkillRow.agent_id == agent.id)
                )
            ).all()
        assert provider_rows == []
        assert skill_rows == []

    async def test_repository_does_not_commit_implicitly(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """``save`` outside ``begin()`` does not auto-commit (§確定 B)."""
        agent = make_agent(empire_id=seeded_empire_id)
        async with session_factory() as session:
            await SqliteAgentRepository(session).save(agent)
            # AsyncSession's __aexit__ rolls back any in-flight tx.

        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_id(agent.id)
        assert fetched is None, (
            "[FAIL] Agent persisted without an outer commit.\n"
            "Next: SqliteAgentRepository.save() must not call session.commit()."
        )
