"""Bootstrap stage 4 orphan-process garbage collection (§確定 E).

The previous run of bakufu may have left subprocess (claude / codex /
etc.) trees alive — a crash, a SIGKILL of the parent, an exotic OS
state. This module sweeps :class:`PidRegistryRow` entries on startup,
classifies each, and either DELETEs the row alone (the PID is gone or
has been recycled by an unrelated process) or kills the descendants
and DELETEs the row.

Classification logic
--------------------
Each row carries the snapshot ``started_at`` from the original
``psutil.Process.create_time()``. That timestamp is the **PID-collision
guard**: if a different process happened to land on the same PID, its
``create_time()`` will not match and we must not kill it.

| psutil result                         | classification | action                       |
|---------------------------------------|----------------|------------------------------|
| ``NoSuchProcess``                     | ``absent``     | DELETE the row only          |
| Process exists, ``create_time`` match | ``orphan_kill``| Kill descendants + DELETE    |
| Process exists, ``create_time`` mismatch | ``protected``  | DELETE the row only (PID reused) |
| ``AccessDenied``                       | (no class.)    | WARN, leave row for next GC  |
"""

from __future__ import annotations

import logging
import signal
import time
from datetime import datetime
from typing import Literal

import psutil
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bakufu.infrastructure.persistence.sqlite.tables.pid_registry import (
    PidRegistryRow,
)

logger = logging.getLogger(__name__)

# Confirmation E: SIGTERM grace before SIGKILL.
SIGTERM_GRACE_SECONDS: int = 5

PidClassification = Literal["orphan_kill", "protected", "absent"]


async def run_startup_gc(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """Sweep ``bakufu_pid_registry`` and reconcile against the OS.

    Args:
        session_factory: AsyncSession factory used to read / DELETE
            registry rows.

    Returns:
        Counts dict with keys ``killed`` / ``protected`` / ``absent`` /
        ``access_denied`` so Bootstrap can include them in the stage-4
        completion log line.
    """
    counts = {"killed": 0, "protected": 0, "absent": 0, "access_denied": 0}

    async with session_factory() as session:
        rows = (await session.execute(select(PidRegistryRow))).scalars().all()

    for row in rows:
        try:
            classification = _classify_row(row.pid, row.started_at)
        except psutil.AccessDenied:
            logger.warning(
                "[WARN] pid_registry GC: psutil.AccessDenied for "
                "pid=%d, retry next cycle",
                row.pid,
            )
            counts["access_denied"] += 1
            continue

        if classification == "orphan_kill":
            _kill_descendants(row.pid)
            counts["killed"] += 1
        elif classification == "protected":
            counts["protected"] += 1
        else:  # "absent"
            counts["absent"] += 1

        async with session_factory() as session, session.begin():
            await session.execute(
                delete(PidRegistryRow).where(PidRegistryRow.pid == row.pid),
            )

    return counts


def _classify_row(pid: int, recorded_started_at: datetime) -> PidClassification:
    """Compare the recorded ``started_at`` with the live process.

    Raises:
        psutil.AccessDenied: surfaces upward so the caller can WARN-log
            the row and skip DELETE (next GC retries).
    """
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return "absent"

    try:
        live_create_time = proc.create_time()
    except psutil.NoSuchProcess:
        return "absent"
    except psutil.AccessDenied:
        raise

    # ``psutil.Process.create_time`` returns POSIX seconds; we stored a
    # tz-aware datetime. Compare with millisecond tolerance to absorb
    # rounding noise across psutil versions.
    recorded_seconds = recorded_started_at.timestamp()
    if abs(live_create_time - recorded_seconds) > 0.001:
        return "protected"
    return "orphan_kill"


def _kill_descendants(pid: int) -> None:
    """SIGTERM all descendants → 5-second grace → SIGKILL stragglers.

    Uses ``psutil.Process.children(recursive=True)`` so the entire
    subtree (claude → codex → grandchildren) is reaped, not just the
    direct child.
    """
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    try:
        descendants = proc.children(recursive=True)
    except psutil.NoSuchProcess:
        return

    targets = [proc, *descendants]

    for target in targets:
        try:
            target.send_signal(signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            logger.warning(
                "[WARN] pid_registry GC: SIGTERM failed for pid=%s: %r",
                getattr(target, "pid", "?"),
                exc,
            )

    deadline = time.monotonic() + SIGTERM_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not any(t.is_running() for t in targets):
            return
        time.sleep(0.1)

    for target in targets:
        if not target.is_running():
            continue
        try:
            target.send_signal(signal.SIGKILL)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:  # pragma: no cover
            logger.warning(
                "[WARN] pid_registry GC: SIGKILL failed for pid=%s: %r",
                getattr(target, "pid", "?"),
                exc,
            )


__all__ = [
    "SIGTERM_GRACE_SECONDS",
    "PidClassification",
    "run_startup_gc",
]
