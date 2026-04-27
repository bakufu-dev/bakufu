"""Alembic initial revision integration tests
(TC-IT-PF-004 / 005 / 015 / 014).

Confirmation C / Schneier 申し送り #4 — the SQLite triggers protecting
``audit_log`` immutability are exercised against the **real**
``DELETE`` / ``UPDATE`` paths so a future revision that forgets to
re-apply them is caught at PR time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import exc as sa_exc
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.asyncio


class TestSchemaCreatedByAlembic:
    """TC-IT-PF-004: 3 tables + 2 triggers + index after upgrade head."""

    async def test_three_tables_present(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-004: audit_log / bakufu_pid_registry / domain_event_outbox exist."""
        async with app_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"audit_log", "bakufu_pid_registry", "domain_event_outbox"}.issubset(tables)

    async def test_two_triggers_present(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-004: audit_log_no_delete + audit_log_update_restricted exist."""
        async with app_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='trigger'"))
            triggers = {row[0] for row in result}
        assert {"audit_log_no_delete", "audit_log_update_restricted"}.issubset(triggers)

    async def test_outbox_polling_index_present(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-004: ix_outbox_status_next_attempt for polling SQL."""
        async with app_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='index'"))
            indices = {row[0] for row in result}
        assert "ix_outbox_status_next_attempt" in indices


class TestAuditLogDeleteForbidden:
    """TC-IT-PF-005: DELETE on audit_log raises (Schneier #4)."""

    async def test_delete_raw_sql_aborts(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-005: DELETE FROM audit_log triggers RAISE(ABORT)."""
        from datetime import UTC, datetime
        from uuid import uuid4

        # Insert a row directly (mask listener fires for ORM, raw INSERT
        # below uses parameter binding — same path the dispatcher would
        # use).
        row_id = uuid4().hex
        async with app_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO audit_log (id, actor, command, args_json, executed_at) "
                    "VALUES (:id, :actor, :cmd, :args, :ts)"
                ),
                {
                    "id": row_id,
                    "actor": "tester@host",
                    "cmd": "list-pending",
                    "args": '{"k": "v"}',
                    "ts": datetime.now(UTC).isoformat(),
                },
            )

        # The trigger turns DELETE into a runtime error.
        with pytest.raises(sa_exc.SQLAlchemyError) as excinfo:
            async with app_engine.begin() as conn:
                await conn.execute(text("DELETE FROM audit_log WHERE id=:id"), {"id": row_id})
        # SQLAlchemy wraps SQLite errors in OperationalError. The error
        # message must carry the trigger's RAISE message.
        assert "audit_log is append-only" in str(excinfo.value)


class TestAuditLogUpdateOnceLocked:
    """TC-IT-PF-015: UPDATE on audit_log row with result NOT NULL is forbidden."""

    async def test_update_after_result_set_is_aborted(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-015: cannot mutate result once it has a value."""
        from datetime import UTC, datetime
        from uuid import uuid4

        row_id = uuid4().hex
        async with app_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO audit_log (id, actor, command, args_json, result, executed_at) "
                    "VALUES (:id, :actor, :cmd, :args, :result, :ts)"
                ),
                {
                    "id": row_id,
                    "actor": "tester@host",
                    "cmd": "retry-task",
                    "args": "{}",
                    "result": "SUCCESS",
                    "ts": datetime.now(UTC).isoformat(),
                },
            )

        with pytest.raises(sa_exc.SQLAlchemyError) as excinfo:
            async with app_engine.begin() as conn:
                await conn.execute(
                    text("UPDATE audit_log SET result='FAILURE' WHERE id=:id"),
                    {"id": row_id},
                )
        assert "audit_log result is immutable once set" in str(excinfo.value)

    async def test_update_with_null_result_is_allowed(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-015 supplemental: NULL → value transition is the *one* allowed UPDATE."""
        from datetime import UTC, datetime
        from uuid import uuid4

        row_id = uuid4().hex
        async with app_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO audit_log (id, actor, command, args_json, executed_at) "
                    "VALUES (:id, :actor, :cmd, :args, :ts)"
                ),
                {
                    "id": row_id,
                    "actor": "tester@host",
                    "cmd": "retry-task",
                    "args": "{}",
                    "ts": datetime.now(UTC).isoformat(),
                },
            )
        # First UPDATE — populating NULL result — must succeed.
        async with app_engine.begin() as conn:
            await conn.execute(
                text("UPDATE audit_log SET result='SUCCESS' WHERE id=:id"),
                {"id": row_id},
            )
        async with app_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT result FROM audit_log WHERE id=:id"),
                {"id": row_id},
            )
            row = result.scalar()
        assert row == "SUCCESS"
