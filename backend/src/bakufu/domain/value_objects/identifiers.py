"""ID type aliases for the bakufu domain.

All identifiers are PEP 695 ``type`` aliases over ``UUID`` (UUIDv4 in
production). They are kept conceptually distinct so call-sites read clearly
and future ``NewType`` refinements are non-breaking.
"""

from __future__ import annotations

from uuid import UUID

# ---------------------------------------------------------------------------
# Identifier types
# ---------------------------------------------------------------------------
type EmpireId = UUID
"""Empire aggregate identifier (UUIDv4 per domain-model/value-objects.md)."""

type RoomId = UUID
"""Room aggregate identifier (UUIDv4)."""

type AgentId = UUID
"""Agent aggregate identifier (UUIDv4)."""

type WorkflowId = UUID
"""Workflow aggregate identifier (UUIDv4)."""

type StageId = UUID
"""Stage entity identifier (within Workflow aggregate)."""

type TransitionId = UUID
"""Transition entity identifier (within Workflow aggregate)."""

type SkillId = UUID
"""Skill identifier (referenced by :class:`SkillRef` inside Agent aggregate)."""

type DirectiveId = UUID
"""Directive aggregate identifier (UUIDv4)."""

type TaskId = UUID
"""Task aggregate identifier (UUIDv4). Referenced by :class:`Directive`
via ``task_id``; the Task aggregate itself ships in :mod:`bakufu.domain.task`."""

type OwnerId = UUID
"""Owner / Reviewer identifier (UUIDv4 per domain-model/value-objects.md).

Used by Task Aggregate behaviors that record an external-review actor
(``approve_review`` / ``reject_review`` / ``advance_to_next`` / ``complete`` /
``cancel``). The ``OwnerId`` is treated as opaque from the domain's point of
view; user-account binding is the application layer's job."""

type GateId = UUID
"""ExternalReviewGate aggregate identifier (UUIDv4).

The Gate is independent of Task (it has its own lifecycle, Tx
boundary, and supports multiple review rounds), so it carries its
own UUID rather than inheriting the parent ``TaskId`` —
external-review-gate detailed-design §確定 R1-A."""

type InternalGateId = UUID
"""InternalReviewGate aggregate identifier (UUIDv4).

Parallel to :data:`GateId` for the internal (agent-to-agent) review
Gate that gates ``INTERNAL_REVIEW`` Stage completion."""


__all__ = [
    "AgentId",
    "DirectiveId",
    "EmpireId",
    "GateId",
    "InternalGateId",
    "OwnerId",
    "RoomId",
    "SkillId",
    "StageId",
    "TaskId",
    "TransitionId",
    "WorkflowId",
]
