"""Alembic environment for the bakufu Backend.

Two modes:

* **Programmatic** — Bootstrap stage 3 calls ``command.upgrade`` from
  inside an active asyncio loop. The migrations runner pre-establishes
  a sync :class:`Connection` and stuffs it into ``config.attributes``;
  this module reuses it instead of opening a new asyncio loop.
* **CLI standalone** — ``alembic upgrade head`` from a shell. There is
  no asyncio loop yet, so we open the engine ourselves and ``asyncio.run``
  the upgrade.

Both paths share the same ``target_metadata`` so autogenerate sees
every cross-cutting table.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from bakufu.infrastructure.persistence.sqlite.base import Base

# Importing the table modules registers the ORM mappings + listeners
# with the metadata, so autogenerate sees them.
from bakufu.infrastructure.persistence.sqlite.tables import (  # noqa: F401
    audit_log,
    outbox,
    pid_registry,
)
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_url() -> str:
    """Pick the SQLAlchemy URL.

    Priority:
    1. ``BAKUFU_ALEMBIC_URL`` env var (test rigs / CI override).
    2. ``BAKUFU_DATA_DIR`` env var → ``<dir>/bakufu.db``.
    3. ``alembic.ini`` ``sqlalchemy.url`` value (CLI fallback).
    """
    override = os.environ.get("BAKUFU_ALEMBIC_URL")
    if override:
        return override
    data_dir = os.environ.get("BAKUFU_DATA_DIR")
    if data_dir:
        return f"sqlite+aiosqlite:///{Path(data_dir) / 'bakufu.db'}"
    raw = config.get_main_option("sqlalchemy.url")
    if raw is None:
        raise RuntimeError(
            "alembic env: sqlalchemy.url not configured and no "
            "BAKUFU_DATA_DIR / BAKUFU_ALEMBIC_URL set"
        )
    return raw


def run_migrations_offline() -> None:
    """Render SQL without opening a connection."""
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    """CLI-standalone path: build an engine and run the upgrade."""
    connectable: AsyncEngine = async_engine_from_config(
        {"sqlalchemy.url": _resolve_url()},
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    # Programmatic path (Bootstrap stage 3): caller has already opened
    # a sync Connection inside ``connection.run_sync`` and stuffed it
    # into ``config.attributes['connection']``.
    injected = config.attributes.get("connection", None)
    if isinstance(injected, Connection):
        _do_run_migrations(injected)
        return
    # CLI standalone: spin up our own engine and asyncio loop.
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
