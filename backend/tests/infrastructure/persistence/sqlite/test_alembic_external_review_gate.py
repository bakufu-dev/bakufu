"""Alembic 8th revision tests — ExternalReviewGate aggregate (TC-IT-ERGR-001〜008).

RQ-ERGR-007 / §確定 R1-B / §確定 R1-K / §設計決定 ERGR-001.

Real Alembic upgrade/downgrade against a real SQLite file plus chain
integrity check that makes sure 0001→…→0008 chain stays linear.

Also verifies:
* 3 tables created: external_review_gates / external_review_gate_attachments /
  external_review_audit_entries.
* 3 indexes: ix_external_review_gates_task_id_created /
  ix_external_review_gates_reviewer_decision /
  ix_external_review_gates_decision.
* FK: external_review_gates.task_id → tasks.id ON DELETE CASCADE.
* §設計決定 ERGR-001: reviewer_id / snapshot_committed_by have NO FK.
* 0008.down_revision == "0007_task_aggregate".
* upgrade → downgrade → upgrade is idempotent.
* Task CASCADE: deleting task removes associated Gates.

Per ``docs/features/external-review-gate-repository/test-design.md``
TC-IT-ERGR-001〜008.
Issue #36 — M2 0008.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
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
# TC-IT-ERGR-001: 0008 creates 3 ExternalReviewGate tables (受入基準 6)
# ---------------------------------------------------------------------------
class TestEighthRevisionThreeTablesPresent:
    """TC-IT-ERGR-001: alembic upgrade head adds the 3 ExternalReviewGate tables."""

    async def test_three_erg_tables_present_after_upgrade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-ERGR-001: 3 ERG tables exist after upgrade head."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}

        expected = {
            "external_review_gates",
            "external_review_gate_attachments",
            "external_review_audit_entries",
        }
        assert expected.issubset(tables), (
            f"[FAIL] Missing ExternalReviewGate tables after upgrade head.\n"
            f"Missing: {expected - tables}\n"
            f"Tables found: {tables}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-002: 3 INDEXes on external_review_gates (§確定 R1-K)
# ---------------------------------------------------------------------------
class TestExternalReviewGateIndexesPresent:
    """TC-IT-ERGR-002: All 3 required INDEXes exist on external_review_gates."""

    async def test_three_indexes_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-ERGR-002: ix_task_id_created / ix_reviewer_decision / ix_decision exist."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master"
                    " WHERE type='index' AND tbl_name='external_review_gates'"
                )
            )
            index_names = {row[0] for row in result}

        expected_indexes = {
            "ix_external_review_gates_task_id_created",
            "ix_external_review_gates_reviewer_decision",
            "ix_external_review_gates_decision",
        }
        assert expected_indexes.issubset(index_names), (
            f"[FAIL] Missing INDEXes on external_review_gates.\n"
            f"Missing: {expected_indexes - index_names}\n"
            f"Indexes found: {index_names}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-003: FK external_review_gates.task_id → tasks.id CASCADE
# ---------------------------------------------------------------------------
class TestExternalReviewGateForeignKey:
    """TC-IT-ERGR-003: external_review_gates.task_id → tasks.id ON DELETE CASCADE."""

    async def test_task_id_fk_to_tasks_cascade(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-ERGR-003: PRAGMA foreign_key_list confirms tasks CASCADE FK."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('external_review_gates')"))
            fk_list = [dict(row._mapping) for row in result]

        tasks_fks = [fk for fk in fk_list if fk.get("table") == "tasks"]
        assert len(tasks_fks) >= 1, (
            f"[FAIL] No FK from external_review_gates to tasks found.\nFK list: {fk_list}"
        )
        cascade_fk = next(
            (fk for fk in tasks_fks if fk.get("on_delete", "").upper() == "CASCADE"),
            None,
        )
        assert cascade_fk is not None, (
            f"[FAIL] tasks FK missing ON DELETE CASCADE.\ntasks FKs: {tasks_fks}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-004: Alembic chain 0001→...→0008 is a single head
# ---------------------------------------------------------------------------
class TestAlembicChainSingleHead:
    """TC-IT-ERGR-004: ScriptDirectory has exactly 1 head (no branch divergence)."""

    def test_alembic_chain_has_single_head(self) -> None:
        """TC-IT-ERGR-004: len(heads) == 1 — chain is linear 0001→...→0008."""
        cfg = _alembic_config()
        script_dir = ScriptDirectory.from_config(cfg)
        heads = script_dir.get_heads()
        assert len(heads) == 1, (
            f"[FAIL] Alembic chain has {len(heads)} heads (expected 1).\n"
            f"Heads: {heads}\n"
            f"Branching means two revisions both point to the same down_revision."
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-005: upgrade → downgrade → upgrade is idempotent (受入基準 6)
# ---------------------------------------------------------------------------
class TestUpgradeDowngradeIdempotent:
    """TC-IT-ERGR-005: upgrade head → downgrade base → upgrade head restores 3 tables."""

    async def test_upgrade_downgrade_upgrade_idempotent(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-ERGR-005: Double migration cycle — final state has 3 ERG tables."""
        import asyncio

        from alembic import command as alembic_command

        await run_upgrade_head(empty_engine)

        # Downgrade to base via alembic command (runs in a thread to avoid event-loop deadlock)
        cfg = _alembic_config()
        cfg.set_main_option("sqlalchemy.url", str(empty_engine.url))

        def _do_downgrade() -> None:
            alembic_command.downgrade(cfg, "base")

        await asyncio.to_thread(_do_downgrade)

        # Verify ERG tables are gone after downgrade
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables_after_down = {row[0] for row in result}
        assert "external_review_gates" not in tables_after_down, (
            f"[FAIL] external_review_gates still present after downgrade to base.\n"
            f"Tables: {tables_after_down}"
        )

        # Re-upgrade
        await run_upgrade_head(empty_engine)

        async with empty_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}

        expected = {
            "external_review_gates",
            "external_review_gate_attachments",
            "external_review_audit_entries",
        }
        assert expected.issubset(tables), (
            f"[FAIL] ERG tables missing after re-upgrade.\nMissing: {expected - tables}"
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-006: 0008.down_revision == "0007_task_aggregate"
# ---------------------------------------------------------------------------
class TestDownRevisionChain:
    """TC-IT-ERGR-006: 0008 down_revision points to 0007_task_aggregate."""

    def test_0008_down_revision_is_0007(self) -> None:
        """TC-IT-ERGR-006: Chain is 0007_task_aggregate → 0008_external_review_gate_aggregate."""
        cfg = _alembic_config()
        script_dir = ScriptDirectory.from_config(cfg)
        rev = script_dir.get_revision("0008_external_review_gate_aggregate")
        assert rev is not None, "[FAIL] Revision 0008_external_review_gate_aggregate not found."
        assert rev.down_revision == "0007_task_aggregate", (
            f"[FAIL] 0008.down_revision = {rev.down_revision!r}, expected '0007_task_aggregate'.\n"
            f"Chain 0007→0008 is broken."
        )


# ---------------------------------------------------------------------------
# TC-IT-ERGR-007: Task CASCADE FK deletes Gates (受入基準 7)
# ---------------------------------------------------------------------------
class TestTaskCascadeDeletesGate:
    """TC-IT-ERGR-007: DELETE FROM tasks cascades to external_review_gates."""

    async def test_delete_task_cascades_to_external_review_gates(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-ERGR-007: Deleting a Task row removes its associated Gate rows."""
        await run_upgrade_head(empty_engine)

        empire_id = uuid4().hex
        workflow_id = uuid4().hex
        room_id = uuid4().hex
        directive_id = uuid4().hex
        task_id = uuid4().hex
        gate_id = uuid4().hex
        stage_id = uuid4().hex
        reviewer_id = uuid4().hex
        committed_by = uuid4().hex
        now_str = "2026-01-01T00:00:00+00:00"

        async with empty_engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))

            await conn.execute(
                text("INSERT INTO empires (id, name) VALUES (:id, 'test_empire')"),
                {"id": empire_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO workflows (id, name, entry_stage_id)"
                    " VALUES (:id, 'test_workflow', :sid)"
                ),
                {"id": workflow_id, "sid": stage_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO rooms (id, empire_id, workflow_id, name)"
                    " VALUES (:id, :eid, :wid, 'test_room')"
                ),
                {"id": room_id, "eid": empire_id, "wid": workflow_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO directives (id, text, target_room_id, created_at)"
                    " VALUES (:id, 'テスト指令', :rid, :n)"
                ),
                {"id": directive_id, "rid": room_id, "n": now_str},
            )
            await conn.execute(
                text(
                    "INSERT INTO tasks"
                    " (id, room_id, directive_id, current_stage_id, status,"
                    "  created_at, updated_at)"
                    " VALUES (:id, :rid, :did, :sid, 'PENDING', :n, :n)"
                ),
                {
                    "id": task_id,
                    "rid": room_id,
                    "did": directive_id,
                    "sid": stage_id,
                    "n": now_str,
                },
            )
            await conn.execute(
                text(
                    "INSERT INTO external_review_gates"
                    " (id, task_id, stage_id, reviewer_id, decision, feedback_text,"
                    "  snapshot_stage_id, snapshot_body_markdown, snapshot_committed_by,"
                    "  snapshot_committed_at, created_at, decided_at)"
                    " VALUES (:id, :tid, :sid, :rid, 'PENDING', '',"
                    "  :ssid, 'body', :scby, :n, :n, NULL)"
                ),
                {
                    "id": gate_id,
                    "tid": task_id,
                    "sid": stage_id,
                    "rid": reviewer_id,
                    "ssid": stage_id,
                    "scby": committed_by,
                    "n": now_str,
                },
            )

        # Verify gate exists before delete
        async with empty_engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM external_review_gates WHERE id = :id"),
                    {"id": gate_id},
                )
            ).first()
        assert row[0] == 1, "[FAIL] Gate row not inserted."

        # Delete task — CASCADE should remove gate
        async with empty_engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys = ON"))
            await conn.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task_id})

        # Gate must be gone
        async with empty_engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM external_review_gates WHERE id = :id"),
                    {"id": gate_id},
                )
            ).first()
        assert row[0] == 0, "[FAIL] Gate row still exists after CASCADE DELETE of parent Task."


# ---------------------------------------------------------------------------
# TC-IT-ERGR-008: §設計決定 ERGR-001 — reviewer_id / snapshot_committed_by have NO FK
# ---------------------------------------------------------------------------
class TestAggregrateBoundaryNoForeignKeys:
    """TC-IT-ERGR-008: reviewer_id / snapshot_committed_by have no FK (§設計決定 ERGR-001)."""

    async def test_reviewer_id_has_no_fk(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-ERGR-008: PRAGMA foreign_key_list — no FK to owners/agents for reviewer_id."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('external_review_gates')"))
            fk_list = [dict(row._mapping) for row in result]

        referenced_tables = {fk.get("table") for fk in fk_list}
        # The only FK must be tasks (CASCADE). Owner / Agent Aggregate tables must not appear.
        forbidden = {"owners", "agents", "users", "members"}
        leaked = referenced_tables & forbidden
        assert not leaked, (
            f"[FAIL] §設計決定 ERGR-001 violated: external_review_gates has FK to {leaked}.\n"
            f"reviewer_id / snapshot_committed_by must have NO FK (Aggregate boundary).\n"
            f"All referenced tables: {referenced_tables}"
        )

    async def test_only_tasks_fk_present(
        self,
        empty_engine: AsyncEngine,
    ) -> None:
        """TC-IT-ERGR-008: The only FK from external_review_gates is to tasks."""
        await run_upgrade_head(empty_engine)
        async with empty_engine.connect() as conn:
            result = await conn.execute(text("PRAGMA foreign_key_list('external_review_gates')"))
            fk_list = [dict(row._mapping) for row in result]

        referenced_tables = {fk.get("table") for fk in fk_list}
        assert referenced_tables == {"tasks"}, (
            f"[FAIL] external_review_gates FKs expected: {{tasks}}, got: {referenced_tables}.\n"
            f"§設計決定 ERGR-001: Only task_id carries an FK (ON DELETE CASCADE).\n"
            f"All FK entries: {fk_list}"
        )
