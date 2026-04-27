"""Persistence drivers (SQLite + Alembic) for the bakufu Backend.

The package is intentionally thin at the top: SQLite is the only
storage target (see ``docs/architecture/tech-stack.md`` §DB), so the
``sqlite/`` subpackage holds engine / session / base / table modules
without an abstraction layer for "future Postgres support" (YAGNI).
Aggregate-specific Repository implementations land in their own
feature PRs (``feature/{aggregate}-repository``); this package
provides only the cross-cutting tables: ``audit_log`` /
``bakufu_pid_registry`` / ``domain_event_outbox``.
"""
