"""Alembic migration runner for Bootstrap stage 3 (Confirmation D-3).

Bootstrap stage 3 calls :func:`run_upgrade_head` with the *application*
engine; this module replaces the engine with a fresh **migration**
engine (``defensive=OFF`` / ``writable_schema=ON``), runs Alembic up to
``head``, then disposes of it. The application engine is never touched
by Alembic — Schneier 重大 2's defensive guarantee survives.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncEngine

from bakufu.infrastructure.persistence.sqlite.engine import create_migration_engine

logger = logging.getLogger(__name__)

# Backend package layout: backend/src/bakufu/infrastructure/persistence/sqlite/migrations.py
# alembic.ini lives at backend/alembic.ini
_ALEMBIC_INI: Path = Path(__file__).resolve().parents[5] / "alembic.ini"


async def run_upgrade_head(app_engine: AsyncEngine) -> str:
    """Apply ``alembic upgrade head`` via a temporary migration engine.

    Args:
        app_engine: Application-level engine; only its URL is read so
            the migration engine targets the same DB file.

    Returns:
        The ``head`` revision identifier that the schema is now at,
        for inclusion in the Bootstrap stage 3 completion log.

    Raises:
        Exception: Alembic itself surfaces a wide variety of errors;
            Bootstrap converts these to :class:`BakufuMigrationError`.
    """
    url = str(app_engine.url)
    migration_engine = create_migration_engine(url)
    try:
        async with migration_engine.connect() as connection:
            def _do_upgrade(sync_connection: object) -> None:
                from alembic import command

                cfg = Config(str(_ALEMBIC_INI))
                cfg.set_main_option("script_location", str(_ALEMBIC_INI.parent / "alembic"))
                cfg.attributes["connection"] = sync_connection
                command.upgrade(cfg, "head")

            await connection.run_sync(_do_upgrade)

        cfg = Config(str(_ALEMBIC_INI))
        cfg.set_main_option("script_location", str(_ALEMBIC_INI.parent / "alembic"))
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        return head or ""
    finally:
        await migration_engine.dispose()


__all__ = ["run_upgrade_head"]
