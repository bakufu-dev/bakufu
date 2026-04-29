"""Task Repository: save() 副テーブルセマンティクス (TC-UT-TR-005/005b/005c)。

REQ-TR-001 / §確定 R1-B — 6段階 save() DELETE+UPSERT+INSERT セマンティクス:
  段階 1: DELETE deliverables WHERE task_id = ?
  段階 2: DELETE task_assigned_agents WHERE task_id = ?
  段階 3: UPSERT tasks (ON CONFLICT DO UPDATE 可変フィールド)
  段階 4: INSERT task_assigned_agents (order_index)
  段階 5: INSERT deliverables
  段階 6: INSERT deliverable_attachments

副テーブルは save() 呼び出しのたびに完全に置換される。
deliverables の UNIQUE(task_id, stage_id) は DELETE が INSERT に先行するため安全。

``docs/features/task-repository/test-design.md`` TC-UT-TR-005/005b/005c 準拠。
Issue #35 — M2 0007。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from bakufu.domain.value_objects import TaskStatus
from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
    SqliteTaskRepository,
)

from tests.factories.task import (
    make_deliverable,
    make_in_progress_task,
    make_task,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-UT-TR-005: save() 6-stage DELETE+UPSERT+INSERT semantics (§確定 R1-B)
# ---------------------------------------------------------------------------
class TestSaveChildTableSemantics:
    """TC-UT-TR-005/005b/005c: save() 6段階の順序と再保存 UPSERT セマンティクス。"""

    async def test_resave_updates_scalar_fields(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """Task を再保存すると可変スカラーフィールドが更新される (ON CONFLICT DO UPDATE)。

        段階 3 (UPSERT) をテスト: current_stage_id / status / last_error / updated_at
        は更新される; room_id / directive_id / created_at は更新されない。
        """
        room_id, directive_id = seeded_task_context
        original = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(original)

        # 異なるステータスで再保存 (PENDING → IN_PROGRESS via factory bypass)
        updated = make_in_progress_task(
            task_id=original.id,
            room_id=room_id,
            directive_id=directive_id,
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(original.id)

        assert restored is not None
        assert restored.status == TaskStatus.IN_PROGRESS
        # room_id / directive_id / created_at は元のまま (不変)
        assert restored.room_id == original.room_id
        assert restored.directive_id == original.directive_id

    async def test_resave_does_not_duplicate_task_rows(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """同じ task_id の再保存は tasks 行を重複させない (UPSERT)。"""
        room_id, directive_id = seeded_task_context
        task = make_task(room_id=room_id, directive_id=directive_id)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task)

        async with session_factory() as session:
            count = await SqliteTaskRepository(session).count()
        assert count == 1, f"[FAIL] Re-saving a Task duplicated the row. count={count}"

    async def test_resave_reinsertes_child_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """異なる assigned_agents での再保存は task_assigned_agents を再挿入。

        段階 2 (DELETE task_assigned_agents) + 段階 4 (新しいエージェントを INSERT) をテスト。
        元のエージェントがクリアされ、新しいエージェントが書き込まれる。
        """
        room_id, directive_id = seeded_task_context
        agent_a = uuid4()
        agent_b = uuid4()
        agent_c = uuid4()

        original = make_task(
            room_id=room_id, directive_id=directive_id, assigned_agent_ids=[agent_a]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(original)

        # 異なるエージェントで再保存
        updated = make_in_progress_task(
            task_id=original.id,
            room_id=room_id,
            directive_id=directive_id,
            assigned_agent_ids=[agent_b, agent_c],
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(updated)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(original.id)

        assert restored is not None
        assert restored.assigned_agent_ids == [agent_b, agent_c], (
            f"[FAIL] assigned_agent_ids not updated after re-save.\n"
            f"Expected: {[agent_b, agent_c]}\nGot: {restored.assigned_agent_ids}"
        )

    async def test_resave_deliverable_unique_constraint_no_duplicate(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-005b: 同じ stage_id の納品物の再保存は UNIQUE 違反にならない。

        UNIQUE(task_id, stage_id) 制約: 段階 1 は古い納品物行をDELETE、
        段階 5 は新しい行をINSERT。DELETE が INSERT の前に行われるため
        UNIQUE 違反は発生しない。
        """
        room_id, directive_id = seeded_task_context
        stage_id = uuid4()
        deliv_v1 = make_deliverable(stage_id=stage_id, body_markdown="# バージョン1")
        task_v1 = make_task(
            room_id=room_id,
            directive_id=directive_id,
            deliverables={stage_id: deliv_v1},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task_v1)

        deliv_v2 = make_deliverable(stage_id=stage_id, body_markdown="# バージョン2")
        task_v2 = make_task(
            task_id=task_v1.id,
            room_id=room_id,
            directive_id=directive_id,
            deliverables={stage_id: deliv_v2},  # type: ignore[dict-item]
        )
        # IntegrityError (UNIQUE 制約) を発生させてはならない
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(task_v2)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(task_v1.id)

        assert restored is not None
        assert restored.deliverables[stage_id].body_markdown == "# バージョン2", (  # type: ignore[index]
            "[FAIL] 再保存後に Deliverable body_markdown が更新されていない。"
        )

    async def test_resave_empty_to_full_task_all_child_tables(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        seeded_task_context: tuple[UUID, UUID],
    ) -> None:
        """TC-UT-TR-005c: 空 Task → 満杯 Task (エージェント + 納品物) の再保存。"""
        room_id, directive_id = seeded_task_context
        # 最初は空
        empty_task = make_task(
            room_id=room_id,
            directive_id=directive_id,
            assigned_agent_ids=[],
            deliverables={},
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(empty_task)

        # エージェント + 納品物で再保存
        stage_id = uuid4()
        deliv = make_deliverable(stage_id=stage_id)
        full_task = make_in_progress_task(
            task_id=empty_task.id,
            room_id=room_id,
            directive_id=directive_id,
            assigned_agent_ids=[uuid4(), uuid4()],
            deliverables={stage_id: deliv},  # type: ignore[dict-item]
        )
        async with session_factory() as session, session.begin():
            await SqliteTaskRepository(session).save(full_task)

        async with session_factory() as session:
            restored = await SqliteTaskRepository(session).find_by_id(empty_task.id)

        assert restored is not None
        assert len(restored.assigned_agent_ids) == 2
        assert stage_id in restored.deliverables  # type: ignore[operator]
