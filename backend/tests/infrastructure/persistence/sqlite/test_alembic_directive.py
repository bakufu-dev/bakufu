"""Alembic 6th revision tests — directive aggregate (TC-IT-DRR-001〜006).

REQ-DRR-003 / §確定 R1-B / §確定 R1-C.

Real Alembic upgrade/downgrade against a real SQLite file, plus chain
integrity check that makes sure the 0001→…→0006 chain stays linear.

Also verifies:
* ``directives`` table created with correct columns.
* ``ix_directives_target_room_id_created_at`` composite index present.
* ``target_room_id`` FK → ``rooms.id`` ON DELETE CASCADE exists.
* §BUG-DRR-001: ``task_id → tasks.id`` FK does NOT exist at 0006 level.

Per ``docs/features/directive-repository/test-design.md`` TC-IT-DRR-001〜006.
Issue #34 — M2 0006.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

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
    """Bring up a fresh app engine without running any migrations."""
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
# TC-IT-DRR-001: 0006 creates directives table + INDEX + FK (受入基準 9)
# ---------------------------------------------------------------------------
class TestSixthRevisionApplied:
    """TC-IT-DRR-001: alembic upgrade head adds the Directive schema."""

    async def test_directives_table_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """``directives`` table exists after upgrade head."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert "directives" in tables, (
            f"[FAIL] directives table missing after upgrade head.\nTables found: {tables}"
        )

    async def test_directives_composite_index_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """``ix_directives_target_room_id_created_at`` composite index exists (§確定 R1-D)."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='directives'")
            )
            index_names = {row[0] for row in result}
        assert "ix_directives_target_room_id_created_at" in index_names, (
            f"[FAIL] ix_directives_target_room_id_created_at index missing on directives.\n"
            f"Indexes found: {index_names}\n"
            f"Next: ensure op.create_index(...) is in 0006_directive_aggregate.py upgrade()."
        )

    async def test_directives_fk_to_rooms_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """PRAGMA foreign_key_list('directives') shows FK → rooms (§確定 R1-B)."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('directives')"))
            fk_rows = list(result)
        # PRAGMA foreign_key_list columns: id, seq, table, from, to, ...
        referenced_tables = {row[2] for row in fk_rows}
        assert "rooms" in referenced_tables, (
            f"[FAIL] directives has no FK to rooms (§確定 R1-B).\n"
            f"FK references found: {referenced_tables}\n"
            f"Next: verify ForeignKey('rooms.id', ondelete='CASCADE') in 0006."
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-002: Alembic chain 0001→...→0006 single head (分岐なし)
# ---------------------------------------------------------------------------
class TestRevisionChainLinear:
    """TC-IT-DRR-002: 0001→0002→0003→0004→0005→0006 single-head chain."""

    async def test_alembic_heads_returns_single_revision(self) -> None:
        """ScriptDirectory.get_heads() returns exactly one revision."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"[FAIL] Alembic head must be linear; got branched heads {heads}.\n"
            f"Each Aggregate Repository PR appends a single revision."
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-003: upgrade/downgrade idempotent (受入基準 9)
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """TC-IT-DRR-003: upgrade head → downgrade base → upgrade head again."""

    async def test_full_cycle_leaves_directives_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """upgrade head → downgrade base → upgrade head — directives survives."""
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
        assert "directives" not in tables, (
            f"[FAIL] directives still present after downgrade to base.\nTables: {tables}"
        )

        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert "directives" in tables, (
            f"[FAIL] directives missing after re-upgrade.\nTables: {tables}"
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-004: 0006.down_revision == "0005_room_aggregate"
# ---------------------------------------------------------------------------
class TestDownRevision:
    """TC-IT-DRR-004: 0006_directive_aggregate chains onto 0005_room_aggregate."""

    async def test_0006_revision_has_correct_down_revision(self) -> None:
        """0006_directive_aggregate.down_revision == '0005_room_aggregate'."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        rev = script.get_revision("0006_directive_aggregate")
        assert rev is not None
        assert rev.down_revision == "0005_room_aggregate", (
            f"[FAIL] 0006_directive_aggregate.down_revision is {rev.down_revision!r}; "
            f"expected '0005_room_aggregate'."
        )

    async def test_chain_walks_from_0006_back_to_base(self) -> None:
        """Walking down_revision from 0006 reaches base in 6 hops."""
        cfg = _alembic_config()
        script = ScriptDirectory.from_config(cfg)
        chain: list[str] = []
        current_id: str | None = "0006_directive_aggregate"
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
            "0006_directive_aggregate",
            "0005_room_aggregate",
            "0004_agent_aggregate",
            "0003_workflow_aggregate",
            "0002_empire_aggregate",
            "0001_init",
        ], f"Unexpected revision chain: {chain}"


