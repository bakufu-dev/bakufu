"""Masking listener integration tests
(TC-IT-PF-007 / 020 / 021 / 022).

The **core** of Schneier 申し送り #6 + Confirmation R1-D — the masking
listener must fire even when callers bypass the ORM mapper and use a
raw ``insert(table).values(...)`` statement. This is what justifies
choosing ``before_insert`` / ``before_update`` event listeners over a
``TypeDecorator``: the listener catches the *table* operation, not the
ORM type binding, so a future Repository that goes raw-SQL still gets
masked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest
from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow
from bakufu.infrastructure.persistence.sqlite.tables.pid_registry import (
    PidRegistryRow,
)
from sqlalchemy import insert, select

from tests.factories.persistence_rows import (
    make_audit_log_row,
    make_outbox_row,
    make_pid_registry_row,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio

# Real-shape secrets. Each must end up redacted before SELECT.
ANTHROPIC_KEY = "sk-ant-api03-" + "A" * 60
GITHUB_PAT = "ghp_" + "X" * 40
AWS_KEY = "AKIA1234567890ABCDEF"
SLACK_TOKEN = "xoxb-1234567890-token-data"
BEARER_PHRASE = "Authorization: Bearer eyJ.tokenpart.signature"


def _outbox_columns(row: OutboxRow) -> dict[str, object]:
    """Project an OutboxRow factory output to a dict of column→value."""
    return {
        "event_id": row.event_id,
        "event_kind": row.event_kind,
        "aggregate_id": row.aggregate_id,
        "payload_json": row.payload_json,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "next_attempt_at": row.next_attempt_at,
        "last_error": row.last_error,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "dispatched_at": row.dispatched_at,
    }


class TestOutboxMaskingViaOrm:
    """TC-IT-PF-007: ORM-path INSERT redacts payload_json + last_error."""

    async def test_payload_json_redacted_after_insert(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-007: Anthropic + GitHub PAT in payload_json get redacted."""
        row = make_outbox_row(
            payload_json={"key": ANTHROPIC_KEY, "github_pat": GITHUB_PAT},
            last_error=AWS_KEY,
        )
        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(stmt)).scalar_one()

        payload = cast("dict[str, object]", fetched.payload_json)
        assert "<REDACTED:ANTHROPIC_KEY>" in str(payload["key"])
        assert "<REDACTED:GITHUB_PAT>" in str(payload["github_pat"])
        assert fetched.last_error is not None
        assert "<REDACTED:AWS_ACCESS_KEY>" in fetched.last_error


class TestOutboxMaskingViaRawSql:
    """TC-IT-PF-020: raw ``insert(table).values(...)`` still triggers the listener.

    This is **the** test that justifies the event-listener approach
    over TypeDecorator (Confirmation R1-D). A future Repository PR that
    bypasses the ORM mapper for performance must not bypass masking.

    **Bug discovered while implementing this test (BUG-PF-001)**:
    ``event.listen(OutboxRow, 'before_insert', ...)`` is a *mapper-level*
    event that fires on ORM ``Session.flush()`` only. It does NOT fire
    for Core ``session.execute(insert(table).values(...))`` — those go
    through SQLAlchemy's Core path which has separate ``before_execute``
    / ``do_orm_execute`` events. Confirmation R1-D's "raw SQL path is
    masked too" claim is **factually false** with the current wiring.

    The xfail tag below preserves the *design contract* assertion so
    CI can detect the day the bug is fixed (``strict=True`` → fix
    without removing the marker fails CI). The bug report is appended
    to the test execution summary.
    """

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "BUG-PF-001: ORM-level before_insert listener does not fire for "
            "Core insert(table).values(...) path. Schneier #6 / Confirmation "
            "R1-D claim broken. Remove this xfail once Linus rewires masking "
            "via Engine-level do_execute / before_execute events."
        ),
    )
    async def test_raw_sql_path_redacts_payload(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-020: raw insert path equally redacts payload_json + last_error."""
        row = make_outbox_row(
            payload_json={"key": ANTHROPIC_KEY},
            last_error=GITHUB_PAT,
        )
        async with session_factory() as session, session.begin():
            stmt = insert(OutboxRow).values(**_outbox_columns(row))
            await session.execute(stmt)

        async with session_factory() as session:
            sel = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(sel)).scalar_one()

        payload = cast("dict[str, object]", fetched.payload_json)
        assert "<REDACTED:ANTHROPIC_KEY>" in str(payload["key"])
        assert fetched.last_error is not None
        assert "<REDACTED:GITHUB_PAT>" in fetched.last_error


class TestOutboxMaskingOnUpdate:
    """TC-IT-PF-021: ``before_update`` redacts updates as well as inserts."""

    async def test_update_path_redacts_last_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-021: re-marking a row as DEAD_LETTER with raw secrets in last_error."""
        row = make_outbox_row(payload_json={"safe": "value"}, last_error=None)
        async with session_factory() as session, session.begin():
            session.add(row)

        # Now load + update with new secret-bearing data.
        async with session_factory() as session, session.begin():
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            target = (await session.execute(stmt)).scalar_one()
            target.status = "DEAD_LETTER"
            target.last_error = AWS_KEY
            target.updated_at = datetime.now(UTC)

        async with session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(stmt)).scalar_one()
        assert fetched.last_error is not None
        assert "<REDACTED:AWS_ACCESS_KEY>" in fetched.last_error


class TestAuditLogAndPidRegistryMaskingHook:
    """TC-IT-PF-022: hook is wired across the other 2 secret-bearing tables."""

    async def test_audit_log_redacts_args_and_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-022 (audit_log): args_json + error_text masked."""
        row = make_audit_log_row(
            args_json={"token": SLACK_TOKEN},
            error_text=BEARER_PHRASE,
        )
        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(AuditLogRow).where(AuditLogRow.id == row.id)
            fetched = (await session.execute(stmt)).scalar_one()
        args = cast("dict[str, object]", fetched.args_json)
        assert "<REDACTED:SLACK_TOKEN>" in str(args["token"])
        assert fetched.error_text is not None
        assert "<REDACTED:BEARER>" in fetched.error_text

    async def test_pid_registry_redacts_cmd(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-022 (pid_registry): cmd column masked."""
        row = make_pid_registry_row(cmd=f"claude --api-key={ANTHROPIC_KEY} --task xyz")
        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(PidRegistryRow).where(PidRegistryRow.pid == row.pid)
            fetched = (await session.execute(stmt)).scalar_one()
        assert "<REDACTED:ANTHROPIC_KEY>" in fetched.cmd
        # The plaintext ``ANTHROPIC_KEY`` must not survive.
        assert ANTHROPIC_KEY not in fetched.cmd
