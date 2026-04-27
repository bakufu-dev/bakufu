"""Cross-cutting + Aggregate-specific tables.

Cross-cutting (M2 persistence-foundation, PR #23):

* :mod:`...tables.audit_log` — Admin CLI audit trail (DELETE-rejecting).
* :mod:`...tables.pid_registry` — bakufu_pid_registry (orphan-process GC).
* :mod:`...tables.outbox` — domain_event_outbox (Outbox pattern).

Empire Aggregate (PR #25):

* :mod:`...tables.empires` — Empire root row.
* :mod:`...tables.empire_room_refs` — RoomRef collection.
* :mod:`...tables.empire_agent_refs` — AgentRef collection.

Secret-bearing tables declare their columns with
:class:`MaskedJSONEncoded` / :class:`MaskedText` TypeDecorators
(defined in :mod:`bakufu.infrastructure.persistence.sqlite.base`) that
route values through the masking gateway via
``process_bind_param``. The TypeDecorators activate on bind-parameter
resolution so Core ``insert(table).values(...)`` and ORM
``Session.add()`` both fire — see
``docs/features/persistence-foundation/requirements-analysis.md``
§確定 R1-D for the technical rationale (旧 ``before_insert`` /
``before_update`` event-listener approach was reverse-rejected after
PR #23 BUG-PF-001 proved that listeners do not fire for Core
``insert(table).values({...})``).

Empire tables carry **no** secret-bearing columns; the explicit
absence is registered with the CI three-layer defense
(grep guard + arch test + storage.md §逆引き表) so a future PR cannot
silently swap a column to a secret-bearing semantic.
"""

from __future__ import annotations

from bakufu.infrastructure.persistence.sqlite.tables import (
    audit_log,
    empire_agent_refs,
    empire_room_refs,
    empires,
    outbox,
    pid_registry,
)

__all__ = [
    "audit_log",
    "empire_agent_refs",
    "empire_room_refs",
    "empires",
    "outbox",
    "pid_registry",
]
