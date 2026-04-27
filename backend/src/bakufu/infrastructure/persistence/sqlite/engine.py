"""SQLite ``AsyncEngine`` factory with PRAGMA enforcement (§確定 D).

Two engine flavors per Confirmation D-2 (Schneier 重大 2):

* :func:`create_engine` — **application** engine. Used by everything
  except Alembic. Sets eight PRAGMAs, including ``defensive=ON`` and
  ``writable_schema=OFF`` so the ``audit_log`` triggers cannot be
  ``DROP``-ed at runtime.
* :func:`create_migration_engine` — **migration** engine. Used only
  inside Bootstrap stage 3, then ``dispose()``-ed. Relaxes
  ``defensive`` / ``writable_schema`` so Alembic can issue DDL.

The PRAGMA list is set per-connection via a ``connect`` event listener
on the underlying sync engine — that is where SQLAlchemy / aiosqlite
hand us a DBAPI connection before any ORM activity.
"""

from __future__ import annotations

import logging
from typing import Final

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

# Confirmation D-1: eight PRAGMAs for the application connection.
# Order matters — `journal_mode=WAL` first, defensive guards last so
# they activate against everything that follows.
_APP_PRAGMAS: Final[tuple[tuple[str, str], ...]] = (
    ("journal_mode", "WAL"),
    ("foreign_keys", "ON"),
    ("busy_timeout", "5000"),
    ("synchronous", "NORMAL"),
    ("temp_store", "MEMORY"),
    ("defensive", "ON"),
    ("writable_schema", "OFF"),
    ("trusted_schema", "OFF"),
)

# Confirmation D-2: migration engine relaxes the defensive guards so
# Alembic can issue CREATE TABLE / CREATE TRIGGER. The other PRAGMAs
# stay identical — concurrency / FK / busy_timeout still matter even
# during migrations.
_MIGRATION_PRAGMAS: Final[tuple[tuple[str, str], ...]] = (
    ("journal_mode", "WAL"),
    ("foreign_keys", "ON"),
    ("busy_timeout", "5000"),
    ("synchronous", "NORMAL"),
    ("temp_store", "MEMORY"),
    ("defensive", "OFF"),
    ("writable_schema", "ON"),
)


def create_engine(url: str, *, debug: bool = False) -> AsyncEngine:
    """Build the application-level :class:`AsyncEngine`.

    Args:
        url: SQLAlchemy URL (e.g. ``sqlite+aiosqlite:///<path>``).
        debug: Forwarded to ``create_async_engine(echo=...)`` for
            verbose SQL logging during development.
    """
    engine = create_async_engine(url, echo=debug, future=True)
    event.listen(engine.sync_engine, "connect", _set_app_pragmas)
    return engine


def create_migration_engine(url: str) -> AsyncEngine:
    """Build the migration-only :class:`AsyncEngine` (Confirmation D-2).

    Use only from Bootstrap stage 3 (Alembic ``upgrade head``) and
    ``dispose()`` immediately after; never share with application code.
    """
    engine = create_async_engine(url, echo=False, future=True)
    event.listen(engine.sync_engine, "connect", _set_migration_pragmas)
    return engine


def _apply_pragmas(
    dbapi_conn: object,
    pragmas: tuple[tuple[str, str], ...],
) -> None:
    """Apply ``PRAGMA name=value;`` for each pair.

    Some PRAGMAs (``defensive`` / ``writable_schema`` / ``trusted_schema``)
    only exist on SQLite 3.31+; on older builds the ``execute`` raises
    and we log the skip. The other PRAGMAs are mandatory — failures
    propagate so Bootstrap can convert them to MSG-PF-002.
    """
    cursor_factory = getattr(dbapi_conn, "cursor", None)
    if cursor_factory is None:
        return
    cursor = cursor_factory()
    try:
        for name, value in pragmas:
            try:
                cursor.execute(f"PRAGMA {name}={value}")
            except Exception as exc:
                if name in {"defensive", "writable_schema", "trusted_schema"}:
                    # Confirmation D-4 fallback: log + continue. The
                    # threat-model entry covers this case.
                    logger.warning(
                        "[WARN] PRAGMA %s=%s not supported on this "
                        "SQLite build (%r); falling back to OS-level "
                        "isolation per threat-model §T2",
                        name,
                        value,
                        exc,
                    )
                    continue
                raise
    finally:
        cursor.close()


def _set_app_pragmas(dbapi_conn: object, _connection_record: object) -> None:
    """``connect`` listener for the application engine."""
    _apply_pragmas(dbapi_conn, _APP_PRAGMAS)


def _set_migration_pragmas(
    dbapi_conn: object,
    _connection_record: object,
) -> None:
    """``connect`` listener for the migration engine."""
    _apply_pragmas(dbapi_conn, _MIGRATION_PRAGMAS)


__all__ = [
    "create_engine",
    "create_migration_engine",
]
