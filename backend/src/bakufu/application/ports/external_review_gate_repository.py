"""ExternalReviewGate Repository port.

Per ``docs/features/external-review-gate-repository/detailed-design.md``
§確定 R1-A (empire-repo / workflow-repo / agent-repo / room-repo /
directive-repo / task-repo テンプレート 100% 継承) plus Gate-specific
query methods:

* Protocol class with **no** ``@runtime_checkable`` decorator (empire-repo
  §確定 A: Python 3.12 ``typing.Protocol`` duck typing is sufficient).
* Every method declared ``async def`` (async-first contract).
* Argument and return types come exclusively from :mod:`bakufu.domain` —
  no SQLAlchemy types cross the port boundary.
* ``save`` signature is ``save(gate: ExternalReviewGate) -> None`` (standard
  1-argument pattern): :class:`ExternalReviewGate` carries all own attributes
  so the Repository reads them directly.
* Four Gate-specific query methods beyond the empire-repo §確定 B baseline
  (``find_pending_by_reviewer`` / ``find_by_task_id`` / ``count_by_decision``).
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.value_objects import GateId, OwnerId, ReviewDecision, TaskId


class ExternalReviewGateRepository(Protocol):
    """Persistence contract for the :class:`ExternalReviewGate` Aggregate Root.

    The application layer (``GateService``, future PRs) consumes this
    Protocol via dependency injection; the SQLite implementation lives in
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.external_review_gate_repository`.
    """

    async def find_by_id(self, gate_id: GateId) -> ExternalReviewGate | None:
        """Hydrate the Gate whose primary key equals ``gate_id``.

        Returns ``None`` when the row is absent. Both child tables
        (external_review_gate_attachments / external_review_audit_entries)
        are fetched and included in the hydrated Gate. SQLAlchemy / driver /
        ``pydantic.ValidationError`` exceptions propagate untouched so the
        application service's Unit-of-Work boundary can choose between
        rollback and surfaced error.
        """
        ...

    async def count(self) -> int:
        """Return ``SELECT COUNT(*) FROM external_review_gates``.

        Global count across all Gates regardless of decision or reviewer.
        Application services use this for monitoring / bulk introspection
        (empire-repo §確定 D 踏襲).
        """
        ...

    async def save(self, gate: ExternalReviewGate) -> None:
        """Persist ``gate`` via the §確定 R1-B 5-step delete-then-insert.

        The save flow covers all three tables:

        1. DELETE external_review_gate_attachments WHERE gate_id = :id
        2. DELETE external_review_audit_entries WHERE gate_id = :id
        3. UPSERT external_review_gates (ON CONFLICT id DO UPDATE mutable fields)
        4. INSERT external_review_gate_attachments (per Attachment in snapshot)
        5. INSERT external_review_audit_entries (per AuditEntry in audit_trail)

        The implementation must not call ``session.commit()`` /
        ``session.rollback()``; the application service owns the
        Unit-of-Work boundary (empire-repo §確定 B 踏襲).
        """
        ...

    async def find_pending_by_reviewer(self, reviewer_id: OwnerId) -> list[ExternalReviewGate]:
        """Return all PENDING Gates for ``reviewer_id`` ordered ``created_at DESC, id DESC``.

        Used by ``GateService`` to surface a reviewer's open review queue.
        Returns ``[]`` when no PENDING Gates exist for the given reviewer.

        ORDER BY ``created_at DESC, id DESC`` (BUG-EMR-001 規約: composite
        key for deterministic ordering — ``created_at`` alone is
        insufficient when multiple Gates share the same timestamp; ``id``
        (PK, UUID) is the tiebreaker that makes the result fully
        deterministic).
        """
        ...

    async def find_by_task_id(self, task_id: TaskId) -> list[ExternalReviewGate]:
        """Return all Gates for ``task_id`` ordered ``created_at ASC, id ASC``.

        Used by ``GateService`` to fetch the full review history for a Task.
        Returns ``[]`` when no Gates exist for the given Task.

        ORDER BY ``created_at ASC, id ASC`` — chronological ordering matches
        the "review history" read pattern where older gates appear first.
        """
        ...

    async def count_by_decision(self, decision: ReviewDecision) -> int:
        """Return ``SELECT COUNT(*) FROM external_review_gates WHERE decision = :decision``.

        Used for dashboard metrics (PENDING backlog size, APPROVED / REJECTED /
        CANCELLED historical counts).
        Returns 0 when no Gates exist with the given decision.
        """
        ...


__all__ = ["ExternalReviewGateRepository"]
