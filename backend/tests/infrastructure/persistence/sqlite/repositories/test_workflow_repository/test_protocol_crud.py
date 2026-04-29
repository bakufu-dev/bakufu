"""Workflow Repository: Protocol サーフェス + 基本 CRUD カバレッジ。

TC-IT-WFR-001 / 002 / 003 / 004 / 005 / 006 / 007 / 019 ── empire-repository (PR #25)
が固定したエントリポイント挙動を本 PR が 100% 踏襲することと、Workflow 固有の
``ORDER BY stage_id`` / ``ORDER BY transition_id`` SQL ログ観測（detailed-design.md L51 の
BUG-EMR-001 from-day-1 契約）を扱う。

``docs/features/workflow-repository/test-design.md`` のマトリクス準拠。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.application.ports.workflow_repository import WorkflowRepository
from bakufu.domain.value_objects import WorkflowId
from bakufu.domain.workflow import Workflow
from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
    SqliteWorkflowRepository,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import (
    WorkflowStageRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_transitions import (
    WorkflowTransitionRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflows import WorkflowRow
from sqlalchemy import event, select

from tests.factories.workflow import make_stage, make_transition, make_workflow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# REQ-WFR-001: Protocol 定義 + 充足 (§確定 A)
# ---------------------------------------------------------------------------
class TestWorkflowRepositoryProtocol:
    """TC-IT-WFR-001 / 002: Protocol サーフェス + ダックタイピング充足。"""

    async def test_protocol_declares_three_async_methods(self) -> None:
        """TC-IT-WFR-001: ``WorkflowRepository`` が find_by_id / count / save を持つ。"""
        # Protocol class はインスタンスレベルではなくクラスレベルでメソッドを公開する。
        # モジュールレベルの ``pytestmark = asyncio`` が警告しないよう ``async`` を付ける。
        assert hasattr(WorkflowRepository, "find_by_id")
        assert hasattr(WorkflowRepository, "count")
        assert hasattr(WorkflowRepository, "save")

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-002: ``SqliteWorkflowRepository`` を ``WorkflowRepository`` に代入できる。

        変数アノテーションが静的型アサーションとして機能する ── pyright strict は、
        Protocol メソッドが欠落または誤シグネチャの場合に代入を拒否する。
        ランタイムのダックタイピングでもインスタンスに 3 メソッドの存在を確認する。
        """
        async with session_factory() as session:
            repo: WorkflowRepository = SqliteWorkflowRepository(session)
            assert hasattr(repo, "find_by_id")
            assert hasattr(repo, "count")
            assert hasattr(repo, "save")


