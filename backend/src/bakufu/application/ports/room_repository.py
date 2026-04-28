"""Room Repository port.

Per ``docs/features/room-repository/detailed-design.md`` §確定 R1-A
(empire-repo / workflow-repo / agent-repo テンプレート 100% 継承) plus
§確定 R1-F (``find_by_name`` 第 4 method — Empire-scoped name lookup)
and §確定 R1-H (``save(room, empire_id)`` — empire_id passed as argument
because :class:`Room` Aggregate holds no ``empire_id`` attribute):

* Protocol class with **no** ``@runtime_checkable`` decorator (empire-repo
  §確定 A: Python 3.12 ``typing.Protocol`` duck typing is sufficient).
* Every method declared ``async def`` (async-first contract).
* Argument and return types come exclusively from :mod:`bakufu.domain` —
  no SQLAlchemy types cross the port boundary.
* ``save`` signature is ``save(room: Room, empire_id: EmpireId) -> None``
  because :class:`Room` does not carry ``empire_id`` (ownership is
  expressed via ``Empire.rooms: list[RoomRef]``); the calling service
  always has ``empire_id`` at hand and passes it as an argument rather
  than forcing a domain-model change (§確定 R1-H).
* ``find_by_name`` takes ``empire_id`` first because Room name uniqueness
  is Empire-scoped (§確定 R1-F: ``WHERE empire_id = :e AND name = :n``).
"""

from __future__ import annotations

from typing import Protocol

from bakufu.domain.room.room import Room
from bakufu.domain.value_objects import EmpireId, RoomId


class RoomRepository(Protocol):
    """Persistence contract for the :class:`Room` Aggregate Root.

    The application layer (``RoomService``, ``EmpireService``, future PRs)
    consumes this Protocol via dependency injection; the SQLite implementation
    lives in
    :mod:`bakufu.infrastructure.persistence.sqlite.repositories.room_repository`.
    """

    async def find_by_id(self, room_id: RoomId) -> Room | None:
        """Hydrate the Room whose primary key equals ``room_id``.

        Returns ``None`` when the row is absent. SQLAlchemy / driver /
        ``pydantic.ValidationError`` exceptions propagate untouched so the
        application service's Unit-of-Work boundary can choose between
        rollback and surfaced error.
        """
        ...

    async def count(self) -> int:
        """Return ``SELECT COUNT(*) FROM rooms``.

        Application services use this for monitoring / bulk introspection.
        The count is empire-global (§確定 R1-D: SQL ``COUNT(*)`` contract,
        empire-repo §確定 D 踏襲).
        """
        ...

    async def save(self, room: Room, empire_id: EmpireId) -> None:
        """Persist ``room`` via the §確定 R1-B three-step delete-then-insert.

        ``empire_id`` is passed as an explicit argument because :class:`Room`
        does not hold ``empire_id`` as an attribute (room §確定 — ownership is
        expressed via ``Empire.rooms``). The calling service always has
        ``empire_id`` in scope and passes it here (§確定 R1-H).

        The implementation must run the three-step sequence (UPSERT rooms →
        DELETE room_members → bulk INSERT room_members) within the
        **caller-managed** transaction. Repositories never call
        ``session.commit()`` / ``session.rollback()``; the application service
        owns the Unit-of-Work boundary (empire-repo §確定 B 踏襲).
        """
        ...

    async def find_by_name(self, empire_id: EmpireId, name: str) -> Room | None:
        """Hydrate the Room named ``name`` inside Empire ``empire_id`` (§確定 R1-F).

        Two-stage flow: a lightweight ``SELECT id ... LIMIT 1`` locates the
        RoomId, then delegation to :meth:`find_by_id` so the child-table
        SELECTs and ``_from_row`` conversion stay single-sourced (agent §R1-C
        inheritance pattern).

        Returns ``None`` when no Room matches. The implementation must not
        fetch all Rooms and filter in Python — that pattern is explicitly
        rejected as a memory / N+1 pitfall in §確定 R1-F (c).
        """
        ...


__all__ = ["RoomRepository"]
