"""SQLite adapter for :class:`bakufu.application.ports.DirectiveRepository`.

Implements the §確定 R1-B single-table UPSERT save flow over one table
(``directives``):

1. ``directives`` UPSERT (id-conflict → ``text`` + ``created_at`` +
   ``task_id`` update; **``target_room_id`` is NOT updated** — ownership
   of a Directive never changes after creation, §確定 R1-B);
   ``text`` binds through :class:`MaskedText` so any embedded API key /
   OAuth token / Discord webhook secret is redacted *before* it hits
   SQLite — §確定 R1-E, §確定 R1-G 不可逆性凍結).

Directive is a flat aggregate with **no child tables**, so the
empire-repository delete-then-insert pattern reduces to a single UPSERT
step with no DELETE step (§確定 R1-B 子テーブルなし版).

The repository **never** calls ``session.commit()`` / ``session.rollback()``:
the caller-side service runs ``async with session.begin():`` so the UPSERT
stays in one transaction (empire-repo §確定 B Tx 境界の責務分離).

``save(directive)`` uses the **standard 1-argument pattern** (§確定 R1-F):
:class:`Directive` carries ``target_room_id`` as its own attribute, so the
Repository reads it directly — the non-symmetric Room pattern is not needed.

``_to_row`` / ``_from_row`` are kept as private methods on the class so both
conversion directions live next to each other and tests don't accidentally
acquire a public conversion API to depend on (empire-repo §確定 C).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.directive.directive import Directive
from bakufu.domain.value_objects import DirectiveId, RoomId
from bakufu.infrastructure.persistence.sqlite.tables.directives import DirectiveRow


class SqliteDirectiveRepository:
    """SQLite implementation of :class:`DirectiveRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, directive_id: DirectiveId) -> Directive | None:
        """SELECT directive row, hydrate via :meth:`_from_row`.

        Returns ``None`` when the directives row is absent. Directive is a
        flat aggregate — no child-table SELECTs needed.
        """
        stmt = select(DirectiveRow).where(DirectiveRow.id == directive_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return self._from_row(row)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM directives``.

        Implementation detail: SQLAlchemy's ``func.count()`` issues a proper
        ``SELECT COUNT(*)`` so SQLite returns one scalar row instead of
        streaming every PK back to Python (empire-repo §確定 D 踏襲).
        """
        stmt = select(func.count()).select_from(DirectiveRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, directive: Directive) -> None:
        """Persist ``directive`` via the §確定 R1-B single-table UPSERT.

        ON CONFLICT (id) DO UPDATE sets ``text``, ``created_at``, and
        ``task_id``. ``target_room_id`` is intentionally **not** updated —
        a Directive's ownership (target room) never changes after creation.

        ``text`` binds through :class:`MaskedText` so the masked form lands
        in the DB even on UPDATE (§確定 R1-E / R1-G).

        The caller is responsible for the surrounding
        ``async with session.begin():`` block; failures propagate untouched
        so the Unit-of-Work boundary in the application service can rollback
        cleanly (empire-repo §確定 B 踏襲).
        """
        row = self._to_row(directive)

        # Single-step UPSERT: directives has no child tables (§確定 R1-B).
        # target_room_id is excluded from the ON CONFLICT update set because
        # ownership is immutable — a Directive always targets the same Room.
        upsert_stmt = sqlite_insert(DirectiveRow).values(row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "text": upsert_stmt.excluded.text,
                "created_at": upsert_stmt.excluded.created_at,
                "task_id": upsert_stmt.excluded.task_id,
            },
        )
        await self._session.execute(upsert_stmt)

    async def find_by_room(self, room_id: RoomId) -> list[Directive]:
        """Return all Directives targeting ``room_id``, newest first.

        ORDER BY ``created_at DESC, id DESC`` (BUG-EMR-001 規約: composite
        key for deterministic ordering). ``created_at`` alone is insufficient
        when multiple Directives share the same timestamp; ``id`` (PK, UUID)
        is the tiebreaker that makes the result fully deterministic (§確定 R1-D).

        Returns ``[]`` when no Directives exist for the Room.
        """
        stmt = (
            select(DirectiveRow)
            .where(DirectiveRow.target_room_id == room_id)
            .order_by(DirectiveRow.created_at.desc(), DirectiveRow.id.desc())
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [self._from_row(row) for row in rows]

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------
    def _to_row(self, directive: Directive) -> dict[str, Any]:
        """Convert ``directive`` to a ``directives`` table row dict.

        SQLAlchemy ``Row`` objects are avoided so the domain layer never
        gains an accidental dependency on the SQLAlchemy type hierarchy. The
        returned dict matches the ``mapped_column`` names verbatim.

        ``text`` is passed as the raw string — :class:`MaskedText`
        ``process_bind_param`` applies the masking gate automatically when
        SQLAlchemy resolves the bind parameter (§確定 R1-E 物理保証).
        """
        return {
            "id": directive.id,
            "text": directive.text,
            "target_room_id": directive.target_room_id,
            "created_at": directive.created_at,
            "task_id": directive.task_id,
        }

    def _from_row(self, row: DirectiveRow) -> Directive:
        """Hydrate a :class:`Directive` Aggregate Root from its row.

        ``Directive.model_validate`` re-runs the post-validator so
        Repository-side hydration goes through the same invariant checks
        that ``DirectiveService.issue()`` does at construction time. The
        contract (empire §確定 C) is "Repository hydration produces a valid
        Directive or raises".

        TypeDecorator-trust pattern (PR #48 v2 確立): :class:`UUIDStr`
        returns ``UUID`` instances from ``process_result_value``, so
        ``row.id`` / ``row.target_room_id`` / ``row.task_id`` are already
        ``UUID`` (or ``None``). Direct attribute access without defensive
        ``UUID(row.id)`` wrapping is correct and required (§確定 R1-G).

        §確定 R1-G §不可逆性: ``text`` carries the already-masked text from
        disk. ``Directive`` accepts any string within the length cap so the
        masked form constructs cleanly, but the resulting Directive should not
        be dispatched to an LLM without ``feature/llm-adapter``'s
        masked-prompt guard.
        """
        return Directive(
            id=row.id,
            text=row.text,
            target_room_id=row.target_room_id,
            created_at=row.created_at,
            task_id=row.task_id,
        )


__all__ = ["SqliteDirectiveRepository"]