# ---------------------------------------------------------------------------
# REQ-WFR-002: find_by_id / count / save の基本 CRUD
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-IT-WFR-003 / 004: find_by_id は保存済み Workflow を取得する。未知の id は None。"""

    async def test_find_by_id_returns_saved_workflow(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-003: ``find_by_id(workflow.id)`` が構造的に等価な Workflow を返す。

        ``make_workflow()`` のデフォルト（単一 ``WORK`` ステージ、``EXTERNAL_REVIEW``
        なし → notify_channels なし）を用いるため §確定 H §不可逆性 に引っかからない。
        不可逆マスキング経路のラウンドトリップ等価性は :mod:`...test_masking` に持つ。
        """
        workflow = make_workflow()
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(workflow.id)

        assert fetched is not None
        assert fetched == workflow

    async def test_find_by_id_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-004: ``find_by_id(uuid4())`` は例外を投げず ``None`` を返す。"""
        unknown_id = uuid4()
        async with session_factory() as session:
            fetched = await SqliteWorkflowRepository(session).find_by_id(unknown_id)
        assert fetched is None


# ---------------------------------------------------------------------------
# REQ-WFR-002 (BUG-EMR-001 から day 1 で受け継ぐ ORDER BY 契約)
# ---------------------------------------------------------------------------
class TestFindByIdOrderByContract:
    """TC-IT-WFR-005 / 006: ``ORDER BY stage_id`` / ``ORDER BY transition_id`` が発行される。

    empire-repository BUG-EMR-001 のクロージャが ORDER BY 契約を凍結し、
    workflow Repository は PR #1 から踏襲する。これらの句がないと SQLite は
    内部スキャン順で行を返し、``Workflow == Workflow`` ラウンドトリップ等価性
    （Aggregate がリスト同士で比較する）が壊れる。

    **sync** engine に ``before_cursor_execute`` リスナを取り付け、ダイアレクトが
    実際に発行する SQL 文字列を観測する。これにより、行順序が偶然合致して
    ラウンドトリップが pass しても、``ORDER BY`` の静かな除去を検出できる。
    """

    async def _build_multi_stage_workflow(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> tuple[Workflow, WorkflowId]:
        """EXTERNAL_REVIEW なしで 3 ステージ / 2 トランジションの Workflow を構築 + save する。

        構築した workflow とその id を返し、呼び出し側でラウンドトリップさせる。
        ``WORK`` ステージは notify_channels を要求しないため、§確定 H §不可逆性 の罠なし。
        """
        stage_a = make_stage(name="ステージA")
        stage_b = make_stage(name="ステージB")
        stage_c = make_stage(name="ステージC")
        transition_ab = make_transition(
            from_stage_id=stage_a.id,
            to_stage_id=stage_b.id,
        )
        transition_bc = make_transition(
            from_stage_id=stage_b.id,
            to_stage_id=stage_c.id,
        )
        workflow = make_workflow(
            stages=[stage_a, stage_b, stage_c],
            transitions=[transition_ab, transition_bc],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)
        return workflow, workflow.id

    async def test_find_by_id_emits_order_by_stage_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-005: ``find_by_id`` が ``ORDER BY workflow_stages.stage_id`` を発行する。"""
        _, workflow_id = await self._build_multi_stage_workflow(session_factory)

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
                await SqliteWorkflowRepository(session).find_by_id(workflow_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # Workflow の stage SELECT は stage_id カラムに ``ORDER BY`` を持たねばならない。
        # SQLAlchemy が選んで発行する任意の空白 / 完全修飾の表記を許容する。
        stage_selects = [
            stmt for stmt in captured if "FROM workflow_stages" in stmt and "SELECT" in stmt.upper()
        ]
        assert stage_selects, "find_by_id must SELECT from workflow_stages"
        assert any("ORDER BY" in stmt.upper() and "stage_id" in stmt for stmt in stage_selects), (
            "find_by_id must issue ``ORDER BY ... stage_id`` per "
            "detailed-design.md L51 (BUG-EMR-001 from day 1). "
            f"Captured stage SELECTs: {stage_selects}"
        )

    async def test_find_by_id_emits_order_by_transition_id(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-006: ``find_by_id`` が
        ``ORDER BY workflow_transitions.transition_id`` を発行する。"""
        _, workflow_id = await self._build_multi_stage_workflow(session_factory)

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
                await SqliteWorkflowRepository(session).find_by_id(workflow_id)
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        transition_selects = [
            stmt
            for stmt in captured
            if "FROM workflow_transitions" in stmt and "SELECT" in stmt.upper()
        ]
        assert transition_selects, "find_by_id must SELECT from workflow_transitions"
        assert any(
            "ORDER BY" in stmt.upper() and "transition_id" in stmt for stmt in transition_selects
        ), (
            "find_by_id must issue ``ORDER BY ... transition_id`` per "
            "detailed-design.md L51 (BUG-EMR-001 from day 1). "
            f"Captured transition SELECTs: {transition_selects}"
        )


# ---------------------------------------------------------------------------
# REQ-WFR-002 (count() は SQL レベルの COUNT(*) を発行しなければならない)
# ---------------------------------------------------------------------------
class TestCountIssuesScalarCount:
    """TC-IT-WFR-007: ``count()`` は ``SELECT COUNT(*)`` を発行し、行を全件スキャンしない。"""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
    ) -> None:
        """TC-IT-WFR-007: SQL ログが ``count()`` に対し ``SELECT count(*)`` を示す。

        Empire-repository §確定 D 補強: ``count()`` は全行を Python へ
        ストリームして ``len()`` を呼んではならない。Workflow の preset
        ライブラリでは数百行を想定するため、SQL レベルの COUNT(*) パターンが
        Empire 以上に重要。
        """
        # 仮の全行スキャンで少なくとも 2 行がマテリアライズされるよう、
        # 2 つの workflow を save する ── ログに見えるはず。
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())

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
                count = await SqliteWorkflowRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert count == 2
        # count() 中に発行される Workflow SELECT はすべて
        # ``count(*)`` 形でなければならず、Repository が後で
        # ``len()`` する全行 ``SELECT id FROM workflows``
        # ストリームになってはならない。
        workflow_selects = [s for s in captured if "FROM workflows" in s]
        assert workflow_selects, "count() must issue at least one SELECT against workflows"
        for stmt in workflow_selects:
            assert "count(" in stmt.lower(), (
                f"[FAIL] count() emitted a non-COUNT SELECT: {stmt!r}\n"
                f"Next: ensure count() uses select(func.count()).select_from(WorkflowRow) "
                f"per detailed-design.md §確定 D 補強."
            )


# ---------------------------------------------------------------------------
# §確定 D: Repository は singleton 不変条件を強制しない
# ---------------------------------------------------------------------------
class TestRepositoryDoesNotEnforceSingleton:
    """TC-IT-WFR-019: Repository は複数の Workflow save を受け入れる。"""

    async def test_two_workflows_saved_without_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-019: 別個の 2 つの Workflow が save 成功し、``count()`` が 2 を返す。

        Singleton 強制（例: 「empire ごとに preset Workflow は 1 つだけ」）は
        application service の責務。Repository は ``count()`` で事実を返すのみで、
        cardinality が 1 を超えただけで例外を投げてはならない。
        """
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(make_workflow())

        async with session_factory() as session:
            count = await SqliteWorkflowRepository(session).count()
        assert count == 2


# ---------------------------------------------------------------------------
# REQ-WFR-002: save が 3 テーブルに INSERT する (TC-IT-WFR-008)
# ---------------------------------------------------------------------------
class TestSaveInsertsAllThreeTables:
    """TC-IT-WFR-008: ``save`` が 3 つの Workflow テーブルへ書き込む。

    ``workflows`` + ``workflow_stages`` + ``workflow_transitions`` のすべてが
    1 回の ``save`` 呼び出しで行を受け取る。
    """

    async def test_save_populates_three_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-WFR-008: 3 ステージ + 2 トランジションが各テーブルに着地する。

        ここでは V-model ペイロードを意図的に避ける ── EXTERNAL_REVIEW ステージを
        持つため、本テストが notify_channels マスキングの関心事
        （test_masking で扱う）と混同される恐れがあるから。
        """
        stage_a = make_stage(name="A")
        stage_b = make_stage(name="B")
        stage_c = make_stage(name="C")
        transition_ab = make_transition(from_stage_id=stage_a.id, to_stage_id=stage_b.id)
        transition_bc = make_transition(from_stage_id=stage_b.id, to_stage_id=stage_c.id)
        workflow = make_workflow(
            stages=[stage_a, stage_b, stage_c],
            transitions=[transition_ab, transition_bc],
            entry_stage_id=stage_a.id,
        )
        async with session_factory() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)

        async with session_factory() as session:
            workflow_rows = (
                await session.execute(select(WorkflowRow).where(WorkflowRow.id == workflow.id))
            ).all()
            stage_rows = (
                await session.execute(
                    select(WorkflowStageRow).where(WorkflowStageRow.workflow_id == workflow.id)
                )
            ).all()
            transition_rows = (
                await session.execute(
                    select(WorkflowTransitionRow).where(
                        WorkflowTransitionRow.workflow_id == workflow.id
                    )
                )
            ).all()

        assert len(workflow_rows) == 1
        assert len(stage_rows) == 3
        assert len(transition_rows) == 2
