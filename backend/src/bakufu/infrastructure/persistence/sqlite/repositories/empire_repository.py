"""SQLite adapter for :class:`bakufu.application.ports.EmpireRepository`.

Implements the §確定 B "delete-then-insert" save flow:

1. ``empires`` UPSERT (id-conflict → name update)
2. ``empire_room_refs`` DELETE WHERE empire_id = ?
3. ``empire_room_refs`` bulk INSERT (one row per ``RoomRef``)
4. ``empire_agent_refs`` DELETE WHERE empire_id = ?
5. ``empire_agent_refs`` bulk INSERT (one row per ``AgentRef``)

The repository **never** calls ``session.commit()`` /
``session.rollback()``: the caller-side service runs
``async with session.begin():`` so the five steps above stay in one
transaction (§確定 B Tx 境界の責務分離). This also lets a single
service combine multiple Repositories in the same Unit-of-Work
(``EmpireRepository.save`` + Outbox row append, etc.).

``_to_row`` / ``_from_row`` are kept as private methods on the class
so both directions live next to each other and tests don't accidentally
acquire a public conversion API to depend on (§確定 C).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.empire import Empire
from bakufu.domain.value_objects import (
    AgentRef,
    EmpireId,
    Role,
    RoomRef,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_agent_refs import (
    EmpireAgentRefRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.empire_room_refs import (
    EmpireRoomRefRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.empires import EmpireRow


class SqliteEmpireRepository:
    """SQLite implementation of :class:`EmpireRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, empire_id: EmpireId) -> Empire | None:
        """SELECT empires + side tables, hydrate via :meth:`_from_row`.

        Returns ``None`` when the empires row is absent. The two side
        SELECTs run sequentially to keep the SQL trivial; bulk Empires
        will not exceed Confirmation C's ``len(rooms) ≤ 100`` cap, so
        IN-clause batching is unnecessary for MVP.
        """
        empire_stmt = select(EmpireRow).where(EmpireRow.id == empire_id)
        empire_row = (await self._session.execute(empire_stmt)).scalar_one_or_none()
        if empire_row is None:
            return None

        # BUG-EMR-001 fix: ORDER BY room_id / agent_id makes the
        # hydrated list deterministic. Without it SQLite returns rows
        # in internal-scan order, which broke ``Empire == Empire``
        # round-trip equality (the Aggregate VO compares list-by-list).
        # See docs/features/empire-repository/detailed-design.md
        # §Known Issues for the design resolution; basic-design.md
        # L127-128 froze ``ORDER BY room_id`` / ``ORDER BY agent_id``
        # as the design contract.
        room_stmt = (
            select(EmpireRoomRefRow)
            .where(EmpireRoomRefRow.empire_id == empire_id)
            .order_by(EmpireRoomRefRow.room_id)
        )
        room_rows = list((await self._session.execute(room_stmt)).scalars().all())

        agent_stmt = (
            select(EmpireAgentRefRow)
            .where(EmpireAgentRefRow.empire_id == empire_id)
            .order_by(EmpireAgentRefRow.agent_id)
        )
        agent_rows = list((await self._session.execute(agent_stmt)).scalars().all())

        return self._from_row(empire_row, room_rows, agent_rows)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM empires``.

        ``EmpireService.create()`` consumes this to enforce the
        singleton invariant (§確定 D); the Repository itself is silent
        about whether ``count != 0`` is an error — that decision is
        the application service's.

        Implementation detail: SQLAlchemy's ``func.count()`` issues a
        proper ``SELECT COUNT(*)`` so SQLite returns one scalar row
        instead of streaming every PK back to Python. This matters as
        a **template responsibility** for the six follow-up Repository
        PRs (workflow / agent / room / directive / task /
        external-review-gate) — Stage / Task tables can hold hundreds
        of rows, so the pattern emitted here propagates downstream.
        """
        stmt = select(func.count()).select_from(EmpireRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, empire: Empire) -> None:
        """Persist ``empire`` via the §確定 B five-step delete-then-insert.

        The caller is responsible for the surrounding
        ``async with session.begin():`` block; failures inside any
        step propagate untouched so the Unit-of-Work boundary in the
        application service can rollback cleanly.
        """
        empire_row, room_refs, agent_refs = self._to_row(empire)

        # Step 1: empires UPSERT (id PK, ON CONFLICT update name).
        upsert_stmt = sqlite_insert(EmpireRow).values(empire_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={"name": upsert_stmt.excluded.name},
        )
        await self._session.execute(upsert_stmt)

        # Step 2: empire_room_refs DELETE.
        await self._session.execute(
            delete(EmpireRoomRefRow).where(EmpireRoomRefRow.empire_id == empire.id)
        )

        # Step 3: empire_room_refs bulk INSERT (skip when no rooms).
        if room_refs:
            await self._session.execute(insert(EmpireRoomRefRow), room_refs)

        # Step 4: empire_agent_refs DELETE.
        await self._session.execute(
            delete(EmpireAgentRefRow).where(EmpireAgentRefRow.empire_id == empire.id)
        )

        # Step 5: empire_agent_refs bulk INSERT (skip when no agents).
        if agent_refs:
            await self._session.execute(insert(EmpireAgentRefRow), agent_refs)

    # ---- private domain ↔ row converters (§確定 C) -------------------
    def _to_row(
        self,
        empire: Empire,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        """Split ``empire`` into ``(empires_row, room_refs, agent_refs)``.

        The three return values match the three tables that
        :meth:`save` writes. SQLAlchemy ``Row`` objects are
        intentionally avoided here so the domain layer never gains an
        accidental dependency on the SQLAlchemy type hierarchy.
        """
        empire_row: dict[str, Any] = {
            "id": empire.id,
            "name": empire.name,
        }
        room_refs: list[dict[str, Any]] = [
            {
                "empire_id": empire.id,
                "room_id": ref.room_id,
                "name": ref.name,
                "archived": ref.archived,
            }
            for ref in empire.rooms
        ]
        agent_refs: list[dict[str, Any]] = [
            {
                "empire_id": empire.id,
                "agent_id": ref.agent_id,
                "name": ref.name,
                "role": ref.role.value,
            }
            for ref in empire.agents
        ]
        return empire_row, room_refs, agent_refs

    def _from_row(
        self,
        empire_row: EmpireRow,
        room_rows: list[EmpireRoomRefRow],
        agent_rows: list[EmpireAgentRefRow],
    ) -> Empire:
        """Hydrate an :class:`Empire` Aggregate Root from its three rows.

        ``Empire.model_validate`` re-runs the post-validator so
        Repository-side hydration goes through the same invariant
        checks that ``EmpireService.create()`` does at construction
        time. The contract (§確定 C) is "Repository hydration produces
        a valid Empire or raises".
        """
        rooms = [
            RoomRef(
                room_id=_uuid(row.room_id),
                name=row.name,
                archived=row.archived,
            )
            for row in room_rows
        ]
        agents = [
            AgentRef(
                agent_id=_uuid(row.agent_id),
                name=row.name,
                role=Role(row.role),
            )
            for row in agent_rows
        ]
        return Empire(
            id=_uuid(empire_row.id),
            name=empire_row.name,
            rooms=rooms,
            agents=agents,
        )


def _uuid(value: UUID | str) -> UUID:
    """Coerce a row value to :class:`uuid.UUID`.

    SQLAlchemy's UUIDStr TypeDecorator already returns ``UUID``
    instances on ``process_result_value``, but defensive coercion lets
    raw-SQL hydration paths route through the same code without an
    extra ``isinstance`` ladder at every call site.
    """
    if isinstance(value, UUID):
        return value
    return UUID(value)


__all__ = ["SqliteEmpireRepository"]
