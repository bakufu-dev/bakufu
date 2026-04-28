"""Cross-cutting + Aggregate-specific tables.

Cross-cutting (M2 persistence-foundation, PR #23):

* :mod:`...tables.audit_log` — Admin CLI audit trail (DELETE-rejecting).
* :mod:`...tables.pid_registry` — bakufu_pid_registry (orphan-process GC).
* :mod:`...tables.outbox` — domain_event_outbox (Outbox pattern).

Empire Aggregate (PR #25):

* :mod:`...tables.empires` — Empire root row.
* :mod:`...tables.empire_room_refs` — RoomRef collection.
* :mod:`...tables.empire_agent_refs` — AgentRef collection.

Workflow Aggregate (PR #31):

* :mod:`...tables.workflows` — Workflow root row (entry_stage_id has
  no DB-level FK; the Aggregate invariant guards it instead).
* :mod:`...tables.workflow_stages` — Stage child rows. The
  ``notify_channels_json`` column is the **first** ``MaskedJSONEncoded``
  column outside ``audit_log`` / ``domain_event_outbox`` and is
  registered with the CI three-layer defense's *positive* contract.
* :mod:`...tables.workflow_transitions` — Transition child rows
  (no-mask).

Agent Aggregate (PR #32):

* :mod:`...tables.agents` — Agent root row. The ``prompt_body``
  column is the **first** ``MaskedText`` Repository application of
  Schneier 申し送り #3 (PR #23 hook → PR #32 wire-up); the table is
  registered with the CI three-layer defense's *partial-mask*
  contract pinning exactly one masked column.
* :mod:`...tables.agent_providers` — ProviderConfig child rows.
  Carries a partial unique index ``WHERE is_default = 1`` for the
  Defense-in-Depth "exactly one default provider per Agent" floor.
* :mod:`...tables.agent_skills` — SkillRef child rows (no-mask).

Room Aggregate (PR #33):

* :mod:`...tables.rooms` — Room root row. The
  ``prompt_kit_prefix_markdown`` column is ``MaskedText`` (room
  §確定 G 実適用); the table is registered with the CI three-layer
  defense's *partial-mask* contract pinning exactly one masked column.
  ``empire_room_refs.room_id → rooms.id`` FK is closed in Alembic
  0005 (BUG-EMR-001 closure).
* :mod:`...tables.room_members` — AgentMembership child rows (no-mask).
  Composite PK + explicit ``UniqueConstraint`` for §確定 R1-D
  Defense-in-Depth; ``agent_id`` intentionally has no FK onto
  ``agents.id`` (application-layer responsibility).

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
silently swap a column to a secret-bearing semantic. The Workflow
``workflows`` / ``workflow_transitions`` tables follow the same
no-mask pattern; only ``workflow_stages.notify_channels_json`` is
secret-bearing on the Workflow side.
"""

from __future__ import annotations

from bakufu.infrastructure.persistence.sqlite.tables import (
    agent_providers,
    agent_skills,
    agents,
    audit_log,
    empire_agent_refs,
    empire_room_refs,
    empires,
    outbox,
    pid_registry,
    room_members,
    rooms,
    workflow_stages,
    workflow_transitions,
    workflows,
)

__all__ = [
    "agent_providers",
    "agent_skills",
    "agents",
    "audit_log",
    "empire_agent_refs",
    "empire_room_refs",
    "empires",
    "outbox",
    "pid_registry",
    "room_members",
    "rooms",
    "workflow_stages",
    "workflow_transitions",
    "workflows",
]
