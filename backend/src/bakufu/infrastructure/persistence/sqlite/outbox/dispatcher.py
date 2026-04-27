"""Outbox dispatcher (skeleton, §確定 K).

The dispatcher is intentionally **skeleton-only** in this PR per
Schneier 中等 3: handlers ship in subsequent
``feature/{event-kind}-handler`` PRs. What this module *does*
provide is:

* The polling loop structure (1-second tick, batch of 50, 5-minute
  DISPATCHING-recovery, 5-attempt dead-letter cap).
* The Confirmation K Fail Loud warnings — Bootstrap startup
  diagnostic + per-cycle empty-registry WARN + 100-row backlog WARN.
* A clean ``stop()`` path so Bootstrap LIFO cleanup can cancel the
  background task.

The actual SELECT / UPDATE SQL lands when handlers exist; here we keep
the surface minimal so subsequent PRs only need to fill in the body
of :meth:`_dispatch_one`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bakufu.infrastructure.persistence.sqlite.outbox import handler_registry
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow

logger = logging.getLogger(__name__)

# Confirmation K — see ``outbox.md``.
DEFAULT_BATCH_SIZE: Final = 50
DEFAULT_POLL_INTERVAL_SECONDS: Final = 1.0
DEFAULT_DISPATCHING_RECOVERY_MINUTES: Final = 5
DEFAULT_MAX_ATTEMPTS: Final = 5
BACKLOG_WARN_THRESHOLD: Final = 100


class OutboxDispatcher:
    """Background dispatcher for ``domain_event_outbox`` rows.

    Bootstrap stage 6 instantiates one of these and schedules
    :meth:`run` as an asyncio task. Bootstrap LIFO cleanup
    (Confirmation J) calls :meth:`stop` to break the loop on shutdown.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        dispatching_recovery_minutes: int = (
            DEFAULT_DISPATCHING_RECOVERY_MINUTES
        ),
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._session_factory = session_factory
        self._batch_size = batch_size
        self._poll_interval = poll_interval_seconds
        self._dispatching_recovery_minutes = dispatching_recovery_minutes
        self._max_attempts = max_attempts
        self._stop_event = asyncio.Event()
        # Track whether we have already warned about an empty handler
        # registry encountering pending rows; avoid spamming the log on
        # every poll cycle (Confirmation K row 2).
        self._empty_registry_warned: bool = False
        # Backlog WARN throttling: emit at most once every 5 minutes.
        self._backlog_last_warn_monotonic: float = 0.0

    async def run(self) -> None:
        """Polling loop. Call from ``asyncio.create_task`` in Bootstrap.

        The loop is intentionally simple — no row processing yet
        because no handlers are registered. Each tick still runs the
        empty-registry / backlog Fail Loud checks so operators see
        the same telemetry once handlers land.
        """
        while not self._stop_event.is_set():
            try:
                await self._poll_once()
            except Exception:  # pragma: no cover — defensive
                # The dispatcher must never die in the body of a poll.
                # Log and continue; the next cycle retries.
                logger.exception(
                    "[ERROR] Outbox dispatcher poll cycle raised; "
                    "continuing to next cycle"
                )
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval,
                )
            except TimeoutError:
                continue

    async def stop(self) -> None:
        """Signal the polling loop to exit at the next iteration."""
        self._stop_event.set()

    async def _poll_once(self) -> None:
        """Single polling cycle: count pending rows + emit WARNs.

        Subsequent PRs extend this to actually process the batch via
        :meth:`_dispatch_one`. This skeleton just exposes the count
        so Confirmation K's startup / per-cycle / backlog warnings
        fire on real data.
        """
        async with self._session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.status == "PENDING")
            result = await session.execute(stmt)
            pending = result.scalars().all()

        pending_count = len(pending)
        registry_size = handler_registry.size()

        # Confirmation K row 2: empty registry + pending rows.
        if pending_count > 0 and registry_size == 0:
            if not self._empty_registry_warned:
                logger.warning(
                    "[WARN] Outbox has %d pending events but "
                    "handler_registry is empty.",
                    pending_count,
                )
                self._empty_registry_warned = True
        else:
            # Once a handler appears or the queue clears, allow the
            # WARN to re-fire if the situation regresses.
            self._empty_registry_warned = False

        # Confirmation K row 3: backlog threshold (>100 rows).
        if pending_count > BACKLOG_WARN_THRESHOLD:
            now = asyncio.get_running_loop().time()
            five_minutes_seconds = 300.0
            if now - self._backlog_last_warn_monotonic > five_minutes_seconds:
                logger.warning(
                    "[WARN] Outbox PENDING count=%d > %d. Inspect with "
                    "bakufu admin list-pending.",
                    pending_count,
                    BACKLOG_WARN_THRESHOLD,
                )
                self._backlog_last_warn_monotonic = now


__all__ = [
    "BACKLOG_WARN_THRESHOLD",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_DISPATCHING_RECOVERY_MINUTES",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "OutboxDispatcher",
]
