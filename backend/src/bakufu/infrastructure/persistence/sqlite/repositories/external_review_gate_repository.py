"""SQLite adapter for :class:`bakufu.application.ports.ExternalReviewGateRepository`.

Implements the §確定 R1-B 5-step save flow over three tables
(``external_review_gates`` / ``external_review_gate_attachments`` /
``external_review_audit_entries``):

1. ``DELETE FROM external_review_gate_attachments WHERE gate_id = :id`` —
   no CASCADE parent; direct DELETE. New Gates produce 0 rows (no-op).
2. ``DELETE FROM external_review_audit_entries WHERE gate_id = :id`` —
   same. Direct DELETE, no CASCADE parent.
3. ``external_review_gates`` UPSERT (id-conflict → mutable fields update;
   ``task_id``, ``stage_id``, ``reviewer_id``, ``created_at``, and all
   ``snapshot_*`` columns are intentionally **not** updated — Gate origin,
   reviewer assignment, and deliverable snapshot are immutable after
   creation).
4. ``INSERT INTO external_review_gate_attachments`` — one row per
   :class:`Attachment` in ``gate.deliverable_snapshot.attachments``. A
   fresh ``uuid4()`` PK is generated for each row on every save
   (DELETE-then-INSERT pattern guarantees no PK collision). Business key
   remains ``UNIQUE(gate_id, sha256)``.
5. ``INSERT INTO external_review_audit_entries`` — one row per
   :class:`AuditEntry` in ``gate.audit_trail``. PKs come directly from
   ``AuditEntry.id`` (domain-assigned UUIDs, not regenerated).

The repository **never** calls ``session.commit()`` / ``session.rollback()``:
the caller-side service runs ``async with session.begin():`` so all 5 steps
stay in one transaction (empire-repo §確定 B Tx 境界の責務分離).

``save(gate)`` uses the **standard 1-argument pattern** (§確定 R1-F):
:class:`ExternalReviewGate` carries all own attributes so the Repository
reads them directly.

``_to_rows`` / ``_from_rows`` are kept as private methods on the class so
both conversion directions live next to each other and tests don't
accidentally acquire a public conversion API to depend on (empire-repo
§確定 C).

TypeDecorator-trust pattern (§確定 R1-A): :class:`UUIDStr` returns
``UUID`` instances from ``process_result_value``, so ``row.id`` etc. are
already ``UUID``. Direct attribute access without defensive ``UUID(row.id)``
wrapping is correct and required. :class:`MaskedText` returns the already-
masked string on SELECT; raw domain strings are passed on INSERT and
``process_bind_param`` applies the masking gate automatically.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.external_review_gate.gate import ExternalReviewGate
from bakufu.domain.value_objects import (
    Attachment,
    AuditAction,
    AuditEntry,
    Deliverable,
    GateId,
    OwnerId,
    ReviewDecision,
    TaskId,
)
from bakufu.infrastructure.persistence.sqlite.tables.external_review_audit_entries import (
    ExternalReviewAuditEntryRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.external_review_gate_attachments import (
    ExternalReviewGateAttachmentRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.external_review_gates import (
    ExternalReviewGateRow,
)


class SqliteExternalReviewGateRepository:
    """SQLite implementation of :class:`ExternalReviewGateRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, gate_id: GateId) -> ExternalReviewGate | None:
        """SELECT gate row + 2 child tables, hydrate via :meth:`_from_rows`.

        Returns ``None`` when the gate row is absent. On success, both
        child tables are queried with their §確定 R1-H ORDER BY clauses so
        the hydrated Aggregate is deterministic.
        """
        gate_row = (
            await self._session.execute(
                select(ExternalReviewGateRow).where(ExternalReviewGateRow.id == gate_id)
            )
        ).scalar_one_or_none()
        if gate_row is None:
            return None
        return await self._hydrate_row(gate_row)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM external_review_gates``.

        SQLAlchemy's ``func.count()`` issues a proper ``SELECT COUNT(*)``
        so SQLite returns one scalar row instead of streaming every PK back
        to Python (empire-repo §確定 D 踏襲).
        """
        return (
            await self._session.execute(select(func.count()).select_from(ExternalReviewGateRow))
        ).scalar_one()

    async def save(self, gate: ExternalReviewGate) -> None:
        """Persist ``gate`` via the §確定 R1-B 5-step delete-then-insert.

        The caller is responsible for the surrounding
        ``async with session.begin():`` block; failures propagate untouched
        so the Unit-of-Work boundary in the application service can rollback
        cleanly (empire-repo §確定 B 踏襲).
        """
        gate_row, attach_rows, audit_rows = self._to_rows(gate)

        # Step 1: DELETE external_review_gate_attachments (no CASCADE, direct).
        await self._session.execute(
            delete(ExternalReviewGateAttachmentRow).where(
                ExternalReviewGateAttachmentRow.gate_id == gate.id
            )
        )

        # Step 2: DELETE external_review_audit_entries (no CASCADE, direct).
        await self._session.execute(
            delete(ExternalReviewAuditEntryRow).where(
                ExternalReviewAuditEntryRow.gate_id == gate.id
            )
        )

        # Step 3: external_review_gates UPSERT.
        # Immutable fields excluded from DO UPDATE — Gate origin, reviewer
        # assignment, and deliverable snapshot never change after creation.
        upsert_stmt = sqlite_insert(ExternalReviewGateRow).values(gate_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "decision": upsert_stmt.excluded.decision,
                "feedback_text": upsert_stmt.excluded.feedback_text,
                "decided_at": upsert_stmt.excluded.decided_at,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 4: INSERT external_review_gate_attachments.
        if attach_rows:
            await self._session.execute(insert(ExternalReviewGateAttachmentRow), attach_rows)

        # Step 5: INSERT external_review_audit_entries.
        if audit_rows:
            await self._session.execute(insert(ExternalReviewAuditEntryRow), audit_rows)

    async def find_pending_by_reviewer(self, reviewer_id: OwnerId) -> list[ExternalReviewGate]:
        """Return all PENDING Gates for ``reviewer_id`` ordered ``created_at DESC, id DESC``.

        The composite INDEX ``ix_external_review_gates_reviewer_decision``
        on ``(reviewer_id, decision)`` covers the WHERE filter (§確定 R1-K).
        Returns ``[]`` when no PENDING Gates exist for the given reviewer.
        """
        gate_rows = list(
            (
                await self._session.execute(
                    select(ExternalReviewGateRow)
                    .where(
                        ExternalReviewGateRow.reviewer_id == reviewer_id,
                        ExternalReviewGateRow.decision == ReviewDecision.PENDING.value,
                    )
                    .order_by(
                        ExternalReviewGateRow.created_at.desc(),
                        ExternalReviewGateRow.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not gate_rows:
            return []

        results: list[ExternalReviewGate] = []
        for gate_row in gate_rows:
            gate = await self.find_by_id(gate_row.id)
            if gate is not None:
                results.append(gate)
        return results

    async def find_by_task_id(self, task_id: TaskId) -> list[ExternalReviewGate]:
        """Return all Gates for ``task_id`` ordered ``created_at ASC, id ASC``.

        The composite INDEX ``ix_external_review_gates_task_id_created``
        on ``(task_id, created_at)`` covers the WHERE + ORDER BY in one
        B-tree scan (§確定 R1-K). Returns ``[]`` when no Gates exist for
        the given Task.
        """
        gate_rows = list(
            (
                await self._session.execute(
                    select(ExternalReviewGateRow)
                    .where(ExternalReviewGateRow.task_id == task_id)
                    .order_by(
                        ExternalReviewGateRow.created_at.asc(),
                        ExternalReviewGateRow.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not gate_rows:
            return []

        results: list[ExternalReviewGate] = []
        for gate_row in gate_rows:
            gate = await self.find_by_id(gate_row.id)
            if gate is not None:
                results.append(gate)
        return results

    async def count_by_decision(self, decision: ReviewDecision) -> int:
        """``SELECT COUNT(*) FROM external_review_gates WHERE decision = :decision``.

        The INDEX ``ix_external_review_gates_decision`` on ``(decision)``
        accelerates this WHERE filter (§確定 R1-K).
        Returns 0 when no Gates exist with the given decision.
        """
        return (
            await self._session.execute(
                select(func.count())
                .select_from(ExternalReviewGateRow)
                .where(ExternalReviewGateRow.decision == decision.value)
            )
        ).scalar_one()

    # ---- private domain ↔ row converters (empire-repo §確定 C) -----------

    async def _hydrate_row(self, gate_row: ExternalReviewGateRow) -> ExternalReviewGate:
        """Fetch child tables for an already-loaded gate row and reconstruct.

        Shared by :meth:`find_by_id`, :meth:`find_pending_by_reviewer`, and
        :meth:`find_by_task_id` to avoid redundant root-table re-fetches.
        """
        # §確定 R1-H: ORDER BY sha256 ASC (UNIQUE per gate scope, deterministic).
        attach_rows = list(
            (
                await self._session.execute(
                    select(ExternalReviewGateAttachmentRow)
                    .where(ExternalReviewGateAttachmentRow.gate_id == gate_row.id)
                    .order_by(ExternalReviewGateAttachmentRow.sha256.asc())
                )
            )
            .scalars()
            .all()
        )

        # §確定 R1-H: ORDER BY occurred_at ASC, id ASC (append-only audit trail
        # must reconstruct in temporal order; id breaks timestamp ties).
        audit_rows = list(
            (
                await self._session.execute(
                    select(ExternalReviewAuditEntryRow)
                    .where(ExternalReviewAuditEntryRow.gate_id == gate_row.id)
                    .order_by(
                        ExternalReviewAuditEntryRow.occurred_at.asc(),
                        ExternalReviewAuditEntryRow.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )

        return self._from_rows(gate_row, attach_rows, audit_rows)

    def _to_rows(
        self,
        gate: ExternalReviewGate,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        """Convert ``gate`` to ``(gate_row, attach_rows, audit_rows)``.

        SQLAlchemy ``Row`` objects are avoided so the domain layer never
        gains an accidental dependency on the SQLAlchemy type hierarchy.

        TypeDecorator-trust (§確定 R1-A): raw domain values are passed
        directly; ``UUIDStr`` / ``MaskedText`` / ``UTCDateTime``
        TypeDecorators perform all conversions at bind-parameter time.
        ``feedback_text``, ``snapshot_body_markdown``, and ``comment`` are
        passed as plain strings — ``MaskedText.process_bind_param`` applies
        the masking gate automatically without manual
        ``MaskingGateway.mask()`` calls.

        Attachment PKs: ``external_review_gate_attachments.id`` has no
        domain-level identity (the business key is ``UNIQUE(gate_id, sha256)``).
        A fresh ``uuid4()`` is generated for each attachment row on every
        save. Because step 1 DELETE-then-step 4 INSERT, there is never a PK
        collision.

        Audit entry PKs: ``external_review_audit_entries.id`` is taken
        directly from ``AuditEntry.id`` (domain-assigned UUID). The DELETE-
        then-INSERT flow in steps 2+5 guarantees no PK collision even as the
        trail grows.
        """
        gate_row: dict[str, Any] = {
            "id": gate.id,
            "task_id": gate.task_id,
            "stage_id": gate.stage_id,
            "reviewer_id": gate.reviewer_id,
            "decision": gate.decision.value,
            # MaskedText.process_bind_param redacts secrets at bind time.
            "feedback_text": gate.feedback_text,
            # Inline snapshot copy — immutable after construction (§確定 D).
            "snapshot_stage_id": gate.deliverable_snapshot.stage_id,
            # MaskedText.process_bind_param redacts secrets at bind time.
            "snapshot_body_markdown": gate.deliverable_snapshot.body_markdown,
            "snapshot_committed_by": gate.deliverable_snapshot.committed_by,
            "snapshot_committed_at": gate.deliverable_snapshot.committed_at,
            "created_at": gate.created_at,
            "decided_at": gate.decided_at,
        }

        attach_rows: list[dict[str, Any]] = [
            {
                # Fresh UUID PK — business key is UNIQUE(gate_id, sha256).
                "id": _uuid.uuid4(),
                "gate_id": gate.id,
                "sha256": attachment.sha256,
                "filename": attachment.filename,
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
            }
            for attachment in gate.deliverable_snapshot.attachments
        ]

        audit_rows: list[dict[str, Any]] = [
            {
                # AuditEntry.id is domain-assigned — preserve it verbatim.
                "id": entry.id,
                "gate_id": gate.id,
                "actor_id": entry.actor_id,
                "action": entry.action.value,
                # MaskedText.process_bind_param redacts secrets at bind time.
                "comment": entry.comment,
                "occurred_at": entry.occurred_at,
            }
            for entry in gate.audit_trail
        ]

        return gate_row, attach_rows, audit_rows

    def _from_rows(
        self,
        gate_row: ExternalReviewGateRow,
        attach_rows: list[ExternalReviewGateAttachmentRow],
        audit_rows: list[ExternalReviewAuditEntryRow],
    ) -> ExternalReviewGate:
        """Hydrate an :class:`ExternalReviewGate` from its row types.

        ``ExternalReviewGate(...)`` direct construction re-runs the
        post-validator so Repository-side hydration goes through the same
        invariant checks that ``GateService.create()`` does at construction
        time (empire §確定 C contract: "Repository hydration produces a valid
        Gate or raises").

        TypeDecorator-trust (§確定 R1-A): ``UUIDStr`` returns ``UUID``
        instances from ``process_result_value``; ``UTCDateTime`` returns
        tz-aware ``datetime``; ``MaskedText`` returns the already-masked
        string. No defensive wrapping (e.g. ``UUID(row.id)``) needed.

        §確定 R1-J §不可逆性: ``feedback_text``, ``snapshot_body_markdown``,
        and ``comment`` carry the already-masked text from disk. All fields
        accept any string within their length caps so the masked form
        constructs cleanly.
        """
        # §確定 R1-C: reconstruct deliverable_snapshot from gate_row scalars
        # + attach_rows (attach_rows already sorted sha256 ASC by caller).
        attachments = [
            Attachment(
                sha256=a.sha256,
                filename=a.filename,
                mime_type=a.mime_type,
                size_bytes=a.size_bytes,
            )
            for a in attach_rows
        ]
        deliverable_snapshot = Deliverable(
            stage_id=gate_row.snapshot_stage_id,
            body_markdown=gate_row.snapshot_body_markdown,
            attachments=attachments,
            committed_by=gate_row.snapshot_committed_by,
            committed_at=gate_row.snapshot_committed_at,
        )

        # §確定 R1-C: reconstruct audit_trail from audit_rows (already sorted
        # occurred_at ASC, id ASC by caller — matches append-only domain order).
        # TypeDecorator-trust (§確定 R1-A): UUIDStr.process_result_value
        # already returns UUID instances — no defensive wrapping needed.
        audit_trail: list[AuditEntry] = [
            AuditEntry(
                id=r.id,
                actor_id=r.actor_id,
                action=AuditAction(r.action),
                comment=r.comment,
                occurred_at=r.occurred_at,
            )
            for r in audit_rows
        ]

        return ExternalReviewGate(
            id=gate_row.id,
            task_id=gate_row.task_id,
            stage_id=gate_row.stage_id,
            deliverable_snapshot=deliverable_snapshot,
            reviewer_id=gate_row.reviewer_id,
            decision=ReviewDecision(gate_row.decision),
            feedback_text=gate_row.feedback_text,
            audit_trail=audit_trail,
            created_at=gate_row.created_at,
            decided_at=gate_row.decided_at,
        )


__all__ = ["SqliteExternalReviewGateRepository"]
