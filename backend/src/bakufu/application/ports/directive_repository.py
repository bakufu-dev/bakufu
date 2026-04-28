"""Directive Repository port.

Per ``docs/features/directive-repository/detailed-design.md`` §確定 R1-A
(empire-repo / workflow-repo / agent-repo / room-repo テンプレート 100% 継承)
plus §確定 R1-D (``find_by_room`` — Room-scoped Directive lookup, ORDER BY
``created_at DESC, id DESC`` for deterministic ordering per BUG-EMR-001 規約)
and §確定 R1-F (``save(directive)`` — standard 1-argument pattern because
:class:`Directive` Aggregate holds ``target_room_id`` as its own attribute):

* Protocol class with **no** ``@runtime_checkable`` decorator (empire-repo
  §確定 A: Python 3.12 ``typing.Protocol`` duck typing is sufficient).
* Every method declared ``async def`` (async-first contract).
* Argument and return types come exclusively from :mod:`bakufu.domain` —
  no SQLAlchemy types cross the port boundary.
* ``save`` signature is ``save(directive: Directive) -> None`` (standard
  1-argument pattern, §確定 R1-F): :class:`Directive` carries
  ``target_room_id`` as an attribute so the Repository can read it
  directly — the non-symmetric Room pattern is not needed here.
* ``find_by_room`` is the 4th method; ``find_by_task_id`` is deferred to
  the task-repository PR (YAGNI, §確定 R1-D 後続申し送り).
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.directive.directive import Directive
from bakufu.domain.value_objects import DirectiveId, RoomId


class DirectiveRepository(Protocol):
    """Persistence contract for the :class:`Directive` Aggregate Root.

    The application layer (``DirectiveService``, future PRs) consumes this
    Protocol via dependency injection; the SQLite implementation lives in
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.directive_repository`.
    """

    async def find_by_id(self, directive_id: DirectiveId) -> Directive | None:
        """Hydrate the Directive whose primary key equals ``directive_id``.

        Returns ``None`` when the row is absent. SQLAlchemy / driver /
        ``pydantic.ValidationError`` exceptions propagate untouched so the
        application service's Unit-of-Work boundary can choose between
        rollback and surfaced error.
        """
        ...

    async def count(self) -> int:
        """Return ``SELECT COUNT(*) FROM directives``.

        Application services use this for monitoring / bulk introspection.
        The count is global (§確定 R1-A: SQL ``COUNT(*)`` contract,
        empire-repo §確定 D 踏襲).
        """
        ...

    async def save(self, directive: Directive) -> None:
        """Persist ``directive`` via a single-table UPSERT (§確定 R1-B).

        Directive has no child tables, so the save flow reduces to one step:
        ``INSERT INTO directives ... ON CONFLICT (id) DO UPDATE SET ...``.

        ``target_room_id`` is read from ``directive.target_room_id`` directly
        (§確定 R1-F: standard 1-argument pattern). The implementation must
        not call ``session.commit()`` / ``session.rollback()``; the
        application service owns the Unit-of-Work boundary (empire-repo
        §確定 B 踏襲).
        """
        ...

    async def find_by_room(self, room_id: RoomId) -> list[Directive]:
        """Return all Directives targeting ``room_id``, newest first.

        ORDER BY ``created_at DESC, id DESC`` (BUG-EMR-001 規約: composite
        key for deterministic ordering — ``created_at`` alone is insufficient
        when multiple Directives share the same timestamp; ``id`` (PK, UUID)
        is the tiebreaker that makes the result fully deterministic).

        Returns ``[]`` when no Directives exist for the Room. The empty-list
        response does not distinguish between "Room exists but has no
        Directives" and "Room does not exist" — that distinction is the
        application layer's responsibility.
        """
        ...


__all__ = ["DirectiveRepository"]
