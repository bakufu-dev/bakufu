"""SQLite adapter for :class:`bakufu.application.ports.RoomRepository`.

Implements the §確定 R1-B three-step save flow over two tables
(``rooms`` / ``room_members``):

1. ``rooms`` UPSERT (id-conflict → workflow_id + name + description +
   prompt_kit_prefix_markdown + archived update; ``prompt_kit_prefix_markdown``
   binds through :class:`MaskedText` so any embedded API key / OAuth token /
   Discord webhook secret is redacted *before* it hits SQLite — room §確定 G
   实適用, §確定 R1-J 不可逆性凍結).
2. ``room_members`` DELETE WHERE room_id = ?
3. ``room_members`` bulk INSERT (one row per AgentMembership).

The repository **never** calls ``session.commit()`` / ``session.rollback()``:
the caller-side service runs ``async with session.begin():`` so the three
steps above stay in one transaction (empire-repo §確定 B Tx 境界の責務分離).

``save`` takes an explicit ``empire_id`` argument because :class:`Room`
Aggregate holds no ``empire_id`` attribute — ownership is expressed via
``Empire.rooms: list[RoomRef]``. The calling service always has ``empire_id``
in scope (§確定 R1-H).

``_to_row`` / ``_from_row`` are kept as private methods on the class so both
conversion directions live next to each other and tests don't accidentally
acquire a public conversion API to depend on (empire-repo §確定 C).

``find_by_name`` delegates to ``find_by_id`` once the RoomId is known so the
child-table SELECTs and ``_from_row`` conversion stay single-sourced
(agent §R1-C テンプレート継承, §確定 R1-F).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.room.room import Room
from bakufu.domain.room.value_objects import AgentMembership, PromptKit
from bakufu.domain.value_objects import EmpireId, Role, RoomId
from bakufu.infrastructure.persistence.sqlite.tables.room_members import RoomMemberRow
from bakufu.infrastructure.persistence.sqlite.tables.rooms import RoomRow


class SqliteRoomRepository:
    """SQLite implementation of :class:`RoomRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, room_id: RoomId) -> Room | None:
        """SELECT room + room_members, hydrate via :meth:`_from_row`.

        Returns ``None`` when the rooms row is absent. The room_members
        SELECT uses ``ORDER BY agent_id, role`` (composite key ascending)
        so the hydrated member list is deterministic — empire-repository
        BUG-EMR-001 froze this contract; we apply it from day one here.
        """
        room_stmt = select(RoomRow).where(RoomRow.id == room_id)
        room_row = (await self._session.execute(room_stmt)).scalar_one_or_none()
        if room_row is None:
            return None

        # ORDER BY makes find_by_id deterministic. Without it SQLite returns
        # rows in internal-scan order, which would break ``Room == Room``
        # round-trip equality (the Aggregate compares list-by-list).
        # See empire-repo BUG-EMR-001 — this PR adopts the resolved contract
        # from day one.
        member_stmt = (
            select(RoomMemberRow)
            .where(RoomMemberRow.room_id == room_id)
            .order_by(RoomMemberRow.agent_id, RoomMemberRow.role)
        )
        member_rows = list((await self._session.execute(member_stmt)).scalars().all())

        return self._from_row(room_row, member_rows)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM rooms``.

        Implementation detail: SQLAlchemy's ``func.count()`` issues a
        proper ``SELECT COUNT(*)`` so SQLite returns one scalar row instead
        of streaming every PK back to Python (empire-repo §確定 D 踏襲).
        """
        stmt = select(func.count()).select_from(RoomRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, room: Room, empire_id: EmpireId) -> None:
        """Persist ``room`` via the §確定 R1-B three-step delete-then-insert.

        ``empire_id`` is an explicit argument because :class:`Room` holds no
        ``empire_id`` attribute (§確定 R1-H). The caller is responsible for
        the surrounding ``async with session.begin():`` block; failures inside
        any step propagate untouched so the Unit-of-Work boundary in the
        application service can rollback cleanly.
        """
        room_row, member_rows = self._to_row(room, empire_id)

        # Step 1: rooms UPSERT (id PK, ON CONFLICT update workflow_id + name
        # + description + prompt_kit_prefix_markdown + archived).
        # ``prompt_kit_prefix_markdown`` binds through MaskedText so the
        # masked form lands in DB even on update (§確定 R1-J).
        upsert_stmt = sqlite_insert(RoomRow).values(room_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "workflow_id": upsert_stmt.excluded.workflow_id,
                "name": upsert_stmt.excluded.name,
                "description": upsert_stmt.excluded.description,
                "prompt_kit_prefix_markdown": upsert_stmt.excluded.prompt_kit_prefix_markdown,
                "archived": upsert_stmt.excluded.archived,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 2: room_members DELETE.
        await self._session.execute(delete(RoomMemberRow).where(RoomMemberRow.room_id == room.id))

        # Step 3: room_members bulk INSERT (skip when no members — a newly
        # created room may legitimately have zero members).
        if member_rows:
            await self._session.execute(insert(RoomMemberRow), member_rows)

    async def find_by_name(self, empire_id: EmpireId, name: str) -> Room | None:
        """Hydrate the Room named ``name`` inside ``empire_id`` (§確定 R1-F).

        Two-stage flow: a lightweight ``SELECT id ... LIMIT 1`` locates the
        RoomId via ``INDEX(empire_id, name)``, then delegation to
        :meth:`find_by_id` so the child-table SELECTs and ``_from_row``
        conversion stay single-sourced (agent §R1-C テンプレート継承).
        """
        id_stmt = (
            select(RoomRow.id).where(RoomRow.empire_id == empire_id, RoomRow.name == name).limit(1)
        )
        found_id = (await self._session.execute(id_stmt)).scalar_one_or_none()
        if found_id is None:
            return None
        return await self.find_by_id(found_id)

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------
    def _to_row(
        self,
        room: Room,
        empire_id: EmpireId,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Split ``room`` into ``(room_row, member_rows)``.

        SQLAlchemy ``Row`` objects are avoided so the domain layer never
        gains an accidental dependency on the SQLAlchemy type hierarchy. Each
        returned ``dict`` matches the ``mapped_column`` names verbatim.

        ``empire_id`` is passed explicitly because :class:`Room` holds no
        ``empire_id`` attribute (§確定 R1-H).
        """
        room_row: dict[str, Any] = {
            "id": room.id,
            "empire_id": empire_id,
            "workflow_id": room.workflow_id,
            "name": room.name,
            "description": room.description,
            # MaskedText.process_bind_param will redact secrets from this
            # string before VARCHAR storage — room §確定 G 実適用.
            "prompt_kit_prefix_markdown": room.prompt_kit.prefix_markdown,
            "archived": room.archived,
        }
        member_rows: list[dict[str, Any]] = [
            {
                "room_id": room.id,
                "agent_id": membership.agent_id,
                "role": membership.role.value,
                "joined_at": membership.joined_at,
            }
            for membership in room.members
        ]
        return room_row, member_rows

    def _from_row(
        self,
        room_row: RoomRow,
        member_rows: list[RoomMemberRow],
    ) -> Room:
        """Hydrate a :class:`Room` Aggregate Root from its two row types.

        ``Room.model_validate`` re-runs the post-validator so Repository-side
        hydration goes through the same invariant checks that
        ``RoomService.establish_room()`` does at construction time.

        §確定 R1-J §不可逆性: ``prompt_kit.prefix_markdown`` carries the
        already-masked text from disk. ``PromptKit`` accepts any string within
        the length cap so the masked form constructs cleanly, but the resulting
        Room should not be dispatched to an LLM without
        ``feature/llm-adapter``'s masked-prompt guard.

        ``empire_id`` is **not** restored onto :class:`Room` — the Aggregate
        holds no ``empire_id`` attribute (§確定 R1-H).
        """
        members = [
            AgentMembership(
                agent_id=_to_uuid(row.agent_id),
                role=Role(row.role),
                joined_at=row.joined_at,
            )
            for row in member_rows
        ]
        return Room(
            id=_to_uuid(room_row.id),
            workflow_id=_to_uuid(room_row.workflow_id),
            name=room_row.name,
            description=room_row.description,
            prompt_kit=PromptKit(prefix_markdown=room_row.prompt_kit_prefix_markdown or ""),
            members=members,
            archived=room_row.archived,
        )


def _to_uuid(value: UUID | str) -> UUID:
    """Coerce a row value to :class:`uuid.UUID`.

    UUIDStr TypeDecorator already returns UUID instances on
    ``process_result_value``, but defensive coercion lets raw-SQL hydration
    paths route through the same code without an extra ``isinstance`` ladder
    at every call site (agent_repository pattern).
    """
    if isinstance(value, UUID):
        return value
    return UUID(value)


__all__ = ["SqliteRoomRepository"]
