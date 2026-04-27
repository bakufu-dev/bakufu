"""Cross-cutting tables shared across all Aggregates.

* :mod:`...tables.audit_log` — Admin CLI audit trail (DELETE-rejecting).
* :mod:`...tables.pid_registry` — bakufu_pid_registry (orphan-process GC).
* :mod:`...tables.outbox` — domain_event_outbox (Outbox pattern).

Each module declares its ORM mapping with :class:`MaskedJSONEncoded`
/ :class:`MaskedText` TypeDecorators (defined in
:mod:`bakufu.infrastructure.persistence.sqlite.base`) that route
secret-bearing columns through the masking gateway via
``process_bind_param``. The TypeDecorators activate on bind-parameter
resolution so Core ``insert(table).values(...)`` and ORM
``Session.add()`` both fire — see
``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D for the technical rationale (旧 ``before_insert`` /
``before_update`` event-listener approach was reverse-rejected after
PR #23 BUG-PF-001 proved that listeners do not fire for Core
``insert(table).values({...})``).
"""

from __future__ import annotations

from bakufu.infrastructure.persistence.sqlite.tables import (
    audit_log,
    outbox,
    pid_registry,
)

__all__ = ["audit_log", "outbox", "pid_registry"]
