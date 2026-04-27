"""Workflow Repository port.

Per ``docs/features/workflow-repository/detailed-design.md`` §確定 A
(empire-repository テンプレート 100% 継承):

* Protocol class with **no** ``@runtime_checkable`` decorator — Python
  3.12 ``typing.Protocol`` duck typing is enough; the runtime overhead
  of ``@runtime_checkable`` adds ``isinstance`` paths the application
  layer never needs (mirrors :mod:`bakufu.application.ports.empire_repository`).
* Every method declared ``async def`` (async-first contract) so the
  application layer can compose Repositories inside an
  ``async with session.begin():`` Unit-of-Work.
* Argument and return types come exclusively from
  :mod:`bakufu.domain` — no SQLAlchemy types leak across the port.
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.value_objects import WorkflowId
from bakufu.domain.workflow import Workflow


class WorkflowRepository(Protocol):
    """Persistence contract for the :class:`Workflow` Aggregate Root.

    The application layer (``WorkflowService``, future PR) consumes
    this Protocol via dependency injection; the SQLite implementation
    lives in
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository`.
    """

    async def find_by_id(self, workflow_id: WorkflowId) -> Workflow | None:
        """Hydrate the Workflow whose primary key equals ``workflow_id``.

        Returns ``None`` when the row is absent. Implementations
        propagate SQLAlchemy / driver / ``pydantic.ValidationError``
        exceptions unchanged so the Unit-of-Work boundary in the
        application service can choose between rollback and surfaced
        error.
        """
        ...

    async def count(self) -> int:
        """Return ``SELECT COUNT(*) FROM workflows``.

        Application services use this to introspect whether at least
        one Workflow has been registered (e.g. preset bootstrap
        check). Deciding what the count means is the *application*
        layer's call (§確定 D).
        """
        ...

    async def save(self, workflow: Workflow) -> None:
        """Persist ``workflow`` via the §確定 B delete-then-insert flow.

        The implementation must run the five-step sequence (UPSERT
        workflows → DELETE workflow_stages → bulk INSERT stages →
        DELETE workflow_transitions → bulk INSERT transitions) within
        the **caller-managed** transaction. Repositories never call
        ``session.commit()`` / ``session.rollback()``; the application
        service owns the Unit-of-Work boundary.
        """
        ...


__all__ = ["WorkflowRepository"]
