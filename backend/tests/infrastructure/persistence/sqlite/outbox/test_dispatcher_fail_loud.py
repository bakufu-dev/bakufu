"""Outbox dispatcher Fail Loud WARN tests
(TC-IT-PF-008-A / 008-B / 008-C / 008-D, Confirmation K).

Schneier 中等 3 物理保証 — when the handler registry is empty but
``domain_event_outbox`` rows are accumulating, the dispatcher must
WARN exactly once per condition (no log spam, no silent backlog).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.outbox import handler_registry
from bakufu.infrastructure.persistence.sqlite.outbox.dispatcher import (
    BACKLOG_WARN_THRESHOLD,
    OutboxDispatcher,
)
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow

from tests.factories.persistence_rows import make_outbox_row

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


async def _insert_pending_rows(
    session_factory: async_sessionmaker[AsyncSession],
    count: int,
) -> list[OutboxRow]:
    """Bulk-insert ``count`` PENDING rows for the dispatcher to find."""
    rows: list[OutboxRow] = []
    async with session_factory() as session, session.begin():
        for _ in range(count):
            row = make_outbox_row(
                event_id=uuid4(),
                payload_json={"safe": "ok"},
                status="PENDING",
                next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
            )
            session.add(row)
            rows.append(row)
    return rows


class TestEmptyRegistryWarnOnFirstSeenPending:
    """TC-IT-PF-008-B: pending row + empty registry → WARN once."""

    async def test_warn_emitted_once_for_pending_with_empty_registry(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-B: dispatcher logs WARN when pending count > 0."""
        await _insert_pending_rows(session_factory, count=1)
        dispatcher = OutboxDispatcher(session_factory)

        caplog.clear()
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        warn_messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any(
            "Outbox has 1 pending events but handler_registry is empty" in m for m in warn_messages
        )


class TestEmptyRegistryWarnDoesNotSpam:
    """TC-IT-PF-008-C: subsequent polls of the same backlog do NOT re-WARN."""

    async def test_second_poll_does_not_re_warn(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-C: empty-registry WARN fires once, not on every cycle."""
        await _insert_pending_rows(session_factory, count=1)
        dispatcher = OutboxDispatcher(session_factory)

        # First poll — expect WARN.
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]
        # Second poll — should NOT add another WARN.
        caplog.clear()
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        assert all(
            "handler_registry is empty" not in r.getMessage()
            for r in caplog.records
            if r.levelname == "WARNING"
        )


class TestEmptyRegistryWarnRefiresAfterRegistration:
    """TC-IT-PF-008-A 系: registration + clear restores the WARN trigger."""

    async def test_registering_then_clearing_re_arms_warning(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-A 系: WARN re-fires after a successful registration cycle.

        Reset semantics (Confirmation K): the ``_empty_registry_warned``
        flag only flips back when a poll observes a non-empty registry
        OR an empty pending queue. So the realistic re-arm sequence is:

        1. Poll #1 — pending>0, registry empty → WARN fires.
        2. Register a handler.
        3. Poll #2 — registry>0 → reset flag (no WARN).
        4. Clear the registry.
        5. Poll #3 — pending>0, registry empty again → WARN re-fires.
        """
        await _insert_pending_rows(session_factory, count=1)
        dispatcher = OutboxDispatcher(session_factory)

        # Poll 1: WARN fires.
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        # Register a handler so poll 2 sees a non-empty registry.
        async def _noop(_payload: dict[str, object]) -> None:
            return None

        handler_registry.register("TestKind", _noop)

        # Poll 2: should reset the flag silently (no new WARN).
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        # Drop the handler to mirror a hot-fix mistake.
        handler_registry.clear()

        # Poll 3: empty again, flag was reset → WARN re-fires.
        caplog.clear()
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]
        warn_messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("handler_registry is empty" in m for m in warn_messages)


class TestBacklogWarnThreshold:
    """TC-IT-PF-008-D: pending rows above BACKLOG_WARN_THRESHOLD raises a separate WARN."""

    async def test_backlog_above_threshold_warns(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-D: > 100 PENDING rows triggers backlog WARN."""
        await _insert_pending_rows(session_factory, count=BACKLOG_WARN_THRESHOLD + 1)
        dispatcher = OutboxDispatcher(session_factory)

        caplog.clear()
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        warn_messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any(f"Outbox PENDING count={BACKLOG_WARN_THRESHOLD + 1}" in m for m in warn_messages)
        assert any("bakufu admin list-pending" in m for m in warn_messages)
