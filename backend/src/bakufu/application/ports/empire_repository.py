"""Empire Repository port.

Per ``docs/features/empire-repository/detailed-design.md`` §確定 A:

* Protocol class with **no** ``@runtime_checkable`` decorator — Python
  3.12 ``typing.Protocol`` duck typing is enough; the runtime overhead
  of ``@runtime_checkable`` adds ``isinstance`` paths the application
  layer never needs.
* Every method declared ``async def`` (async-first contract) so the
  application layer can compose Repositories inside an
  ``async with session.begin():`` Unit-of-Work.
* Argument and return types come exclusively from
  :mod:`bakufu.domain` — no SQLAlchemy types leak across the port.
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.empire import Empire
from bakufu.domain.value_objects import EmpireId


class EmpireRepository(Protocol):
    """Persistence contract for the :class:`Empire` Aggregate Root.

    The application layer (``EmpireService``) consumes this Protocol
    via dependency injection; the SQLite implementation lives in
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.empire_repository`.
    """

    async def find_by_id(self, empire_id: EmpireId) -> Empire | None:
        """Hydrate the Empire whose primary key equals ``empire_id``.

        Returns ``None`` when the row is absent. Implementations
        propagate SQLAlchemy / driver exceptions unchanged so the
        Unit-of-Work boundary in the application service can choose
        between rollback and surfaced error.
        """
        ...

    async def count(self) -> int:
        """Return ``SELECT COUNT(*) FROM empires``.

        ``EmpireService.create()`` calls this to enforce the Empire
        singleton invariant. The count itself is the Repository's
        responsibility; deciding whether ``count == 0`` /
        ``count == 1`` / ``count >= 2`` triggers a service-level error
        is the *application* layer's call (§確定 D).
        """
        ...

    async def save(self, empire: Empire) -> None:
        """Persist ``empire`` via the §確定 B delete-then-insert flow.

        The implementation must run the five-step sequence (UPSERT
        empires → DELETE empire_room_refs → bulk INSERT room_refs →
        DELETE empire_agent_refs → bulk INSERT agent_refs) within the
        **caller-managed** transaction. Repositories never call
        ``session.commit()`` / ``session.rollback()``; the application
        service owns the Unit-of-Work boundary.
        """
        ...


__all__ = ["EmpireRepository"]
