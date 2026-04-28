"""Task Repository port.

Per ``docs/features/task-repository/detailed-design.md`` §確定 R1-A
(empire-repo / workflow-repo / agent-repo / room-repo / directive-repo
テンプレート 100% 継承) plus §確定 R1-D (additional Task-specific methods):

* Protocol class with **no** ``@runtime_checkable`` decorator (empire-repo
  §確定 A: Python 3.12 ``typing.Protocol`` duck typing is sufficient).
* Every method declared ``async def`` (async-first contract).
* Argument and return types come exclusively from :mod:`bakufu.domain` —
  no SQLAlchemy types cross the port boundary.
* ``save`` signature is ``save(task: Task) -> None`` (standard 1-argument
  pattern, §確定 R1-F): :class:`Task` carries ``room_id`` and
  ``directive_id`` as own attributes so the Repository reads them directly.
* Three Task-specific query methods beyond the empire-repo §確定 B baseline
  (``count_by_status`` / ``count_by_room`` / ``find_blocked``) are
  included per §確定 R1-D.
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.task.task import Task
from bakufu.domain.value_objects import RoomId, TaskId, TaskStatus


class TaskRepository(Protocol):
    """Persistence contract for the :class:`Task` Aggregate Root.

    The application layer (``TaskService``, future PRs) consumes this
    Protocol via dependency injection; the SQLite implementation lives in
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.task_repository`.
    """

    async def find_by_id(self, task_id: TaskId) -> Task | None:
        """Hydrate the Task whose primary key equals ``task_id``.

        Returns ``None`` when the row is absent. All five child tables
        (task_assigned_agents / conversations / conversation_messages /
        deliverables / deliverable_attachments) are fetched and included
        in the hydrated Task. SQLAlchemy / driver / ``pydantic.ValidationError``
        exceptions propagate untouched so the application service's
        Unit-of-Work boundary can choose between rollback and surfaced error.
        """
        ...

    async def count(self) -> int:
        """Return ``SELECT COUNT(*) FROM tasks``.

        Global count across all Tasks regardless of status or room.
        Application services use this for monitoring / bulk introspection
        (empire-repo §確定 D 踏襲).
        """
        ...

    async def save(self, task: Task) -> None:
        """Persist ``task`` via the §確定 R1-B 9-step delete-then-insert.

        The save flow covers all six tables:
        1. DELETE deliverables (CASCADE removes deliverable_attachments)
        2. DELETE conversations (CASCADE removes conversation_messages)
        3. DELETE task_assigned_agents
        4. UPSERT tasks (ON CONFLICT id DO UPDATE)
        5. INSERT task_assigned_agents (per AgentId, with order_index)
        6. INSERT conversations (per Conversation)
        7. INSERT conversation_messages (per Message per Conversation)
        8. INSERT deliverables (per Deliverable)
        9. INSERT deliverable_attachments (per Attachment per Deliverable)

        The implementation must not call ``session.commit()`` /
        ``session.rollback()``; the application service owns the
        Unit-of-Work boundary (empire-repo §確定 B 踏襲).
        """
        ...

    async def count_by_status(self, status: TaskStatus) -> int:
        """Return ``SELECT COUNT(*) FROM tasks WHERE status = :status``.

        Used for Room dashboard status aggregations and monitoring.
        Returns 0 when no Tasks exist with the given status.
        """
        ...

    async def count_by_room(self, room_id: RoomId) -> int:
        """Return ``SELECT COUNT(*) FROM tasks WHERE room_id = :room_id``.

        Used for Room detail page Task count display (after HTTP API PR).
        Returns 0 when no Tasks exist for the given Room.
        """
        ...

    async def find_blocked(self) -> list[Task]:
        """Return all BLOCKED Tasks ordered by ``updated_at DESC, id DESC``.

        Used by ``TaskService.find_blocked_tasks()`` (Issue #38) for
        障害隔離 — recently blocked Tasks are surfaced first so operators
        can triage in priority order.

        ORDER BY ``updated_at DESC, id DESC`` (BUG-EMR-001 規約: composite
        key for deterministic ordering — ``updated_at`` alone is
        insufficient when multiple Tasks share the same timestamp; ``id``
        (PK, UUID) is the tiebreaker that makes the result fully
        deterministic).

        Returns ``[]`` when no BLOCKED Tasks exist.
        """
        ...


__all__ = ["TaskRepository"]
