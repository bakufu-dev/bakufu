"""Task Repository: Protocol サーフェス + 基本 CRUD + ライフサイクル。

TC-UT-TR-001〜004/009 + TC-IT-TR-LIFECYCLE.

REQ-TR-001 / REQ-TR-002 ── 6 メソッドの Protocol (§確定 R1-A / §確定 R1-D) +
CRUD (find_by_id / count / save / Tx 境界) + ライフサイクル。

save() の child-table セマンティクス (TC-UT-TR-005/005b/005c) は
``test_save_child_tables.py`` に置く。count_by_status / count_by_room
(TC-UT-TR-006/007) は ``test_count_methods.py`` に置く。

``docs/features/task-repository/test-design.md`` 準拠。
Issue #35 — M2 0007。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.domain.value_objects import TaskStatus
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)
from sqlalchemy import event

from tests.factories.task import (
    make_blocked_task,
    make_deliverable,
    make_done_task,
    make_task,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-TR-001: Protocol 定義 + 6 メソッドサーフェス (§確定 R1-A / §確定 R1-D)
# ---------------------------------------------------------------------------
class TestTaskRepositoryProtocol:
    """TC-UT-TR-001: Protocol が 6 つの async メソッドを宣言する。"""

    async def test_protocol_declares_six_async_methods(self) -> None:
        """TC-UT-TR-001: TaskRepository が必須 6 メソッドをすべて持つ。"""
        for method_name in (
            "find_by_id",
            "count",
            "save",
            "count_by_status",
            "count_by_room",
            "find_blocked",
        ):
            assert hasattr(TaskRepository, method_name), (
                f"[FAIL] TaskRepository.{method_name} missing.\n"
                f"Protocol requires 6 methods per §確定 R1-D."
            )

    async def test_protocol_does_not_have_yagni_methods(self) -> None:
        """TC-UT-TR-001: YAGNI メソッド (find_by_room, find_by_directive) は不在。

        §確定 R1-D で YAGNI 拒否済み: find_by_room は
        ページネーション仕様（未確定）が必要、find_by_directive は
        呼び出し元なし。これらが再出現したら、requirements-analysis
        §確定 R1-D の YAGNI 判断を設計ドキュメントを更新せず反転させた
        ことになる。
        """
        for banned_method in ("find_by_room", "find_by_directive"):
            assert not hasattr(TaskRepository, banned_method), (
                f"[FAIL] TaskRepository.{banned_method} must not exist (YAGNI).\n"
                f"Next: remove from Protocol, or update §確定 R1-D YAGNI 拒否 first."
            )

    async def test_sqlite_repository_satisfies_protocol(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-TR-001: SqliteTaskRepository が TaskRepository Protocol を満たす。"""
        async with session_factory() as session:
            repo: TaskRepository = SqliteTaskRepository(session)
            for method_name in (
                "find_by_id",
                "count",
                "save",
                "count_by_status",
                "count_by_room",
                "find_blocked",
            ):
                assert hasattr(repo, method_name)

    async def test_sqlite_repository_duck_typing_6_methods(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-TR-001: ダックタイピングで実装に 6 メソッドすべての存在を確認する。"""
        async with session_factory() as session:
            repo = SqliteTaskRepository(session)
            for method_name in (
                "find_by_id",
                "count",
                "save",
                "count_by_status",
                "count_by_room",
                "find_blocked",
            ):
                assert hasattr(repo, method_name), (
                    f"[FAIL] SqliteTaskRepository.{method_name} missing."
                )


# ---------------------------------------------------------------------------
# TC-UT-TR-002: find_by_id (REQ-TR-002)
# ---------------------------------------------------------------------------
class TestFindById:
    """TC-UT-TR-002: find_by_id は保存済み Task を取得する。未知の id は None。"""

    async def test_find_by_id_returns_saved_task(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """save(task) → find_by_id(task.id) が Task を返す。"""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            fetched = await SqliteTaskRepository(session).find_by_id(task.id)
        assert fetched is not None
        assert fetched.id == task.id

    async def test_find_by_id_returns_none_for_unknown(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """未知 TaskId での find_by_id は None を返す。"""
        async with session_factory() as session:
            result = await SqliteTaskRepository(session).find_by_id(uuid4())  # type: ignore[arg-type]
        assert result is None


# ---------------------------------------------------------------------------
# TC-UT-TR-003: save ラウンドトリップ ── 全属性 (§確定 R1-H / §確定 R1-J)
# ---------------------------------------------------------------------------
class TestSaveRoundTrip:
    """TC-UT-TR-003: save → find_by_id ですべての Task 属性がラウンドトリップする。"""

    async def test_save_find_by_id_round_trip_all_attributes(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """全スカラー + 子属性が save → find_by_id ラウンドトリップを生き残る。

        §確定 R1-J: _from_rows は assigned_agent_ids（order_index 順）と
        deliverables (dict[StageId, Deliverable]) を再構成する。
        Task ドメインモデルにまだ conversations 属性がないため conversations は空。
        """
        room_id, directive_id = seeded_task_context
        agent1_id = uuid4()
        agent2_id = uuid4()
        stage_id = uuid4()
        deliverable = make_deliverable(stage_id=stage_id, body_markdown="# 成果物本文")

        task = make_task(
            room_id=room_id,
            directive_id=directive_id,
            status=TaskStatus.IN_PROGRESS,
            assigned_agent_ids=[agent1_id, agent2_id],
            deliverables={stage_id: deliverable},  # type: ignore[dict-item]
            last_error=None,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.id == task.id
        assert restored.room_id == task.room_id
        assert restored.directive_id == task.directive_id
        assert restored.current_stage_id == task.current_stage_id
        assert restored.status == task.status
        assert restored.last_error == task.last_error
        assert restored.created_at.tzinfo is not None, (
            "[FAIL] created_at lost timezone info in round-trip."
        )
        assert restored.updated_at.tzinfo is not None, (
            "[FAIL] updated_at lost timezone info in round-trip."
        )
        # §確定 R1-J: assigned_agent_ids は order_index 順で保持される
        assert restored.assigned_agent_ids == [agent1_id, agent2_id], (
            f"[FAIL] assigned_agent_ids order not preserved.\n"
            f"Expected: {[agent1_id, agent2_id]}\nGot: {restored.assigned_agent_ids}"
        )
        # §確定 R1-J: deliverables dict は stage_id をキーとする
        assert stage_id in restored.deliverables, (  # type: ignore[operator]
            f"[FAIL] deliverables dict missing stage_id={stage_id}"
        )
        restored_deliv = restored.deliverables[stage_id]  # type: ignore[index]
        assert restored_deliv.body_markdown == deliverable.body_markdown

    async def test_created_at_is_utc_timezone_aware_after_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """find_by_id 後、created_at / updated_at が UTC tz-aware である。"""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.created_at.tzinfo is not None
        assert restored.updated_at.tzinfo is not None

    async def test_last_error_none_survives_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """last_error=None の PENDING task はラウンドトリップしても None のまま。"""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id, last_error=None)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.last_error is None

    async def test_empty_assigned_agents_survives_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """アサイン agent なしの Task は空リストでラウンドトリップする。"""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id, assigned_agent_ids=[])
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.assigned_agent_ids == []

    async def test_empty_deliverables_survives_round_trip(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """deliverable なしの Task は空 dict でラウンドトリップする。"""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id, deliverables={})
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task.id)

        assert restored is not None
        assert restored.deliverables == {}


# ---------------------------------------------------------------------------
# TC-UT-TR-004: count() の SQL COUNT(*) (empire §確定 D 踏襲)
# ---------------------------------------------------------------------------
class TestCountScalar:
    """TC-UT-TR-004: count() は全行ロード無しに SELECT COUNT(*) を発行する。"""

    async def test_count_emits_select_count_not_full_load(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """count() の SQL ログに COUNT(*) が含まれ、全行 SELECT が含まれない。"""
        room_id, directive_id = seeded_task_context
        for _ in range(3):
            async with session_factory() as session, session.begin():
                await SqliteTaskRepository(session).save(
                    make_task(room_id=room_id, directive_id=directive_id)
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
                result = await SqliteTaskRepository(session).count()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        assert result == 3
        count_stmts = [s for s in captured if "count" in s.lower() and "tasks" in s.lower()]
        assert count_stmts, (
            f"[FAIL] count() did not emit SELECT count(*) FROM tasks.\nCaptured: {captured}"
        )
        # 全行ロード経路は出現してはならない
        full_load_stmts = [
            s
            for s in captured
            if "FROM tasks" in s and "SELECT" in s.upper() and "count" not in s.lower()
        ]
        assert not full_load_stmts, (
            f"[FAIL] count() emitted a full-row SELECT instead of COUNT(*).\n"
            f"Full-load stmts: {full_load_stmts}"
        )


# ---------------------------------------------------------------------------
# TC-UT-TR-009: Tx 境界 (empire §確定 B 踏襲)
# ---------------------------------------------------------------------------
class TestTxBoundary:
    """TC-UT-TR-009: Repository は自動 commit せず、UoW 境界は呼び出し側が所有する。"""

    async def test_save_within_begin_persists(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """async with session.begin() 内の save は行を永続化する。"""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            fetched = await SqliteTaskRepository(session).find_by_id(task.id)
        assert fetched is not None

    async def test_save_without_begin_does_not_persist(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """session.begin() なしの save は session クローズ後に行が残らない。

        begin() がないと SQLAlchemy async session は終了時に自動ロールバックする。
        """
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session:
            # session.begin() なし → __aexit__ で自動ロールバック
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            fetched = await SqliteTaskRepository(session).find_by_id(task.id)
        assert fetched is None, (
            "[FAIL] Repository auto-committed without session.begin().\n"
            "Next: verify save() does not call session.commit()."
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-LIFECYCLE: 6 メソッドのフルライフサイクル
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """TC-IT-TR-LIFECYCLE: 6 メソッドのフルライフサイクル統合。"""

    async def test_full_lifecycle_6_method(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """save x2 → count_by_status → find_blocked → count_by_room → count → 再 save → 検証。"""
        room_id, directive_id = seeded_task_context

        # Step 1: PENDING タスクと BLOCKED タスクを save
        pending = make_task(room_id=room_id, directive_id=directive_id)
        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error="AuthExpired: service token expired",
        )
        async with session_factory() as session, session.begin():
            repo = SqliteTaskRepository(session)
            await repo.save(pending)
            await repo.save(blocked)

        # Step 2: count_by_status の検証
        async with session_factory() as session:
            blocked_count = await SqliteTaskRepository(session).count_by_status(TaskStatus.BLOCKED)
        assert blocked_count == 1

        # Step 3: find_blocked が blocked タスクを返す
        async with session_factory() as session:
            blocked_tasks = await SqliteTaskRepository(session).find_blocked()
        assert len(blocked_tasks) == 1
        assert blocked_tasks[0].id == blocked.id

        # Step 4: count_by_room の検証
        async with session_factory() as session:
            room_count = await SqliteTaskRepository(session).count_by_room(room_id)  # type: ignore[arg-type]
        assert room_count == 2

        # Step 5: count の検証
        async with session_factory() as session:
            total = await SqliteTaskRepository(session).count()
        assert total == 2

        # Step 6: blocked を更新後 status (DONE) で再 save
        done = make_done_task(
            task_id=blocked.id,
            room_id=room_id,
            directive_id=directive_id,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(done)

        # Step 7: find_blocked が [] を返すようになる
        async with session_factory() as session:
            blocked_after = await SqliteTaskRepository(session).find_blocked()
        assert blocked_after == []

        # Step 8: count_by_status(BLOCKED) == 0 の検証
        async with session_factory() as session:
            blocked_count_after = await SqliteTaskRepository(session).count_by_status(
                TaskStatus.BLOCKED
            )
        assert blocked_count_after == 0
