"""Backend startup sequencer (Confirmation E + G + J + K + L).

Owns the eight-stage cold-start choreography described in
``docs/features/persistence-foundation/detailed-design/bootstrap.md``.
Splitting it into one class lets us:

* Read the order top-to-bottom in :meth:`Bootstrap.run` (Confirmation G).
* Bind the LIFO cleanup contract to ``try/finally`` in one place
  (Confirmation J — Schneier 中等 4).
* Set ``os.umask(0o077)`` *before* SQLite ever opens a WAL/SHM file
  (Confirmation L — Schneier 中等 1).
* Surface the empty-handler-registry WARN at the end of stage 6
  (Confirmation K — Schneier 中等 3).
* Centralize the FATAL log + ``exit(1)`` flow so every stage failure
  produces the same shape of telemetry.

The actual FastAPI bind (stage 8) is supplied via the
``listener_starter`` callable so this PR can ship without dragging in
the ``feature/http-api`` HTTP surface — tests pass ``None`` to skip
stage 8 entirely.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from bakufu.infrastructure.config import data_dir
from bakufu.infrastructure.exceptions import (
    BakufuConfigError,
    BakufuMigrationError,
)
from bakufu.infrastructure.persistence.sqlite import engine as engine_mod
from bakufu.infrastructure.persistence.sqlite import pid_gc
from bakufu.infrastructure.persistence.sqlite import session as session_mod
from bakufu.infrastructure.persistence.sqlite.outbox import (
    dispatcher as dispatcher_mod,
)
from bakufu.infrastructure.persistence.sqlite.outbox import (
    handler_registry,
)
from bakufu.infrastructure.security import masking
from bakufu.infrastructure.storage import attachment_root

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Confirmation L: secure-by-default file mode (POSIX only).
SECURE_UMASK: int = 0o077

# Type alias for the optional stage-8 callable.
ListenerStarter = Callable[[], Awaitable[None]]


class Bootstrap:
    """Eight-stage startup orchestrator.

    Tests construct one with ``listener_starter=None`` and call
    :meth:`run` to verify the full sequence sans HTTP bind.
    Production wires the FastAPI binder in.
    """

    def __init__(
        self,
        *,
        listener_starter: ListenerStarter | None = None,
        migration_runner: Callable[[AsyncEngine], Awaitable[str]] | None = None,
    ) -> None:
        self._listener_starter = listener_starter
        # Migration is decoupled so tests can inject a stub instead of
        # spinning up Alembic. Production passes the Alembic-driven
        # implementation from ``infrastructure.persistence.sqlite.migrations``.
        self._migration_runner = migration_runner

        # State populated as stages succeed; LIFO cleanup walks them in
        # reverse on failure.
        self._app_engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._dispatcher: dispatcher_mod.OutboxDispatcher | None = None
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._attachments_task: asyncio.Task[None] | None = None
        self._data_dir: Path | None = None

    @property
    def app_engine(self) -> AsyncEngine | None:
        """Application engine (``None`` until stage 2 succeeds)."""
        return self._app_engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession] | None:
        """Session factory (``None`` until stage 2 succeeds)."""
        return self._session_factory

    async def run(self) -> None:
        """Execute stages 0〜8. ``finally`` block runs LIFO cleanup.

        Raises:
            BakufuConfigError: any fatal stage failure (1/2/3/5/6/7/8).
                Stage 4 (pid_gc) only emits WARNs; ``AccessDenied``
                rows are left for the next sweep.
        """
        try:
            self._stage_0_umask()
            self._stage_1_resolve_data_dir()
            await self._stage_2_init_engine()
            await self._stage_3_migrate()
            await self._stage_4_pid_gc()
            self._stage_5_attachments()
            await self._stage_6_dispatcher()
            self._stage_7_orphan_scheduler()
            await self._stage_8_listener()
        finally:
            await self._cleanup()

    # ------------------------------------------------------------------
    # Stage 0: secure-by-default umask (Confirmation L).
    # ------------------------------------------------------------------
    def _stage_0_umask(self) -> None:
        """Set ``umask`` so SQLite-created files inherit ``0o600``.

        POSIX only — Windows uses ACLs and ``os.umask`` is a no-op.
        Failure to set a more-restrictive umask isn't fatal; the OS
        default is still ``0o022`` and our explicit ``chmod`` calls in
        stages 5 / Alembic compensate.
        """
        if platform.system() == "Windows":
            return
        try:
            os.umask(SECURE_UMASK)
            logger.info(
                "[INFO] Bootstrap stage 0/8: umask set to 0o%03o",
                SECURE_UMASK,
            )
        except OSError as exc:  # pragma: no cover — extreme OS state
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=f"[FAIL] Bootstrap stage 0/8: umask SET failed: {exc!r}",
            ) from exc

    # ------------------------------------------------------------------
    # Stage 1: resolve BAKUFU_DATA_DIR.
    # ------------------------------------------------------------------
    def _stage_1_resolve_data_dir(self) -> None:
        logger.info("[INFO] Bootstrap stage 1/8: resolving BAKUFU_DATA_DIR...")
        try:
            self._data_dir = data_dir.resolve()
        except BakufuConfigError as exc:
            logger.error("[FAIL] Bootstrap stage 1/8: %s", exc.message)
            raise
        # Materialize the directory itself so subsequent stages can
        # write into it without races. ``exist_ok=True`` keeps idempotent
        # restarts cheap.
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BakufuConfigError(
                msg_id="MSG-PF-001",
                message=(
                    f"[FAIL] Bootstrap stage 1/8: cannot create data_dir at "
                    f"{self._data_dir}: {exc!r}"
                ),
            ) from exc
        logger.info(
            "[INFO] Bootstrap stage 1/8: data dir resolved at %s",
            self._data_dir,
        )

    # ------------------------------------------------------------------
    # Stage 2: SQLite engine + masking gateway init.
    # ------------------------------------------------------------------
    async def _stage_2_init_engine(self) -> None:
        logger.info("[INFO] Bootstrap stage 2/8: initializing SQLite engine...")
        if self._data_dir is None:  # pragma: no cover — stage ordering
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=(
                    "[FAIL] Bootstrap stage 2/8: data_dir not resolved "
                    "(stage 1 must run first)"
                ),
            )
        # Initialize the masking gateway *before* the engine because
        # tables register listeners at import time and the listeners
        # call ``mask`` immediately.
        try:
            masking.init()
        except BakufuConfigError:
            # Bubble the MSG-PF-008 case unchanged; Bootstrap exit is
            # the contract for a Fail-Fast masking init failure.
            raise
        url = f"sqlite+aiosqlite:///{self._data_dir / 'bakufu.db'}"
        try:
            self._app_engine = engine_mod.create_engine(url)
            self._session_factory = session_mod.make_session_factory(self._app_engine)
        except Exception as exc:
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=(
                    f"[FAIL] Bootstrap stage 2/8: SQLite engine "
                    f"initialization failed: {exc!r}"
                ),
            ) from exc
        logger.info(
            "[INFO] Bootstrap stage 2/8: engine ready (PRAGMA WAL/foreign_keys/"
            "busy_timeout/synchronous/temp_store/defensive applied)"
        )

    # ------------------------------------------------------------------
    # Stage 3: Alembic upgrade via migration engine (Confirmation D-3).
    # ------------------------------------------------------------------
    async def _stage_3_migrate(self) -> None:
        logger.info("[INFO] Bootstrap stage 3/8: applying Alembic migrations...")
        if self._app_engine is None:  # pragma: no cover — stage ordering
            raise BakufuMigrationError(
                msg_id="MSG-PF-004",
                message="[FAIL] Bootstrap stage 3/8: app_engine not initialized",
            )
        if self._migration_runner is None:
            # Tests / minimal startups pass no runner; skip with a
            # WARN so production wiring failures are obvious.
            logger.warning(
                "[WARN] Bootstrap stage 3/8: no migration_runner injected; "
                "skipping Alembic upgrade (test-mode or minimal startup)."
            )
            return
        try:
            head = await self._migration_runner(self._app_engine)
        except Exception as exc:
            raise BakufuMigrationError(
                msg_id="MSG-PF-004",
                message=f"[FAIL] Alembic migration failed: {exc!r}",
            ) from exc
        logger.info(
            "[INFO] Bootstrap stage 3/8: schema at head %s", head
        )

    # ------------------------------------------------------------------
    # Stage 4: pid_registry orphan GC (non-fatal).
    # ------------------------------------------------------------------
    async def _stage_4_pid_gc(self) -> None:
        logger.info("[INFO] Bootstrap stage 4/8: pid_registry orphan GC...")
        if self._session_factory is None:  # pragma: no cover — stage ordering
            return
        try:
            counts = await pid_gc.run_startup_gc(self._session_factory)
            logger.info(
                "[INFO] Bootstrap stage 4/8: GC complete "
                "(killed=%d, protected=%d, absent=%d, access_denied=%d)",
                counts["killed"],
                counts["protected"],
                counts["absent"],
                counts["access_denied"],
            )
        except Exception as exc:
            # Confirmation E + G: stage 4 is non-fatal. The unaffected
            # rows survive to the next GC and the Backend continues.
            logger.warning(
                "[WARN] Bootstrap stage 4/8: pid_registry GC raised "
                "(%r); continuing startup",
                exc,
            )

    # ------------------------------------------------------------------
    # Stage 5: attachments FS root (Confirmation E).
    # ------------------------------------------------------------------
    def _stage_5_attachments(self) -> None:
        logger.info("[INFO] Bootstrap stage 5/8: ensuring attachment FS root...")
        if self._data_dir is None:  # pragma: no cover — stage ordering
            raise BakufuConfigError(
                msg_id="MSG-PF-003",
                message="[FAIL] Bootstrap stage 5/8: data_dir not resolved",
            )
        root = attachment_root.ensure_root(self._data_dir)
        logger.info(
            "[INFO] Bootstrap stage 5/8: attachments root at %s "
            "(mode=0o%03o)",
            root,
            attachment_root.ATTACHMENTS_MODE,
        )

    # ------------------------------------------------------------------
    # Stage 6: Outbox dispatcher (Confirmation K Fail Loud).
    # ------------------------------------------------------------------
    async def _stage_6_dispatcher(self) -> None:
        logger.info(
            "[INFO] Bootstrap stage 6/8: starting Outbox Dispatcher "
            "(poll_interval=%ss, batch=%d)...",
            dispatcher_mod.DEFAULT_POLL_INTERVAL_SECONDS,
            dispatcher_mod.DEFAULT_BATCH_SIZE,
        )
        if self._session_factory is None:  # pragma: no cover — stage ordering
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message="[FAIL] Bootstrap stage 6/8: session_factory not ready",
            )
        self._dispatcher = dispatcher_mod.OutboxDispatcher(self._session_factory)
        self._dispatcher_task = asyncio.create_task(self._dispatcher.run())
        size = handler_registry.size()
        logger.info(
            "[INFO] Bootstrap stage 6/8: dispatcher running "
            "(handler_registry size=%d)",
            size,
        )
        # Confirmation K row 1: empty registry WARN at startup.
        if size == 0:
            logger.warning(
                "[WARN] Bootstrap stage 6/8: No event handlers registered. "
                "Outbox events will accumulate without dispatch. Register "
                "handlers via feature/{event-kind}-handler PRs before "
                "processing real events."
            )

    # ------------------------------------------------------------------
    # Stage 7: attachments orphan GC scheduler.
    # ------------------------------------------------------------------
    def _stage_7_orphan_scheduler(self) -> None:
        logger.info(
            "[INFO] Bootstrap stage 7/8: starting attachment orphan GC "
            "scheduler (interval=24h)..."
        )
        self._attachments_task = attachment_root.start_orphan_gc_scheduler()
        logger.info("[INFO] Bootstrap stage 7/8: scheduler running")

    # ------------------------------------------------------------------
    # Stage 8: FastAPI / WebSocket bind (delegated).
    # ------------------------------------------------------------------
    async def _stage_8_listener(self) -> None:
        if self._listener_starter is None:
            logger.info(
                "[INFO] Bootstrap stage 8/8: no listener_starter injected; "
                "skipping HTTP bind (skeleton mode)."
            )
            return
        logger.info(
            "[INFO] Bootstrap stage 8/8: binding FastAPI listener "
            "(delegated)..."
        )
        try:
            await self._listener_starter()
        except Exception as exc:
            raise BakufuConfigError(
                msg_id="MSG-PF-002",
                message=f"[FAIL] Bootstrap stage 8/8: listener bind failed: {exc!r}",
            ) from exc
        logger.info("[INFO] Bootstrap stage 8/8: bakufu Backend ready")

    # ------------------------------------------------------------------
    # LIFO cleanup (Confirmation J).
    # ------------------------------------------------------------------
    async def _cleanup(self) -> None:
        """Cancel async tasks in reverse start order, then dispose engine.

        Order (from Confirmation J):

        1. Cancel the attachments orphan-GC scheduler (stage 7).
        2. Stop and cancel the Outbox dispatcher (stage 6).
        3. Dispose the application engine (stage 2).
        4. Flush log handlers.
        """
        # Stage 7 cleanup — gather() with return_exceptions so a single
        # CancelledError doesn't mask issues in stage 6 cleanup.
        if self._attachments_task is not None:
            self._attachments_task.cancel()
            await asyncio.gather(self._attachments_task, return_exceptions=True)

        if self._dispatcher is not None:
            await self._dispatcher.stop()
        if self._dispatcher_task is not None:
            self._dispatcher_task.cancel()
            await asyncio.gather(self._dispatcher_task, return_exceptions=True)

        if self._app_engine is not None:
            await self._app_engine.dispose()

        for handler in logger.handlers:
            with contextlib.suppress(Exception):  # pragma: no cover — defensive
                handler.flush()


__all__ = [
    "SECURE_UMASK",
    "Bootstrap",
    "ListenerStarter",
]
