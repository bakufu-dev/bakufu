"""Cross-cutting tables shared across all Aggregates.

* :mod:`...tables.audit_log` — Admin CLI audit trail (DELETE-rejecting).
* :mod:`...tables.pid_registry` — bakufu_pid_registry (orphan-process GC).
* :mod:`...tables.outbox` — domain_event_outbox (Outbox pattern).

Each module declares its ORM mapping **and** registers the
``before_insert`` / ``before_update`` listeners that route
secret-bearing columns through the masking gateway. The listeners are
module-level so they activate at import time — the package
``__init__`` imports each table module to ensure no consumer can
forget to wire them up.
"""

from __future__ import annotations

from bakufu.infrastructure.persistence.sqlite.tables import (
    audit_log,
    outbox,
    pid_registry,
)

__all__ = ["audit_log", "outbox", "pid_registry"]
