"""``async_sessionmaker`` factory (Unit-of-Work boundary).

Aggregate Repositories obtain an :class:`AsyncSession` from the
factory created here; each ``async with session.begin():`` block
encloses one Unit-of-Work. Sessions are configured for explicit
flushing (``autoflush=False``) so listener-driven masking applies
exactly once per row write — auto-flushing inside read queries would
add ambiguity nobody wants.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def make_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Build the session factory for ``engine``.

    Args:
        engine: Application-level engine from
            :func:`bakufu.infrastructure.persistence.sqlite.engine.create_engine`.

    The factory is async, ``expire_on_commit=False`` (so domain objects
    survive across commit boundaries), and ``autoflush=False`` (so
    masking listeners are predictable).
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


__all__ = ["make_session_factory"]
