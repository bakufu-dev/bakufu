"""Task Repository: find_blocked (TC-UT-TR-008〜008e)。

REQ-TR-003 / §確定 R1-D:
  * ``find_blocked()`` — SELECT BLOCKED ORDER BY updated_at DESC, id DESC

count_by_status (TC-UT-TR-006) と count_by_room (TC-UT-TR-007) は
``test_count_methods.py`` にある。

``docs/features/task-repository/test-design.md`` 準拠。
Issue #35 — M2 0007。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
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
# TC-UT-TR-008: find_blocked returns only BLOCKED Tasks (§確定 R1-D)
# ---------------------------------------------------------------------------
class TestFindBlocked:
    """TC-UT-TR-008: find_blocked は BLOCKED Task のみを返す; 空 → []; タイブレーカ。"""

    async def test_find_blocked_returns_only_blocked(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008: find_blocked は BLOCKED Task を返す; PENDING/DONE をスキップ。"""
        room_id, directive_id = seeded_task_context
        pending = make_task(room_id=room_id, directive_id=directive_id)
        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error="AuthExpired: token expired",
        )
        done = make_done_task(room_id=room_id, directive_id=directive_id)

        async with session_factory() as session, session.begin():
            repo = SqliteTaskRepository(session)
            await repo.save(pending)
            await repo.save(blocked)
            await repo.save(done)

        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()

        assert len(results) == 1, (
            f"[FAIL] find_blocked が {len(results)} タスクを返した; 期待値は 1 (BLOCKED のみ)。"
        )
        assert results[0].id == blocked.id
        assert results[0].status == TaskStatus.BLOCKED

    async def test_find_blocked_returns_empty_when_none_blocked(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008b: BLOCKED Task がない場合、find_blocked は [] を返す。"""
        room_id, directive_id = seeded_task_context
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_task(room_id=room_id, directive_id=directive_id)
            )

        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()

        assert results == [], f"[FAIL] find_blocked が {results!r} を返したが、[] が期待値。"

    async def test_find_blocked_returns_empty_from_empty_db(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-UT-TR-008b: 空 DB での find_blocked は [] を返す。"""
        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()
        assert results == []

    async def test_find_blocked_emits_status_filter_sql(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        app_engine: AsyncEngine,
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008c: find_blocked SQL ログは WHERE status = 'BLOCKED' ORDER BY を示す。"""
        room_id, directive_id = seeded_task_context
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(
                make_blocked_task(room_id=room_id, directive_id=directive_id)
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
                await SqliteTaskRepository(session).find_blocked()
        finally:
            event.remove(sync_engine, "before_cursor_execute", _on_execute)

        # find_blocked statement は ORDER BY を伴う tasks テーブルを含む必要
        status_stmts = [s for s in captured if "tasks" in s.lower() and "status" in s.lower()]
        assert status_stmts, (
            f"[FAIL] find_blocked() が tasks + status フィルタを伴う SQL を発行しなかった。\n"
            f"キャプチャ: {captured}"
        )
        # ORDER BY が存在する必要（最新優先の DESC 順）
        order_stmts = [s for s in status_stmts if "order by" in s.lower() or "ORDER BY" in s]
        assert order_stmts, (
            f"[FAIL] find_blocked() SQL が ORDER BY 句を欠く。\nstatus_stmts: {status_stmts}"
        )

    async def test_find_blocked_restores_full_attributes(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008d: find_blocked は BLOCKED Task の完全な属性をハイドレート。

        assigned_agent_ids、deliverables、およびすべてのスカラーフィールドを含む。
        """
        room_id, directive_id = seeded_task_context
        agent_id = uuid4()
        stage_id = uuid4()
        deliv = make_deliverable(stage_id=stage_id, body_markdown="# ブロック時成果物")

        blocked = make_blocked_task(
            room_id=room_id,
            directive_id=directive_id,
            last_error="AuthExpired: service token expired after rate limit",
            assigned_agent_ids=[agent_id],
            deliverables={stage_id: deliv},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(blocked)

        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()

        assert len(results) == 1
        restored = results[0]
        assert restored.id == blocked.id
        assert restored.status == TaskStatus.BLOCKED
        assert restored.room_id == blocked.room_id
        assert restored.directive_id == blocked.directive_id
        assert len(restored.assigned_agent_ids) == 1
        assert restored.assigned_agent_ids[0] == agent_id
        assert stage_id in restored.deliverables  # type: ignore[operator]
        assert restored.last_error is not None  # last_error は保存時にマスク
        assert restored.created_at.tzinfo is not None
        assert restored.updated_at.tzinfo is not None

    async def test_find_blocked_tiebreaker_id_desc(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-008e: BUG-EMR-001 規約 — 同じ updated_at → ORDER BY id DESC タイブレーカ。

        同じ updated_at タイムスタンプを持つ 2 つの BLOCKED Task は
        id DESC で順序付けされる必要。16進大の UUID を持つタスクは
        find_blocked() 結果の最初に現れる必要。

        このテストは§確定 R1-K ``ORDER BY updated_at DESC, id DESC`` から
        タイブレーカを物理的にアサートし、構成時に ID とタイムスタンプを制御。
        """
        room_id, directive_id = seeded_task_context

        # 共有 updated_at をピンして、タイブレーカが発動するようにする。
        fixed_ts = datetime(9999, 1, 1, 0, 0, 0, tzinfo=UTC)

        # UUID hex: "ffffffff..." > "00000000..." 辞書順。
        id_high = UUID("ffffffff-ffff-4000-8000-000000000001")
        id_low = UUID("00000000-0000-4000-8000-000000000001")

        task_low = make_blocked_task(
            task_id=id_low,
            room_id=room_id,
            directive_id=directive_id,
            last_error="error low",
            updated_at=fixed_ts,
        )
        task_high = make_blocked_task(
            task_id=id_high,
            room_id=room_id,
            directive_id=directive_id,
            last_error="error high",
            updated_at=fixed_ts,
        )

        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task_low)
            await SqliteTaskRepository(session).save(task_high)

        async with session_factory() as session:
            results = await SqliteTaskRepository(session).find_blocked()

        assert len(results) == 2, f"[FAIL] 2 つの BLOCKED Task が期待値、 {len(results)} を取得"
        # id DESC: id_high は id_low の前に来る必要
        assert results[0].id == id_high, (
            f"[FAIL] タイブレーカ ORDER BY id DESC が違反。\n"
            f"期待値最初: {id_high!r}\n"
            f"実際最初:      {results[0].id!r}\n"
            f"BUG-EMR-001規約: find_blocked ORDER BY updated_at DESC, id DESC は "
            f"updated_at が等しい場合に決定的な順序を生成する必要。"
        )
        assert results[1].id == id_low
