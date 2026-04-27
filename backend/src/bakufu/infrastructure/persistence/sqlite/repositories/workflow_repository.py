"""SQLite adapter for :class:`bakufu.application.ports.WorkflowRepository`.

Implements the §確定 B "delete-then-insert" save flow over three
tables (``workflows`` / ``workflow_stages`` / ``workflow_transitions``):

1. ``workflows`` UPSERT (id-conflict → name + entry_stage_id update)
2. ``workflow_stages`` DELETE WHERE workflow_id = ?
3. ``workflow_stages`` bulk INSERT (one row per Stage; ``notify_channels_json``
   binds through :class:`MaskedJSONEncoded` so Discord webhook tokens are
   redacted *before* the JSON hits disk — Schneier 申し送り #6 multilayer
   defense, applied to the Workflow path here).
4. ``workflow_transitions`` DELETE WHERE workflow_id = ?
5. ``workflow_transitions`` bulk INSERT (one row per Transition).

The repository **never** calls ``session.commit()`` /
``session.rollback()``: the caller-side service runs
``async with session.begin():`` so the five steps above stay in one
transaction (§確定 B Tx 境界の責務分離). Same Unit-of-Work pattern as
:class:`SqliteEmpireRepository`.

``_to_row`` / ``_from_row`` are kept as private methods on the class
so both directions live next to each other and tests don't accidentally
acquire a public conversion API to depend on (§確定 C). The two
helpers also encapsulate the four format choices frozen in §確定 G〜J:

* ``roles_csv`` — sorted-CSV serialization of ``frozenset[Role]``
  (§確定 G). Sorting is **mandatory** so frozenset's
  implementation-dependent iteration order does not produce
  delete-then-insert diff noise across runs.
* ``notify_channels_json`` — :class:`MaskedJSONEncoded` (§確定 H). The
  underlying TypeDecorator does the masking; ``_to_row`` only feeds
  it ``list[dict]`` produced by ``NotifyChannel.model_dump(mode='json')``
  (which itself masks through the VO's ``when_used='json'`` serializer
  — defense-in-depth).
* ``completion_policy_json`` — plain :class:`JSONEncoded` (§確定 I).
  CompletionPolicy carries no Schneier #6 secret category, so
  ``MaskedJSONEncoded`` would be over-masking; the CI Layer 2 arch
  test pins the un-masked TypeDecorator.
* ``workflows.entry_stage_id`` — no DB-level FK (§確定 J); Aggregate
  invariant ``_validate_entry_in_stages`` guards it.

``_from_row`` runs ``Workflow.model_validate(...)`` so the same
invariants the application layer enforces at construction time fire
on rehydration too. ``find_by_id`` may therefore raise
``pydantic.ValidationError`` when a saved Workflow contained
``EXTERNAL_REVIEW`` stages whose notify URLs were masked at save time
(§確定 H §不可逆性): the application layer catches and surfaces a
"webhook re-registration required" error to the operator.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.domain.value_objects import (
    CompletionPolicy,
    NotifyChannel,
    Role,
    StageKind,
    TransitionCondition,
    WorkflowId,
)
from bakufu.domain.workflow import Stage, Transition, Workflow
from bakufu.infrastructure.persistence.sqlite.tables.workflow_stages import (
    WorkflowStageRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflow_transitions import (
    WorkflowTransitionRow,
)
from bakufu.infrastructure.persistence.sqlite.tables.workflows import WorkflowRow


class SqliteWorkflowRepository:
    """SQLite implementation of :class:`WorkflowRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, workflow_id: WorkflowId) -> Workflow | None:
        """SELECT workflow + side tables, hydrate via :meth:`_from_row`.

        Returns ``None`` when the workflows row is absent. Side-table
        SELECTs use ``ORDER BY stage_id`` / ``ORDER BY transition_id``
        so the hydrated lists are deterministic — empire-repository
        BUG-EMR-001 froze this contract; we apply it from PR #1 here.
        """
        workflow_stmt = select(WorkflowRow).where(WorkflowRow.id == workflow_id)
        workflow_row = (await self._session.execute(workflow_stmt)).scalar_one_or_none()
        if workflow_row is None:
            return None

        # ORDER BY makes find_by_id deterministic. Without it SQLite
        # returns rows in internal-scan order, which would break
        # ``Workflow == Workflow`` round-trip equality (the Aggregate
        # compares list-by-list). See basic-design §ユースケース 2 +
        # docs/features/empire-repository/detailed-design.md §Known
        # Issues §BUG-EMR-001 — this PR adopts the resolved contract
        # from day one.
        stage_stmt = (
            select(WorkflowStageRow)
            .where(WorkflowStageRow.workflow_id == workflow_id)
            .order_by(WorkflowStageRow.stage_id)
        )
        stage_rows = list((await self._session.execute(stage_stmt)).scalars().all())

        transition_stmt = (
            select(WorkflowTransitionRow)
            .where(WorkflowTransitionRow.workflow_id == workflow_id)
            .order_by(WorkflowTransitionRow.transition_id)
        )
        transition_rows = list((await self._session.execute(transition_stmt)).scalars().all())

        return self._from_row(workflow_row, stage_rows, transition_rows)

    async def count(self) -> int:
        """``SELECT COUNT(*) FROM workflows``.

        Implementation detail: SQLAlchemy's ``func.count()`` issues a
        proper ``SELECT COUNT(*)`` so SQLite returns one scalar row
        instead of streaming every PK back to Python. This is the
        empire-repository §確定 D 補強 contract continued — Stage /
        Transition / Workflow tables can hold hundreds of rows
        once preset libraries land, so the pattern matters.
        """
        stmt = select(func.count()).select_from(WorkflowRow)
        return (await self._session.execute(stmt)).scalar_one()

    async def save(self, workflow: Workflow) -> None:
        """Persist ``workflow`` via the §確定 B five-step delete-then-insert.

        The caller is responsible for the surrounding
        ``async with session.begin():`` block; failures inside any
        step propagate untouched so the Unit-of-Work boundary in the
        application service can rollback cleanly.
        """
        workflow_row, stage_rows, transition_rows = self._to_row(workflow)

        # Step 1: workflows UPSERT (id PK, ON CONFLICT update name +
        # entry_stage_id). entry_stage_id can change when the
        # operator inserts a new entry stage at the head of the DAG.
        upsert_stmt = sqlite_insert(WorkflowRow).values(workflow_row)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": upsert_stmt.excluded.name,
                "entry_stage_id": upsert_stmt.excluded.entry_stage_id,
            },
        )
        await self._session.execute(upsert_stmt)

        # Step 2: workflow_stages DELETE.
        await self._session.execute(
            delete(WorkflowStageRow).where(WorkflowStageRow.workflow_id == workflow.id)
        )

        # Step 3: workflow_stages bulk INSERT (skip when no stages —
        # though Workflow's capacity validator forbids zero-length
        # stages, defensive empty-skip keeps the behavior consistent
        # with the Empire template).
        if stage_rows:
            await self._session.execute(insert(WorkflowStageRow), stage_rows)

        # Step 4: workflow_transitions DELETE.
        await self._session.execute(
            delete(WorkflowTransitionRow).where(WorkflowTransitionRow.workflow_id == workflow.id)
        )

        # Step 5: workflow_transitions bulk INSERT (skip when no
        # transitions — a single-stage Workflow is valid).
        if transition_rows:
            await self._session.execute(insert(WorkflowTransitionRow), transition_rows)

    # ---- private domain ↔ row converters (§確定 C) -------------------
    def _to_row(
        self,
        workflow: Workflow,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        """Split ``workflow`` into ``(workflow_row, stage_rows, transition_rows)``.

        SQLAlchemy ``Row`` objects are intentionally avoided here so
        the domain layer never gains an accidental dependency on the
        SQLAlchemy type hierarchy. Each returned ``dict`` matches the
        ``mapped_column`` names of the corresponding table verbatim.
        """
        workflow_row: dict[str, Any] = {
            "id": workflow.id,
            "name": workflow.name,
            "entry_stage_id": workflow.entry_stage_id,
        }
        stage_rows: list[dict[str, Any]] = [
            {
                "workflow_id": workflow.id,
                "stage_id": stage.id,
                "name": stage.name,
                "kind": stage.kind.value,
                # §確定 G: sorted CSV. ``sorted(..., key=str)`` keeps
                # the byte-equality contract no matter how Python
                # frozenset chooses to iterate.
                "roles_csv": ",".join(sorted(role.value for role in stage.required_role)),
                "deliverable_template": stage.deliverable_template,
                # §確定 I: plain JSONEncoded. ``model_dump(mode='json')``
                # returns ``{'kind': ..., 'description': ...}``.
                "completion_policy_json": stage.completion_policy.model_dump(mode="json"),
                # §確定 H: list[dict] with masked targets. The column
                # type :class:`MaskedJSONEncoded` re-runs ``mask_in``
                # on the bound value so even a hypothetical raw URL
                # leaking past ``when_used='json'`` would be redacted
                # by the gateway before ``json.dumps`` (BUG-PF-001
                # twin defense).
                "notify_channels_json": [
                    channel.model_dump(mode="json") for channel in stage.notify_channels
                ],
            }
            for stage in workflow.stages
        ]
        transition_rows: list[dict[str, Any]] = [
            {
                "workflow_id": workflow.id,
                "transition_id": transition.id,
                "from_stage_id": transition.from_stage_id,
                "to_stage_id": transition.to_stage_id,
                "condition": transition.condition.value,
                "label": transition.label,
            }
            for transition in workflow.transitions
        ]
        return workflow_row, stage_rows, transition_rows

    def _from_row(
        self,
        workflow_row: WorkflowRow,
        stage_rows: list[WorkflowStageRow],
        transition_rows: list[WorkflowTransitionRow],
    ) -> Workflow:
        """Hydrate a :class:`Workflow` Aggregate Root from its three rows.

        ``Workflow.model_validate`` re-runs the post-validator so
        Repository-side hydration goes through the same invariant
        checks the application service runs at construction time
        (Empire §確定 C). Hydration of a Workflow whose
        ``EXTERNAL_REVIEW`` stages had notify channels will raise
        ``pydantic.ValidationError`` because the persisted target was
        masked — that is the design contract per §確定 H §不可逆性.
        """
        stages = [self._stage_from_row(row) for row in stage_rows]
        transitions = [self._transition_from_row(row) for row in transition_rows]
        return Workflow(
            id=_uuid(workflow_row.id),
            name=workflow_row.name,
            stages=stages,
            transitions=transitions,
            entry_stage_id=_uuid(workflow_row.entry_stage_id),
        )

    @staticmethod
    def _stage_from_row(row: WorkflowStageRow) -> Stage:
        """Hydrate one ``Stage`` from its persisted row."""
        # §確定 G: split CSV → set comprehension → frozenset. An empty
        # ``required_role`` is impossible because the storage column
        # is NOT NULL and Workflow capacity invariants reject it on
        # save. If a malformed row sneaks past, ``Role(s)`` raises
        # ``ValueError`` and the Aggregate's StageInvariantViolation
        # path takes over downstream (Fail-Fast).
        roles = frozenset(Role(token) for token in row.roles_csv.split(","))
        completion_policy = CompletionPolicy.model_validate(row.completion_policy_json)
        # §確定 H §不可逆性: NotifyChannel.model_validate may raise
        # because the persisted ``target`` field was masked at save
        # time. The exception escapes find_by_id deliberately.
        notify_payloads = cast(
            "list[dict[str, Any]]",
            row.notify_channels_json or [],
        )
        notify_channels = [NotifyChannel.model_validate(payload) for payload in notify_payloads]
        return Stage(
            id=_uuid(row.stage_id),
            name=row.name,
            kind=StageKind(row.kind),
            required_role=roles,
            deliverable_template=row.deliverable_template,
            completion_policy=completion_policy,
            notify_channels=notify_channels,
        )

    @staticmethod
    def _transition_from_row(row: WorkflowTransitionRow) -> Transition:
        """Hydrate one ``Transition`` from its persisted row."""
        return Transition(
            id=_uuid(row.transition_id),
            from_stage_id=_uuid(row.from_stage_id),
            to_stage_id=_uuid(row.to_stage_id),
            condition=TransitionCondition(row.condition),
            label=row.label,
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


__all__ = ["SqliteWorkflowRepository"]
