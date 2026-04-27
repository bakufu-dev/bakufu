"""SessionFactory + UoW boundary integration test (TC-IT-PF-014).

REQ-PF-003 — ``async with session.begin():`` commits on success and
rolls back on exception.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


class TestUnitOfWorkCommit:
    """TC-IT-PF-014: clean exit commits the row."""

    async def test_clean_exit_commits(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-014: row visible after ``async with`` exits cleanly."""
        row_id = uuid4()
        async with session_factory() as session, session.begin():
            session.add(
                AuditLogRow(
                    id=row_id,
                    actor="tester",
                    command="retry-task",
                    args_json={"task_id": str(uuid4())},
                    executed_at=datetime.now(UTC),
                )
            )

        async with session_factory() as session:
            stmt = select(AuditLogRow).where(AuditLogRow.id == row_id)
            result = await session.execute(stmt)
            fetched = result.scalar_one()
        assert fetched.id == row_id


class TestUnitOfWorkRollback:
    """TC-IT-PF-014: exception inside ``begin()`` rolls back."""

    async def test_exception_inside_begin_rolls_back(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-014: row is not persisted when the body raises."""

        class _DeliberateError(Exception):
            pass

        row_id = uuid4()
        with pytest.raises(_DeliberateError):
            async with session_factory() as session, session.begin():
                session.add(
                    AuditLogRow(
                        id=row_id,
                        actor="tester",
                        command="retry-task",
                        args_json={},
                        executed_at=datetime.now(UTC),
                    )
                )
                raise _DeliberateError

        async with session_factory() as session:
            stmt = select(AuditLogRow).where(AuditLogRow.id == row_id)
            result = await session.execute(stmt)
            fetched = result.scalar_one_or_none()
        assert fetched is None
