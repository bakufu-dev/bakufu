"""Alembic 7th revision tests — task aggregate (TC-IT-TR-001〜009).

REQ-TR-005 / §確定 R1-B / §確定 R1-C / §確定 R1-K / §設計決定 TR-001.

Real Alembic upgrade/downgrade against a real SQLite file plus chain
integrity check that makes sure 0001→…→0007 chain stays linear.

Also verifies:
* 4 tables created: tasks / task_assigned_agents / deliverables /
  deliverable_attachments (conversations / conversation_messages は §BUG-TR-002
  凍結済みのため除外).
* 2 indexes: ix_tasks_room_id / ix_tasks_status_updated_id (§確定 R1-K).
* tasks FK constraints: room_id → rooms CASCADE, directive_id → directives CASCADE.
* BUG-DRR-001 FK closure: directives.task_id → tasks.id present at HEAD (0007).
* §設計決定 TR-001: task_assigned_agents.agent_id has NO FK to agents.

Per ``docs/features/task-repository/test-design.md`` TC-IT-TR-001〜009.
Issue #35 — M2 0007.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite.migrations import run_upgrade_head
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def empty_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Fresh app engine with no migrations applied."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'bakufu.db'}"
    engine = engine_mod.create_engine(url)
    try:
        yield engine
    finally:
        await engine.dispose()


def _alembic_config() -> Config:
    """Resolve bakufu Alembic config for ScriptDirectory inspection."""
    backend_root = Path(__file__).resolve().parents[4]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    return cfg


# ---------------------------------------------------------------------------
# TC-IT-TR-001: 0007 creates 4 task tables (受入基準 §確定 R1-B)
# conversations / conversation_messages は §BUG-TR-002 凍結 (YAGNI)
# ---------------------------------------------------------------------------
class TestSeventhRevisionFourTablesPresent:
    """TC-IT-TR-001: alembic upgrade head adds the 4 Task-aggregate tables.

    conversations / conversation_messages are §BUG-TR-002 凍結:
    Task domain model has no conversations attribute; these tables are
    NOT created by 0007_task_aggregate (deferred to feature/conversation-repository).
    """

    async def test_four_task_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """4 task tables exist after upgrade head (§BUG-TR-002: conversations excluded)."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}

        expected = {
            "tasks",
            "task_assigned_agents",
            "deliverables",
            "deliverable_attachments",
        }
        assert expected.issubset(tables), (
            f"[FAIL] Missing task aggregate tables after upgrade head.\n"
            f"Missing: {expected - tables}\n"
            f"Tables found: {tables}"
        )
        # Verify §BUG-TR-002: conversations / conversation_messages must NOT exist yet.
        assert "conversations" not in tables, (
            "[FAIL] conversations table exists but §BUG-TR-002 requires it to be excluded."
        )
        assert "conversation_messages" not in tables, (
            "[FAIL] conversation_messages table exists but §BUG-TR-002 requires it to be excluded."
        )

    async def test_conversations_and_messages_tables_absent_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """§BUG-TR-002 凍結: conversations / conversation_messages must NOT exist.

        Task PR #35 intentionally omits these tables (YAGNI — no conversations
        attribute on Task domain model). They are deferred to the
        feature/conversation-repository PR. If they appear here, the YAGNI
        decision was violated.
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}

        for absent_table in ("conversations", "conversation_messages"):
            assert absent_table not in tables, (
                f"[FAIL] {absent_table!r} table must NOT exist after 0007_task_aggregate.\n"
                f"§BUG-TR-002 凍結: deferred to feature/conversation-repository PR.\n"
                f"Tables found: {tables}"
            )


# ---------------------------------------------------------------------------
# TC-IT-TR-002: 2 indexes on tasks (§確定 R1-K)
# ---------------------------------------------------------------------------
class TestTaskIndexesPresent:
    """TC-IT-TR-002: ix_tasks_room_id and ix_tasks_status_updated_id exist."""

    async def test_ix_tasks_room_id_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """ix_tasks_room_id single-column index exists on tasks."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks'")
            )
            index_names = {row[0] for row in result}
        assert "ix_tasks_room_id" in index_names, (
            f"[FAIL] ix_tasks_room_id missing on tasks.\n"
            f"Indexes found: {index_names}\n"
            f"Next: ensure op.create_index('ix_tasks_room_id', ...) in 0007."
        )

    async def test_ix_tasks_status_updated_id_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """ix_tasks_status_updated_id composite index (status, updated_at, id) exists."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tasks'")
            )
            index_names = {row[0] for row in result}
        assert "ix_tasks_status_updated_id" in index_names, (
            f"[FAIL] ix_tasks_status_updated_id missing on tasks.\n"
            f"Indexes found: {index_names}\n"
            f"Next: ensure op.create_index('ix_tasks_status_updated_id', 'tasks', "
            f"['status', 'updated_at', 'id']) in 0007 upgrade()."
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-003: tasks FK constraints (→rooms CASCADE, →directives CASCADE)
# ---------------------------------------------------------------------------
class TestTaskForeignKeys:
    """TC-IT-TR-003: tasks.room_id → rooms CASCADE and tasks.directive_id → directives CASCADE."""

    async def test_tasks_room_id_fk_to_rooms(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """PRAGMA foreign_key_list('tasks') shows FK → rooms."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('tasks')"))
            fk_rows = list(result)
        referenced_tables = {row[2] for row in fk_rows}
        assert "rooms" in referenced_tables, (
            f"[FAIL] tasks has no FK to rooms.\nFK references found: {referenced_tables}"
        )

    async def test_tasks_directive_id_fk_to_directives(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """PRAGMA foreign_key_list('tasks') shows FK → directives."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('tasks')"))
            fk_rows = list(result)
        referenced_tables = {row[2] for row in fk_rows}
        assert "directives" in referenced_tables, (
            f"[FAIL] tasks has no FK to directives.\nFK references found: {referenced_tables}"
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-004: Alembic chain 0001→…→0007 single head (分岐なし)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """TC-IT-TR-004: 0001→0002→…→0007 single-head chain."""

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """ScriptDirectory.get_heads() returns exactly one revision."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"[FAIL] Alembic head must be linear; got branched heads {heads}.\n"
            f"Each Aggregate Repository PR appends a single revision."
        )

    async def test_chain_walks_from_0007_back_to_base(self) -> None:
        """Walking down_revision from 0007 reaches base in 7 hops."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        chain: list[str] = []
        current_id: str | None = "0007_task_aggregate"
        for _ in range(15):
            if current_id is None:
                break
            rev = script.get_revision(current_id)
            assert rev is not None, f"Revision {current_id!r} not found"
            chain.append(rev.revision)
            down = rev.down_revision
            if isinstance(down, tuple | list):
                pytest.fail(f"Revision {rev.revision!r} has multiple down_revisions {down}")
            current_id = down  # pyright: ignore[reportAssignmentType]

        assert chain == [
            "0007_task_aggregate",
            "0006_directive_aggregate",
            "0005_room_aggregate",
            "0004_agent_aggregate",
            "0003_workflow_aggregate",
            "0002_empire_aggregate",
            "0001_init",
        ], f"Unexpected revision chain: {chain}"


# ---------------------------------------------------------------------------
# TC-IT-TR-005: upgrade/downgrade idempotent
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """TC-IT-TR-005: upgrade head → downgrade base → upgrade head again."""

    async def test_full_cycle_leaves_task_tables_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """upgrade head → downgrade base → upgrade head — task tables survive."""
        await run_upgrade_head(empty_engine)

        from alembic import command  # local import to avoid global side effects

        cfg = _alembic_config()
        url = str(empty_engine.url)
        cfg.set_main_option("sqlalchemy.url", url)

        def _do_downgrade() -> None:
            command.downgrade(cfg, "base")

        await asyncio.to_thread(_do_downgrade)

        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert "tasks" not in tables, (
            f"[FAIL] tasks table still present after downgrade to base.\nTables: {tables}"
        )

        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        expected = {
            "tasks",
            "task_assigned_agents",
            "deliverables",
            "deliverable_attachments",
        }
        assert expected.issubset(tables), (
            f"[FAIL] task tables missing after re-upgrade.\nMissing: {expected - tables}"
        )
        # §BUG-TR-002 凍結: conversations / conversation_messages must remain absent
        for absent_table in ("conversations", "conversation_messages"):
            assert absent_table not in tables, (
                f"[FAIL] {absent_table!r} must NOT exist after re-upgrade.\n"
                f"§BUG-TR-002 凍結: deferred to feature/conversation-repository PR."
            )


# ---------------------------------------------------------------------------
# TC-IT-TR-006: 0007.down_revision == "0006_directive_aggregate"
# ---------------------------------------------------------------------------
class TestDownRevision:
    """TC-IT-TR-006: 0007_task_aggregate chains onto 0006_directive_aggregate."""

    async def test_0007_revision_has_correct_down_revision(self) -> None:
        """0007_task_aggregate.down_revision == '0006_directive_aggregate'."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0007_task_aggregate")
        assert rev is not None
        assert rev.down_revision == "0006_directive_aggregate", (
            f"[FAIL] 0007_task_aggregate.down_revision is {rev.down_revision!r}; "
            f"expected '0006_directive_aggregate'."
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-007: Room CASCADE → tasks deleted (受入基準 §確定 R1-C)
# ---------------------------------------------------------------------------
class TestRoomCascadeDeletesTask:
    """TC-IT-TR-007: Deleting a Room auto-deletes its Tasks (CASCADE)."""

    async def test_room_deletion_cascades_to_tasks(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """DELETE FROM rooms → Task row automatically deleted (CASCADE).

        Inserts empire → workflow → room → directive → task via raw SQL to
        avoid Repository layer dependencies. Then DELETEs the room and
        verifies the task row disappears due to ON DELETE CASCADE.
        """
        await run_upgrade_head(empty_engine)

        empire_id = uuid4().hex
        workflow_id = uuid4().hex
        room_id = uuid4().hex
        directive_id = uuid4().hex
        task_id = uuid4().hex
        now = datetime.now(UTC).isoformat()

        async with empty_engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            await conn.execute(
                text("INSERT INTO empires (id, name) VALUES (:id, :name)"),
                {"id": empire_id, "name": "test_empire"},
            )
            await conn.execute(
                text(
                    "INSERT INTO workflows (id, name, entry_stage_id) "
                    "VALUES (:id, :name, :entry_stage_id)"
                ),
                {"id": workflow_id, "name": "test_workflow", "entry_stage_id": workflow_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO rooms (id, empire_id, workflow_id, name, description, "
                    "prompt_kit_prefix_markdown, archived) "
                    "VALUES (:id, :eid, :wid, :name, '', '', 0)"
                ),
                {"id": room_id, "eid": empire_id, "wid": workflow_id, "name": "test_room"},
            )
            await conn.execute(
                text(
                    "INSERT INTO directives (id, text, target_room_id, created_at, task_id) "
                    "VALUES (:id, :text, :room_id, :created_at, NULL)"
                ),
                {"id": directive_id, "text": "テスト指令", "room_id": room_id, "created_at": now},
            )
            await conn.execute(
                text(
                    "INSERT INTO tasks (id, room_id, directive_id, current_stage_id, "
                    "status, last_error, created_at, updated_at) "
                    "VALUES (:id, :room_id, :directive_id, :stage_id, :status, "
                    "NULL, :created_at, :updated_at)"
                ),
                {
                    "id": task_id,
                    "room_id": room_id,
                    "directive_id": directive_id,
                    "stage_id": uuid4().hex,
                    "status": "PENDING",
                    "created_at": now,
                    "updated_at": now,
                },
            )

        # Verify task exists before delete
        async with empty_engine.connect() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            result = await conn.execute(
                text("SELECT id FROM tasks WHERE id = :id"),
                {"id": task_id},
            )
            assert result.first() is not None, "Task must exist before CASCADE test"

        # Delete the room — CASCADE should remove the task
        async with empty_engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            await conn.execute(
                text("DELETE FROM rooms WHERE id = :id"),
                {"id": room_id},
            )

        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT id FROM tasks WHERE id = :id"),
                {"id": task_id},
            )
            remaining = result.first()
        assert remaining is None, (
            "[FAIL] Task row still exists after Room deletion.\n"
            "tasks.room_id → rooms.id ON DELETE CASCADE is not working.\n"
            "Next: verify ForeignKey('rooms.id', ondelete='CASCADE') in tables/tasks.py."
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-008: BUG-DRR-001 closure — directives.task_id FK to tasks present
# ---------------------------------------------------------------------------
class TestBugDrr001FkClosureAtHead:
    """TC-IT-TR-008: directives.task_id → tasks.id FK exists at HEAD (0007).

    BUG-DRR-001: at 0006 level, directives.task_id had no FK because
    the tasks table did not exist yet. 0007_task_aggregate closes this
    via op.batch_alter_table('directives', recreate='always') adding
    fk_directives_task_id (directives.task_id → tasks.id ON DELETE RESTRICT).
    """

    async def test_directives_task_id_fk_present_at_head(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """PRAGMA foreign_key_list('directives') has reference to 'tasks' at HEAD."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('directives')"))
            fk_rows = list(result)
        referenced_tables = {row[2] for row in fk_rows}
        assert "tasks" in referenced_tables, (
            f"[FAIL] directives.task_id FK to 'tasks' missing at HEAD level (0007).\n"
            f"BUG-DRR-001 closure requires 0007_task_aggregate to add FK via "
            f"op.batch_alter_table('directives') + create_foreign_key('fk_directives_task_id', "
            f"'tasks', ['task_id'], ['id'], ondelete='RESTRICT').\n"
            f"FK references found: {referenced_tables}"
        )


# ---------------------------------------------------------------------------
# TC-IT-TR-009: §設計決定 TR-001 — task_assigned_agents.agent_id has NO FK to agents
# ---------------------------------------------------------------------------
class TestDesignDecisionTr001AgentFkAbsent:
    """TC-IT-TR-009: §設計決定 TR-001 — task_assigned_agents.agent_id has no FK to agents.

    §設計決定 TR-001 rationale: room_members.agent_id は agents テーブルへの FK なし
    の前例と同方針。archived agent の CASCADE 削除が task_assigned_agents を巻き
    込む危険性を避けるため、FK は設計決定として意図的に省略した (BUG 扱いではない)。

    This test physically confirms the absence at HEAD (0007).
    """

    async def test_task_assigned_agents_has_no_agent_fk(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """PRAGMA foreign_key_list('task_assigned_agents') has NO reference to 'agents'.

        §設計決定 TR-001: task_assigned_agents.agent_id intentionally has no FK
        onto agents.id. Cascade-deleting an archived agent must not silently
        wipe task assignment history (same rationale as room_members.agent_id).
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('task_assigned_agents')"))
            fk_rows = list(result)
        referenced_tables = {row[2] for row in fk_rows}
        assert "agents" not in referenced_tables, (
            f"[FAIL] task_assigned_agents.agent_id has an unexpected FK to agents.\n"
            f"§設計決定 TR-001 prohibits this FK (archived agent cascade danger).\n"
            f"FK references found: {referenced_tables}\n"
            f"If this FK was added intentionally, update §設計決定 TR-001 in the "
            f"detailed-design.md first."
        )
        # Only tasks FK should be present (via task_id → tasks.id ON DELETE CASCADE)
        assert "tasks" in referenced_tables, (
            f"[FAIL] task_assigned_agents.task_id FK to tasks missing.\n"
            f"FK references found: {referenced_tables}"
        )
