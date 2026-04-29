"""DB factory for tests: async SQLite engine + session factory in tempdir.

Per ``docs/features/http-api-foundation/http-api/test-design.md`` §外部 I/O 依存マップ.

Production code MUST NOT import this module.
"""

from __future__ import annotations

from pathlib import Path

from bakufu.infrastructure.persistence.sqlite.engine import create_engine
from bakufu.infrastructure.persistence.sqlite.session import make_session_factory
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def make_test_engine(db_path: Path) -> AsyncEngine:
    """Build a test-only async SQLite engine at ``db_path``.

    Uses the application-level engine configuration (8 PRAGMAs)
    so integration tests exercise the real DB behaviour.
    """
    url = f"sqlite+aiosqlite:///{db_path}"
    return create_engine(url)


def make_test_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to the test engine."""
    return make_session_factory(engine)


__all__ = ["make_test_engine", "make_test_session_factory"]
