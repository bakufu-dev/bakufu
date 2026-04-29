"""Agent Repository: Protocol サーフェス + 基本 CRUD カバレッジ。

TC-UT-AGR-001 / 004 / 005 ── エントリポイント挙動と
**4 メソッドの Protocol サーフェス**（agent-repository は empire / workflow の
3 メソッドテンプレートに ``find_by_name`` を加える最初の Repository。§確定 F）。

``docs/features/agent-repository/test-design.md`` 準拠。
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
# REQ-AGR-001: Protocol 定義 + 4 メソッドサーフェス (§確定 A + F)
# ---------------------------------------------------------------------------
class TestAgentRepositoryProtocol:
    """TC-UT-AGR-001: Protocol が ``find_by_name`` を含む 4 つの async メソッドを宣言する。"""

    async def test_protocol_declares_four_async_methods(self) -> None:
        """TC-UT-AGR-001: ``AgentRepository`` が
        find_by_id / count / save / find_by_name を持つ。"""
        # モジュールレベルの pytestmark = asyncio が警告しないよう async を付ける。
        assert hasattr(AgentRepository, "find_by_id")
        assert hasattr(AgentRepository, "count")
        assert hasattr(AgentRepository, "save")
        # ``find_by_name`` は §確定 F で導入された 4 番目のメソッド ──
        # 3 メソッドテンプレートを最初に拡張する M2 Repository PR。
        assert hasattr(AgentRepository, "find_by_name")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-AGR-001: ``SqliteAgentRepository`` を ``AgentRepository`` に代入できる。

        変数アノテーションが静的型アサーションとして機能する。pyright strict は、
        Protocol メソッドが欠落または誤シグネチャの場合に代入を拒否する。
        """
        async with session_factory() as session:
            repo: AgentRepository = SqliteAgentRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")
            assert hasattr(repo, "find_by_name")


# ---------------------------------------------------------------------------
# REQ-AGR-002 (find_by_id の基本ラウンドトリップ)
# ---------------------------------------------------------------------------
class TestFindById:
    """find_by_id は保存済み Agent を取得する。未知の id は None を返す。"""

    async def test_find_by_id_returns_saved_agent(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_empire_id: UUID,
    ) -> None:
        """``find_by_id(agent.id)`` が構造的に等価な Agent を返す（デフォルトでは secret なし）。"""
        # デフォルト factory の ``prompt_body='You are a thorough reviewer.'`` には
        # Schneier-#6 の secret が含まれないため、マスキングは no-op となり
        # ラウンドトリップ等価性が成立する。secret を含む prompt のラウンドトリップは
        # :mod:`...test_masking_persona` (§確定 H §不可逆性) で扱う。
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
        """``find_by_id(uuid4())`` は例外を投げず ``None`` を返す。"""
        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteAgentRepository(session).find_by_id(unknown_id)
        assert fetched is None


# ---------------------------------------------------------------------------
# TC-UT-AGR-004: count() must issue SQL-level COUNT(*)
# ---------------------------------------------------------------------------
class TestCountIssuesScalarCount:
    """TC-UT-AGR-004: ``count()`` は ``SELECT COUNT(*)`` を発行し、行を全件スキャンしない。"""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_empire_id: UUID,
    ) -> None:
        """SQL ログが ``count()`` に対し ``SELECT count(*)`` を示す。

        empire-repository §確定 D 補強の契約を継続する ── Agent の
        provider / skill 行は preset ライブラリ着地後は数百レコードを保持しうるため、
        COUNT(*) パターンが Empire 以上に重要となる。
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
    """TC-UT-AGR-005: ``find_by_name`` が Empire スコープを強制する。

    §確定 F に沿う 3 つの直交ケース:

    1. **ヒット**: ``empire_a`` 内の ``foo`` という名前の Agent が返る。
    2. **同 Empire 内ミス**: ``empire_a`` 配下の ``bar`` という名前は None を返す。
    3. **Empire 間隔離**: ``foo`` が ``empire_a`` に存在しても、``empire_b`` 配下の
       ``foo`` 検索は None を返す。これが IDOR ガード ── ``WHERE empire_id=:empire_id``
       がなければ攻撃者が名前を推測して別テナントの Agent を読み取れる。
    """

    async def test_find_by_name_returns_agent_when_present(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """ヒット経路: name + empire_id ペアが Agent を返す。"""
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
        """ミス経路: 既知 Empire 内の未知の名前は None を返す。"""
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
        """**IDOR ガード**: 別 Empire 配下の同名は None を返す。

        本テストは test-design.md §確定 F の中核契約。``WHERE empire_id`` 句を落とす
        回帰（例: 全 Empire 横断で name 検索）は、攻撃者がテナント越境で Agent を
        読めてしまう ── このアサーションは即座にそれを表面化させる。
        """
        empire_a = await seed_empire(session_factory)
        empire_b = await seed_empire(session_factory)
        agent_in_a = make_agent(empire_id=empire_a, name="shared_name")
        async with session_factory() as session, session.begin():
            await SqliteAgentRepository(session).save(agent_in_a)

        async with session_factory() as session:
            # 同じ名前を別の empire で検索する ── empire_a に "shared_name" が
            # 存在しても、None を返さねばならない。
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
        """SQL ログに ``WHERE agents.empire_id = ?`` と ``LIMIT 1`` が含まれる。

        上の振る舞いテストに対する多層防御: クロス Empire テストが seed の名前衝突など
        行偶発で pass してしまっても、SQL 自体がスコープ句を持たねばならない。
        ``before_cursor_execute`` リスナを取り付け、empire_id 述語を grep する。
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

        # AgentId を検索するために ``agents`` を叩いた SELECT を探す。
        agent_id_selects = [s for s in captured if "FROM agents" in s and "SELECT" in s.upper()]
        assert agent_id_selects, "find_by_name must SELECT from agents"
        # 該当する最初の SELECT は、フルテーブルスキャンを避けるため、
        # empire_id 述語と LIMIT 句の両方を持たねばならない。
        target_stmt = agent_id_selects[0]
        assert "empire_id" in target_stmt, (
            f"[FAIL] find_by_name SQL missing empire_id predicate.\nCaptured: {target_stmt!r}"
        )
        assert "LIMIT" in target_stmt.upper(), (
            f"[FAIL] find_by_name SQL missing LIMIT clause.\nCaptured: {target_stmt!r}"
        )


# ---------------------------------------------------------------------------
# ライフサイクル統合: save → find_by_name → find_by_id → save (更新)
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """TC-IT-AGR-LIFECYCLE: save → 検索 → 更新の完全フロー。"""

    async def test_full_lifecycle_with_persona_update(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Save → find_by_name → find_by_id → persona 更新 → save。

        4 つの Protocol メソッドがエンドツーエンドで協調し、再 save 経由の
        persona 更新が UPSERT 経路（§確定 B 5 ステップの Step 1）で DB に到達することを検証する。
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

        # 更新: persona display_name を変更して再 save。
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
