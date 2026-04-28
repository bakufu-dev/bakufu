"""SQLite adapter for :class:`bakufu.application.ports.TaskRepository`.

Implements the §確定 R1-B 9-step save flow over six tables
(``tasks`` / ``task_assigned_agents`` / ``conversations`` /
``conversation_messages`` / ``deliverables`` / ``deliverable_attachments``):

1. ``DELETE FROM deliverables WHERE task_id = :id`` — CASCADE removes
   ``deliverable_attachments`` automatically.
2. ``DELETE FROM conversations WHERE task_id = :id`` — CASCADE removes
   ``conversation_messages`` automatically.
3. ``DELETE FROM task_assigned_agents WHERE task_id = :id`` — no CASCADE,
   direct DELETE.
4. ``tasks`` UPSERT (id-conflict → ``current_stage_id`` + ``status`` +
   ``last_error`` + ``updated_at`` update; ``room_id``, ``directive_id``,
   and ``created_at`` are intentionally **not** updated — Task ownership
   and origin never change after creation).
5. ``INSERT INTO task_assigned_agents`` — one row per AgentId with
   ``order_index`` = list position (0-indexed).
6. ``INSERT INTO conversations`` — per Conversation in ``task.conversations``
   (currently empty: Task domain model has no ``conversations`` attribute).
7. ``INSERT INTO conversation_messages`` — per Message per Conversation
   (currently empty, same reason).
8. ``INSERT INTO deliverables`` — one row per Deliverable in
   ``task.deliverables.values()``. A fresh ``uuid4()`` PK is generated for
   each row on every save (DELETE-then-INSERT pattern guarantees no PK
   collision).
9. ``INSERT INTO deliverable_attachments`` — one row per Attachment per
   Deliverable, linked via the ``deliverable_id`` FK generated in step 8.

The repository **never** calls ``session.commit()`` / ``session.rollback()``:
the caller-side service runs ``async with session.begin():`` so all 9 steps
stay in one transaction (empire-repo §確定 B Tx 境界の責務分離).

``save(task)`` uses the **standard 1-argument pattern** (§確定 R1-F):
:class:`Task` carries ``room_id`` and ``directive_id`` as own attributes,
so the Repository reads them directly.

``_to_rows`` / ``_from_rows`` are kept as private methods on the class so
both conversion directions live next to each other and tests don't
accidentally acquire a public conversion API to depend on (empire-repo
§確定 C).

TypeDecorator-trust pattern (PR #48 v2 確立): :class:`UUIDStr` returns
``UUID`` instances from ``process_result_value``, so ``row.id`` etc. are
already ``UUID``. Direct attribute access without defensive ``UUID(row.id)``
wrapping is correct and required (§確定 R1-A).
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.task.task import Task
from bakufu.domain.value_objects import (
    Attachment,
    Deliverable,
    RoomId,
    StageId,
    TaskId,
    TaskStatus,
)
from bakufu.infrastructure.persistence.sqlite.tables.conversation_messages import (
    ConversationMessageRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.conversations import (
    ConversationRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.deliverable_attachments import (
    DeliverableAttachmentRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.deliverables import DeliverableRow
from bakufu.infrastructure.persistence.sqlite.tables.task_assigned_agents import (
    TaskAssignedAgentRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.tasks import TaskRow


class SqliteTaskRepository:
    """SQLite implementation of :class:`TaskRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, task_id: TaskId) -> Task | None:
        """SELECT tasks row + 5 child tables, hydrate via :meth:`_from_rows`.

        Returns ``None`` when the tasks row is absent. On success, all five
        child tables are queried with their §確定 R1-H ORDER BY clauses so
        the hydrated Aggregate is deterministic.
        """
        task_row = (
            await self._session.execute(select(TaskRow).where(TaskRow.id == task_id))
        ).scalar_one_or_none()
        if task_row is None:
            return None

        # §確定 R1-H: ORDER BY order_index ASC preserves assigned-agent list
        # order from the Aggregate's ``assigned_agent_ids``.
        agent_rows = list(
            (
                await self._session.execute(
                    select(TaskAssignedAgentRow)
                    .where(TaskAssignedAgentRow.task_id == task_id)
                    .order_by(TaskAssignedAgentRow.order_index.asc())
                )
            )
            .scalars()
            .all()
        )

        # conversations / conversation_messages: schema exists for future use;
        # Task domain model currently has no ``conversations`` attribute.
        conv_rows: list[Any] = []
        msg_rows: list[Any] = []

        # §確定 R1-H: ORDER BY stage_id ASC (UNIQUE per task, deterministic).
        deliv_rows = list(
            (
                await self._session.execute(
                    select(DeliverableRow)
                    .where(DeliverableRow.task_id == task_id)
                    .order_by(DeliverableRow.stage_id.asc())
                )
            )
            .scalars()
            .all()
        )

        # §確定 R1-H: fetch all attachments in one query, group by deliverable_id.
        # ORDER BY sha256 ASC (UNIQUE per deliverable scope, deterministic).
        attach_rows_by_deliv: dict[UUID, list[DeliverableAttachmentRow]] = {}
        if deliv_rows:
            deliv_ids = [r.id for r in deliv_rows]
            for row in (
                await self._session.execute(
                    select(DeliverableAttachmentRow)
                    .where(DeliverableAttachmentRow.deliverable_id.in_(deliv_ids))
                    .order_by(DeliverableAttachmentRow.sha256.asc())
                )
            ).scalars():
                attach_rows_by_deliv.setdefault(row.deliverable_id, []).append(row)

        return self._from_rows(
            task_row, agent_rows, conv_rows, msg_rows, deliv_rows, attach_rows_by_deliv
        )

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM tasks``.

        SQLAlchemy's ``func.count()`` issues a proper ``SELECT COUNT(*)``
        so SQLite returns one scalar row instead of streaming every PK back
        to Python (empire-repo §確定 D 踏襲).
        """
        return (await self._session.execute(select(func.count()).select_from(TaskRow))).scalar_one()

    async def save(self, task: Task) -> None:
        """Persist ``task`` via the §確定 R1-B 9-step delete-then-insert.

        The caller is responsible for the surrounding
        ``async with session.begin():`` block; failures propagate untouched
        so the Unit-of-Work boundary in the application service can rollback
        cleanly (empire-repo §確定 B 踏襲).
        """
        task_row, agent_rows, conv_rows, msg_rows, deliv_rows, attach_rows = self._to_rows(task)

        # Step 1: DELETE deliverables — CASCADE removes deliverable_attachments.
        await self._session.execute(delete(DeliverableRow).where(DeliverableRow.task_id == task.id))

        # Step 2: DELETE conversations — CASCADE removes conversation_messages.
        # Currently a no-op (Task has no conversations), but executed to maintain
        # the §確定 R1-B ordering contract and clean any future-loaded rows.
        await self._session.execute(
            delete(ConversationRow).where(ConversationRow.task_id == task.id)
        )

        # Step 3: DELETE task_assigned_agents (no CASCADE, direct DELETE).
        await self._session.execute(
            delete(TaskAssignedAgentRow).where(TaskAssignedAgentRow.task_id == task.id)
        )

        # Step 4: tasks UPSERT.
        # room_id / directive_id / created_at are excluded from DO UPDATE —
        # Task ownership and origin are immutable after creation.
        upsert_stmt = sqlite_insert(TaskRow).values(task_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "current_stage_id": upsert_stmt.excluded.current_stage_id,
                "status": upsert_stmt.excluded.status,
                "last_error": upsert_stmt.excluded.last_error,
                "updated_at": upsert_stmt.excluded.updated_at,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 5: INSERT task_assigned_agents.
        if agent_rows:
            await self._session.execute(insert(TaskAssignedAgentRow), agent_rows)

        # Steps 6-7: INSERT conversations + conversation_messages.
        # Currently empty: Task domain model has no ``conversations`` attribute.
        # The branch executes once the Conversation domain type is added and
        # _to_rows() starts returning non-empty conv_rows / msg_rows.
        if conv_rows:
            await self._session.execute(insert(ConversationRow), conv_rows)
            if msg_rows:
                await self._session.execute(insert(ConversationMessageRow), msg_rows)

        # Step 8: INSERT deliverables.
        if deliv_rows:
            await self._session.execute(insert(DeliverableRow), deliv_rows)

        # Step 9: INSERT deliverable_attachments.
        if attach_rows:
            await self._session.execute(insert(DeliverableAttachmentRow), attach_rows)

    async def count_by_status(self, status: TaskStatus) -> int:
        """``SELECT COUNT(*) FROM tasks WHERE status = :status``.

        The composite INDEX ``ix_tasks_status_updated_id`` prefix on
        ``(status)`` accelerates this WHERE filter (§確定 R1-K).
        Returns 0 when no Tasks exist with the given status.
        """
        return (
            await self._session.execute(
                select(func.count()).select_from(TaskRow).where(TaskRow.status == status.value)
            )
        ).scalar_one()

    async def count_by_room(self, room_id: RoomId) -> int:
        """``SELECT COUNT(*) FROM tasks WHERE room_id = :room_id``.

        The INDEX ``ix_tasks_room_id`` accelerates this WHERE filter
        (§確定 R1-K). Returns 0 when no Tasks exist for the given Room.
        """
        return (
            await self._session.execute(
                select(func.count()).select_from(TaskRow).where(TaskRow.room_id == room_id)
            )
        ).scalar_one()

    async def find_blocked(self) -> list[Task]:
        """Return all BLOCKED Tasks ordered by ``updated_at DESC, id DESC``.

        The composite INDEX ``ix_tasks_status_updated_id`` on
        ``(status, updated_at, id)`` covers both the WHERE filter and the
        ORDER BY in a single B-tree scan (§確定 R1-K). For each BLOCKED
        TaskRow, child tables are fetched individually — the same pattern
        as :meth:`find_by_id`.

        Returns ``[]`` when no BLOCKED Tasks exist.
        """
        task_rows = list(
            (
                await self._session.execute(
                    select(TaskRow)
                    .where(TaskRow.status == TaskStatus.BLOCKED.value)
                    .order_by(TaskRow.updated_at.desc(), TaskRow.id.desc())
                )
            )
            .scalars()
            .all()
        )
        if not task_rows:
            return []

        results: list[Task] = []
        for task_row in task_rows:
            task = await self.find_by_id(task_row.id)
            if task is not None:
                results.append(task)
        return results

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------

    def _to_rows(
        self,
        task: Task,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        """Convert ``task`` to ``(task_row, agent_rows, conv_rows, msg_rows,
        deliv_rows, attach_rows)``.

        SQLAlchemy ``Row`` objects are avoided so the domain layer never
        gains an accidental dependency on the SQLAlchemy type hierarchy.

        TypeDecorator-trust (§確定 R1-A): raw domain values are passed
        directly; ``UUIDStr`` / ``MaskedText`` / ``UTCDateTime``
        TypeDecorators perform all conversions at bind-parameter time.
        ``last_error`` and ``body_markdown`` are passed as plain strings —
        ``MaskedText.process_bind_param`` applies the masking gate
        automatically without manual ``MaskingGateway.mask()`` calls.

        Deliverable PKs: ``deliverables.id`` has no domain-level identity
        (the Aggregate identifies Deliverables by ``stage_id``). A fresh
        ``uuid4()`` is generated for each deliverable row on every save.
        Because steps 1→8 are DELETE-then-INSERT, there is never a PK
        collision. The same fresh UUID is used as ``deliverable_id`` in the
        corresponding attachment rows built in the same call.

        ``conv_rows`` / ``msg_rows`` are always ``[]``: the Task domain model
        has no ``conversations`` attribute yet (§確定 R1-J future wiring).
        """
        task_row: dict[str, Any] = {
            "id": task.id,
            "room_id": task.room_id,
            "directive_id": task.directive_id,
            "current_stage_id": task.current_stage_id,
            "status": task.status.value,
            # MaskedText.process_bind_param redacts secrets at bind time.
            "last_error": task.last_error,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

        agent_rows: list[dict[str, Any]] = [
            {
                "task_id": task.id,
                "agent_id": agent_id,
                "order_index": idx,
            }
            for idx, agent_id in enumerate(task.assigned_agent_ids)
        ]

        # conversations / messages: empty until Task gains a ``conversations``
        # attribute (§確定 R1-J future wiring point).
        conv_rows: list[dict[str, Any]] = []
        msg_rows: list[dict[str, Any]] = []

        deliv_rows: list[dict[str, Any]] = []
        attach_rows: list[dict[str, Any]] = []

        for deliverable in task.deliverables.values():
            # Fresh UUID for this deliverable's PK.  The same UUID is
            # used below as ``deliverable_id`` in all attachment rows for
            # this deliverable — linking them within this save() call.
            deliv_pk = _uuid.uuid4()
            deliv_rows.append(
                {
                    "id": deliv_pk,
                    "task_id": task.id,
                    "stage_id": deliverable.stage_id,
                    # MaskedText.process_bind_param redacts secrets at bind time.
                    "body_markdown": deliverable.body_markdown,
                    "committed_by": deliverable.committed_by,
                    "committed_at": deliverable.committed_at,
                }
            )
            for attachment in deliverable.attachments:
                attach_rows.append(
                    {
                        "id": _uuid.uuid4(),
                        "deliverable_id": deliv_pk,
                        "sha256": attachment.sha256,
                        "filename": attachment.filename,
                        "mime_type": attachment.mime_type,
                        "size_bytes": attachment.size_bytes,
                    }
                )

        return task_row, agent_rows, conv_rows, msg_rows, deliv_rows, attach_rows

    def _from_rows(
        self,
        task_row: TaskRow,
        agent_rows: list[TaskAssignedAgentRow],
        conv_rows: list[Any],
        msg_rows: list[Any],
        deliv_rows: list[DeliverableRow],
        attach_rows_by_deliv: dict[UUID, list[DeliverableAttachmentRow]],
    ) -> Task:
        """Hydrate a :class:`Task` Aggregate Root from its row types.

        ``Task.model_validate`` / direct construction re-runs the
        post-validator so Repository-side hydration goes through the same
        invariant checks that ``TaskService.create()`` does at construction
        time (empire §確定 C contract: "Repository hydration produces a valid
        Task or raises").

        TypeDecorator-trust (§確定 R1-A): ``UUIDStr`` returns ``UUID``
        instances from ``process_result_value``; ``UTCDateTime`` returns
        tz-aware ``datetime``; ``MaskedText`` returns the already-masked
        string. No defensive wrapping (e.g. ``UUID(row.id)``) needed.

        ``conv_rows`` / ``msg_rows`` are accepted for forward-API
        compatibility (§確定 R1-J) but are not used because :class:`Task`
        has no ``conversations`` field yet.

        §確定 R1-J §不可逆性: ``last_error`` and deliverable
        ``body_markdown`` carry the already-masked text from disk. Both
        fields accept any string within the length cap so the masked form
        constructs cleanly; LLM-facing dispatch must apply its own
        masked-prompt guard (``feature/llm-adapter`` scope).
        """
        del conv_rows, msg_rows  # not used until Task gains conversations

        # §確定 R1-H: agent_rows already sorted order_index ASC by the caller.
        assigned_agent_ids = [row.agent_id for row in agent_rows]

        # §確定 R1-J: reconstruct deliverables dict keyed by StageId.
        # deliv_rows already sorted stage_id ASC by the caller.
        deliverables: dict[StageId, Deliverable] = {}
        for deliv_row in deliv_rows:
            stage_id: StageId = deliv_row.stage_id
            attachments = [
                Attachment(
                    sha256=att.sha256,
                    filename=att.filename,
                    mime_type=att.mime_type,
                    size_bytes=att.size_bytes,
                )
                for att in attach_rows_by_deliv.get(deliv_row.id, [])
            ]
            deliverables[stage_id] = Deliverable(
                stage_id=deliv_row.stage_id,
                body_markdown=deliv_row.body_markdown,
                attachments=attachments,
                committed_by=deliv_row.committed_by,
                committed_at=deliv_row.committed_at,
            )

        return Task(
            id=task_row.id,
            room_id=task_row.room_id,
            directive_id=task_row.directive_id,
            current_stage_id=task_row.current_stage_id,
            status=TaskStatus(task_row.status),
            last_error=task_row.last_error,
            assigned_agent_ids=assigned_agent_ids,
            deliverables=deliverables,
            created_at=task_row.created_at,
            updated_at=task_row.updated_at,
        )


__all__ = ["SqliteTaskRepository"]
