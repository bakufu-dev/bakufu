"""Alembic initial revision integration テスト
(TC-IT-PF-004 / 005 / 015 / 014)。

Confirmation C / Schneier 申し送り #4 — ``audit_log`` 不変性を保護する
SQLite trigger は **実際の** ``DELETE`` / ``UPDATE`` パスに対して
実行されます。将来の revision がこれらを再適用することを忘れた場合、
PR 時にキャッチされるように。
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
    """TC-IT-PF-004: upgrade head 後 3 テーブル + 2 トリガー + インデックス。"""

    async def test_three_tables_present(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-004: audit_log / bakufu_pid_registry / domain_event_outbox が存在。"""
        async with app_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = {row[0] for row in result}
        assert {"audit_log", "bakufu_pid_registry", "domain_event_outbox"}.issubset(tables)

    async def test_two_triggers_present(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-004: audit_log_no_delete + audit_log_update_restricted が存在。"""
        async with app_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='trigger'"))
            triggers = {row[0] for row in result}
        assert {"audit_log_no_delete", "audit_log_update_restricted"}.issubset(triggers)

    async def test_outbox_polling_index_present(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-004: polling SQL 用の ix_outbox_status_next_attempt。"""
        async with app_engine.connect() as conn:
            result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='index'"))
            indices = {row[0] for row in result}
        assert "ix_outbox_status_next_attempt" in indices


class TestAuditLogDeleteForbidden:
    """TC-IT-PF-005: audit_log への DELETE が raise (Schneier #4)。"""

    async def test_delete_raw_sql_aborts(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-005: DELETE FROM audit_log が RAISE(ABORT) をトリガー。"""
        from datetime import UTC, datetime
        from uuid import uuid4

        # 直接行を INSERT (ORM の mask listener 発火、下記の raw INSERT は
        # parameter binding を使用 — dispatcher が使用するのと同じパス)。
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

        # Trigger が DELETE をランタイムエラーに変える。
        with pytest.raises(sa_exc.SQLAlchemyError) as excinfo:
            async with app_engine.begin() as conn:
                await conn.execute(text("DELETE FROM audit_log WHERE id=:id"), {"id": row_id})
        # SQLAlchemy が SQLite エラーを OperationalError でラップ。エラー
        # メッセージは trigger の RAISE メッセージを含む必要がある。
        assert "audit_log is append-only" in str(excinfo.value)


class TestAuditLogUpdateOnceLocked:
    """TC-IT-PF-015: result NOT NULL の audit_log 行への UPDATE は禁止。"""

    async def test_update_after_result_set_is_aborted(self, app_engine: AsyncEngine) -> None:
        """TC-IT-PF-015: result が値を持つと mutate できない。"""
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
        """TC-IT-PF-015 補足: NULL → value 遷移が唯一許可される UPDATE。"""
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
        # 最初の UPDATE — NULL result を定義 — は成功する必要がある。
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
