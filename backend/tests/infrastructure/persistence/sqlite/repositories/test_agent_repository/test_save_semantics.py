"""Agent Repository: save() のセマンティクス ── delete-then-insert + ORDER BY + Tx 境界。

TC-UT-AGR-002 / 003 / 010 / 011 ── §確定 B / §BUG-EMR-001 を踏襲して ``save()`` フローを
裏付ける契約 + ORDER BY 観測 + Tx 境界 + ラウンドトリップ等価性。

``docs/features/agent-repository/test-design.md`` 準拠。
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
    """TC-UT-AGR-002: ``save`` が §確定 B の 5 ステップ DML シーケンスを発行する。

    empire-repository TC-IT-EMR-011 / workflow-repository TC-IT-WFR-010 と
    同じハーネスで ``before_cursor_execute`` リスナにより SQL を観測し、
    プレフィックスを assert する:

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
        """5 ステップの DML 順序が §確定 B に一致する。"""
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
            # 5 つの DML がすべて発火するよう、providers と skills を持つ Agent を構築する
            # （side-table が空だと INSERT がスキップされる）。
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
    """TC-UT-AGR-003: ``ORDER BY provider_kind`` / ``ORDER BY skill_id`` が発行される。

    empire-repository BUG-EMR-001 のクロージャが ORDER BY 契約を凍結し、
    agent Repository は PR #1 から踏襲する。これらの句がないと SQLite は
    内部スキャン順で行を返し、``Agent == Agent`` ラウンドトリップ等価性
    （Aggregate がリスト同士で比較する）が壊れる。
    """

    async def test_find_by_id_emits_order_by_provider_kind(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
    ) -> None:
        """``find_by_id`` が ``ORDER BY agent_providers.provider_kind`` を発行する。"""
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
        """``find_by_id`` が ``ORDER BY agent_skills.skill_id`` を発行する。"""
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
    """``save`` が side-table 行を丸ごと置換する (§確定 B)。"""

    async def test_save_replaces_skill_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """skills 2 → 1 が agent_skills で 1 行として反映される（残骸なし）。"""
        # 初期状態は 2 skill。
        original = make_agent(
            empire_id=seeded_empire_id,
            skills=[make_skill_ref(name="skill_a"), make_skill_ref(name="skill_b")],
        )
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(original)

        # 同じ agent_id で skill 1 件にして再 save。
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
    """TC-UT-AGR-011: save → find_by_id ラウンドトリップで Agent の同一性が保たれる。

    本テストはデフォルトの ``prompt_body``（secret なし）を使うため、マスキングは
    no-op となり full ``==`` が成立する。secret を含むラウンドトリップは
    §確定 H §不可逆性 により非等価になる ── その経路は
    :mod:`...test_masking_persona` で扱う。
    """

    async def test_agent_with_providers_and_skills_round_trips(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """provider 1 + skill 1 を持つ Agent が構造的にラウンドトリップする。"""
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
        # ORDER BY を考慮した比較（ここでは要素 1 つだが、契約は
        # 「リスト順序が SQL の ORDER BY キーに一致する」）。
        assert restored.providers == sorted(agent.providers, key=lambda p: p.provider_kind.value)
        assert restored.skills == sorted(agent.skills, key=lambda s: s.skill_id)


# ---------------------------------------------------------------------------
# TC-UT-AGR-010: Tx boundary responsibility separation (§確定 B)
# ---------------------------------------------------------------------------
class TestTxBoundaryRespectedByRepository:
    """TC-UT-AGR-010: Repository は commit / rollback を呼ばない (§確定 B)。"""

    async def test_commit_path_persists_via_outer_block(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """外側の ``async with session.begin()`` が save を commit する。"""
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
        """``begin()`` 内の例外が 5 ステップの DML すべてをロールバックする。

        Agent 行 + providers + skills は同一の呼び出し側管理トランザクションに参加する。
        ``begin()`` ブロック内の単一の未捕捉例外が **すべて** を破棄せねばならない。
        """

        class _BoomError(Exception):
            """ロールバック経路を駆動する合成例外。"""

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

        # side-table も空 ── §確定 B の契約により、5 ステップは
        # 呼び出し側 UoW 下で **1 つ** の論理操作として扱われる。
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
        """``begin()`` の外側での ``save`` は自動 commit しない (§確定 B)。"""
        agent = make_agent(empire_id=seeded_empire_id)
        async with session_factory() as session:
            await SqliteAgentRepository(session).save(agent)
            # AsyncSession の __aexit__ が処理中の tx をロールバックする。

        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_id(agent.id)
        assert fetched is None, (
            "[FAIL] Agent persisted without an outer commit.\n"
            "Next: SqliteAgentRepository.save() must not call session.commit()."
        )
