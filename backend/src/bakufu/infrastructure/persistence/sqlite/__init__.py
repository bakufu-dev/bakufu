"""SQLite persistence layer (async via :mod:`sqlalchemy.ext.asyncio`).

The package boundary mirrors the design's responsibility split
(see ``docs/features/persistence-foundation/detailed-design/``):

* :mod:`bakufu.infrastructure.persistence.sqlite.engine` —
  ``AsyncEngine`` factory with PRAGMA enforcement + dual-connection
  separation (application vs. migration).
* :mod:`bakufu.infrastructure.persistence.sqlite.session` —
  ``async_sessionmaker`` factory (Unit-of-Work boundary).
* :mod:`bakufu.infrastructure.persistence.sqlite.base` — declarative
  base + UUID / UTC-aware datetime / JSON :class:`TypeDecorator` types.
* :mod:`bakufu.infrastructure.persistence.sqlite.tables` —
  cross-cutting tables (``audit_log`` / ``bakufu_pid_registry`` /
  ``domain_event_outbox``) with their masking listeners.
* :mod:`bakufu.infrastructure.persistence.sqlite.outbox` —
  Outbox dispatcher + handler registry skeleton.
* :mod:`bakufu.infrastructure.persistence.sqlite.pid_gc` —
  Bootstrap-stage 4 orphan-process garbage collection.
"""