# ---------------------------------------------------------------------------
# TC-IT-DRR-005: target_room_id FK ON DELETE CASCADE (§確定 R1-B, 受入基準 10)
# ---------------------------------------------------------------------------
class TestCascadeDeleteOnRoomDeletion:
    """TC-IT-DRR-005: Deleting a Room auto-deletes its Directives (CASCADE)."""

    async def test_room_deletion_cascades_to_directives(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """DELETE FROM rooms → Directive rows automatically deleted (CASCADE).

        Inserts empire → workflow → room → directive via raw SQL to avoid
        Repository layer dependencies. Then DELETEs the room and verifies
        the directive row disappears due to ON DELETE CASCADE.
        """
        from uuid import uuid4

        await run_upgrade_head(empty_engine)

        empire_id = uuid4().hex
        workflow_id = uuid4().hex
        room_id = uuid4().hex
        directive_id = uuid4().hex
        from datetime import UTC, datetime

        created_at = datetime.now(UTC).isoformat()

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
                {
                    "id": directive_id,
                    "text": "テスト指令",
                    "room_id": room_id,
                    "created_at": created_at,
                },
            )

        # Verify directive exists before delete
        async with empty_engine.connect() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            result = await conn.execute(
                text("SELECT id FROM directives WHERE id = :id"),
                {"id": directive_id},
            )
            assert result.first() is not None, "Directive must exist before CASCADE test"

        # Delete the room — CASCADE should remove the directive
        async with empty_engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            await conn.execute(
                text("DELETE FROM rooms WHERE id = :id"),
                {"id": room_id},
            )

        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT id FROM directives WHERE id = :id"),
                {"id": directive_id},
            )
            remaining = result.first()
        assert remaining is None, (
            "[FAIL] Directive row still exists after Room deletion.\n"
            "directives.target_room_id → rooms.id ON DELETE CASCADE is not working.\n"
            "Next: verify ForeignKey('rooms.id', ondelete='CASCADE') in tables/directives.py."
        )


# ---------------------------------------------------------------------------
# TC-IT-DRR-006: §BUG-DRR-001 — task_id FK does NOT exist at 0006 (受入基準 11)
# ---------------------------------------------------------------------------
class TestBugDrr001TaskIdFkClosure:
    """TC-IT-DRR-006: BUG-DRR-001 closure confirmed — directives.task_id FK now present.

    §BUG-DRR-001 (BUG-EMR-001 パターン): was OPEN at 0006 level (tasks table did
    not exist). Alembic revision 0007_task_aggregate closed this by adding
    ``fk_directives_task_id`` (``directives.task_id → tasks.id`` ON DELETE RESTRICT)
    via ``op.batch_alter_table('directives')``.

    This test physically confirms the closure: at HEAD (0007), the FK IS present.
    TC-IT-TR-008 in test_alembic_task.py is the canonical closure test; this test
    confirms the directive side is consistent with that assertion.
    """

    async def test_task_id_fk_present_in_directives_at_head(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """PRAGMA foreign_key_list('directives') has reference to 'tasks' at HEAD.

        BUG-DRR-001 closure: 0007_task_aggregate added the FK via batch_alter_table.
        At upgrade head (0007), directives.task_id → tasks.id FK must exist.
        """
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('directives')"))
            fk_rows = list(result)
        # PRAGMA foreign_key_list columns: id, seq, table, from, to, ...
        referenced_tables = {row[2] for row in fk_rows}
        assert "tasks" in referenced_tables, (
            f"[FAIL] directives.task_id FK to 'tasks' missing at HEAD level.\n"
            f"BUG-DRR-001 closure requires 0007_task_aggregate to add FK via "
            f"op.batch_alter_table('directives') + create_foreign_key('fk_directives_task_id', "
            f"'tasks', ['task_id'], ['id'], ondelete='RESTRICT').\n"
            f"FK references found: {referenced_tables}"
        )

    async def test_task_id_column_exists_as_nullable(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """task_id column exists in directives but is nullable with no FK."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA table_info('directives')"))
            columns = {row[1]: {"notnull": row[3], "dflt": row[4]} for row in result}
        assert "task_id" in columns, (
            f"[FAIL] task_id column missing from directives.\nColumns found: {list(columns.keys())}"
        )
        assert columns["task_id"]["notnull"] == 0, (
            "[FAIL] task_id must be nullable at 0006 level (§BUG-DRR-001)."
        )
