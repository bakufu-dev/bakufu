"""Task Aggregate Root (REQ-TS-001〜009).

Implements ``docs/features/task/`` as the M1 6th sibling. The aggregate
follows the same shape established by empire / workflow / agent / room /
directive but adds two structural elements unique to the lifecycle-driven
nature of a Task:

* a **decision-table state machine** in
  :mod:`bakufu.domain.task.state_machine`, locked by
  ``Final[Mapping]`` + :class:`types.MappingProxyType` per §確定 B; and
* **ten dedicated behavior methods** whose names map 1:1 to the action
  names in the state-machine table per §確定 A-2 (Steve R2 凍結) — no
  internal dispatch, no ``advance(..., gate_decision=...)`` argument
  shape. ``method x current_status -> action`` is statically determined
  by the method definition itself.

Design contracts (do not break without re-running design review):

* **Pre-validate rebuild (§確定 A)** — every behavior calls
  :meth:`_rebuild_with_state` which goes through ``model_dump`` /
  ``swap`` / ``model_validate``. ``model_copy(update=...)`` is
  intentionally avoided: Pydantic v2 defaults that path to
  ``validate=False`` and would silently bypass the model validator.
* **Terminal Fail-Fast (§確定 R1-B)** — DONE / CANCELLED Tasks are
  immutable. Every method enters through :meth:`_assert_not_terminal`
  before touching the state machine.
* **State-machine bypass Fail-Fast (§確定 R1-A)** — illegal
  ``(status, action)`` pairs raise
  ``TaskInvariantViolation(kind='state_transition_invalid')`` with
  the legal-action set attached in ``detail`` so MSG-TS-002 lands
  with the "next action" hint already populated.
* **Webhook auto-mask (§確定 I)** — :class:`TaskInvariantViolation`
  applies ``mask_discord_webhook`` /
  ``mask_discord_webhook_in`` to ``message`` / ``detail`` at
  construction time, so even if ``last_error`` carries a Discord
  webhook URL the exception stream stays redacted.
* **Aggregate boundary (§確定 K)** — the Task does **not** import
  ``ReviewDecision`` (Gate VO) or any other Aggregate's value
  object. ``approve_review`` / ``reject_review`` are dispatched by
  the application layer (``GateService``) on Gate APPROVED /
  REJECTED, keeping the Task ignorant of Gate internals.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task.aggregate_validators import (
    _validate_assigned_agents_capacity,
    _validate_assigned_agents_unique,
    _validate_blocked_has_last_error,
    _validate_last_error_consistency,
    _validate_timestamp_order,
)
from bakufu.domain.task.state_machine import (
    TaskAction,
    allowed_actions_from,
    lookup,
)
from bakufu.domain.value_objects import (
    AgentId,
    Deliverable,
    DirectiveId,
    OwnerId,
    RoomId,
    StageId,
    TaskId,
    TaskStatus,
    TransitionId,
)


class Task(BaseModel):
    """Lifecycle-aware unit of work delegated to one or more Agents.

    A Task is created by ``DirectiveService.issue()`` (PENDING with
    no assigned agents), advances through a Workflow's Stages while
    accumulating per-Stage :class:`Deliverable` snapshots, and
    eventually terminates as DONE or CANCELLED. The lifecycle is
    driven by ten behavior methods whose names match the state
    machine action names exactly — there is no implicit dispatch.

    Out-of-aggregate concerns (Workflow / Room / Agent reference
    integrity, ``current_stage_id`` lookup, Gate decision bridging)
    live in ``TaskService`` per §確定 K.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: TaskId
    room_id: RoomId
    directive_id: DirectiveId
    current_stage_id: StageId
    deliverables: dict[StageId, Deliverable] = {}
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent_ids: list[AgentId] = []
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None

    # ---- pre-validation -------------------------------------------------
    @field_validator("created_at", "updated_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        """Reject naive datetimes at the aggregate boundary (§確定 H)."""
        if value.tzinfo is None:
            raise ValueError(
                "Task timestamps must be timezone-aware UTC datetimes (received a naive datetime)"
            )
        return value

    @field_validator("last_error", mode="before")
    @classmethod
    def _normalize_last_error(cls, value: object) -> object:
        """Apply NFC normalization without ``strip`` (§確定 C).

        LLM stack traces rely on leading whitespace for indentation;
        the precedent set by ``Persona.prompt_body`` /
        ``PromptKit.prefix_markdown`` / ``Directive.text`` (NFC-only,
        no strip) carries forward to ``Task.last_error``.
        """
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Run the structural invariants (§確定 J kinds 3〜7)."""
        _validate_assigned_agents_unique(self.assigned_agent_ids)
        _validate_assigned_agents_capacity(self.assigned_agent_ids)
        _validate_last_error_consistency(self.status, self.last_error)
        _validate_blocked_has_last_error(self.status, self.last_error)
        _validate_timestamp_order(self.created_at, self.updated_at)
        return self

    # ---- behaviors (Tell, Don't Ask) ------------------------------------
    def assign(self, agent_ids: list[AgentId], *, updated_at: datetime) -> Task:
        """PENDING → IN_PROGRESS, attach ``agent_ids`` (REQ-TS-002).

        The list is taken verbatim — uniqueness / capacity checks
        live in the model validator so a Repository hydration path
        hits the same gate as this method.
        """
        next_status = self._lookup_or_raise("assign")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "assigned_agent_ids": list(agent_ids),
                "updated_at": updated_at,
            }
        )

    def commit_deliverable(
        self,
        stage_id: StageId,
        deliverable: Deliverable,
        by_agent_id: AgentId,
        *,
        updated_at: datetime,
    ) -> Task:
        """IN_PROGRESS self-loop, ``deliverables[stage_id] = deliverable`` (REQ-TS-003).

        ``by_agent_id`` is accepted for API symmetry with ``TaskService``
        but is **not** validated against ``assigned_agent_ids`` here —
        per §確定 G that membership check is the application layer's
        job; the aggregate proves only that ``stage_id`` is structurally
        a valid ``StageId`` and that the state machine permits the
        action.
        """
        del by_agent_id  # checked by TaskService.commit_deliverable, not here.
        next_status = self._lookup_or_raise("commit_deliverable")
        new_deliverables = {**self.deliverables, stage_id: deliverable}
        return self._rebuild_with_state(
            {
                "status": next_status,
                "deliverables": new_deliverables,
                "updated_at": updated_at,
            }
        )

    def request_external_review(self, *, updated_at: datetime) -> Task:
        """IN_PROGRESS → AWAITING_EXTERNAL_REVIEW (REQ-TS-004)."""
        next_status = self._lookup_or_raise("request_external_review")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "updated_at": updated_at,
            }
        )

    def approve_review(
        self,
        transition_id: TransitionId,
        by_owner_id: OwnerId,
        next_stage_id: StageId,
        *,
        updated_at: datetime,
    ) -> Task:
        """AWAITING_EXTERNAL_REVIEW → IN_PROGRESS (Gate APPROVED, REQ-TS-005a).

        ``transition_id`` / ``by_owner_id`` are positional metadata
        the application layer passes through for audit purposes; the
        aggregate stores neither (audit_log is GateService's job).
        ``next_stage_id`` is the Stage the Workflow says to advance
        to — verifying it lives inside the Workflow's stages is the
        application layer's job (§確定 K).
        """
        del transition_id, by_owner_id
        next_status = self._lookup_or_raise("approve_review")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "current_stage_id": next_stage_id,
                "updated_at": updated_at,
            }
        )

    def reject_review(
        self,
        transition_id: TransitionId,
        by_owner_id: OwnerId,
        next_stage_id: StageId,
        *,
        updated_at: datetime,
    ) -> Task:
        """AWAITING_EXTERNAL_REVIEW → IN_PROGRESS (Gate REJECTED, REQ-TS-005b).

        Same shape as :meth:`approve_review`; ``next_stage_id`` is the
        rollback / revision Stage rather than the forward one. Keeping
        the methods separate (instead of a single ``advance(...,
        gate_decision=...)``) is the §確定 A-2 凍結 — Tell-Don't-Ask
        and Aggregate-boundary preservation.
        """
        del transition_id, by_owner_id
        next_status = self._lookup_or_raise("reject_review")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "current_stage_id": next_stage_id,
                "updated_at": updated_at,
            }
        )

    def advance_to_next(
        self,
        transition_id: TransitionId,
        by_owner_id: OwnerId,
        next_stage_id: StageId,
        *,
        updated_at: datetime,
    ) -> Task:
        """IN_PROGRESS self-loop, advance ``current_stage_id`` (REQ-TS-005c).

        Used for Stage-to-Stage progression that does **not** go
        through an EXTERNAL_REVIEW Gate (e.g. a WORK Stage feeding
        the next WORK Stage). Status stays IN_PROGRESS; only the
        ``current_stage_id`` moves.
        """
        del transition_id, by_owner_id
        next_status = self._lookup_or_raise("advance_to_next")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "current_stage_id": next_stage_id,
                "updated_at": updated_at,
            }
        )

    def complete(
        self,
        transition_id: TransitionId,
        by_owner_id: OwnerId,
        *,
        updated_at: datetime,
    ) -> Task:
        """IN_PROGRESS → DONE (terminal, REQ-TS-005d).

        ``current_stage_id`` is intentionally unchanged: the Task
        terminates *at* its current Stage, and downstream consumers
        can read the last Stage from this attribute. Verifying that
        the current Stage is genuinely a sink is GateService /
        TaskService's job (§確定 K).
        """
        del transition_id, by_owner_id
        next_status = self._lookup_or_raise("complete")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "updated_at": updated_at,
            }
        )

    def cancel(
        self,
        by_owner_id: OwnerId,
        reason: str,
        *,
        updated_at: datetime,
    ) -> Task:
        """{PENDING / IN_PROGRESS / AWAITING_EXTERNAL_REVIEW / BLOCKED} → CANCELLED (REQ-TS-006).

        ``reason`` is application-layer audit metadata; the
        aggregate does **not** persist it (§設計判断補足 §"なぜ
        cancel reason を Aggregate 属性として持たないか"). The cancel
        path also resets ``last_error`` to ``None`` so the
        ``status != BLOCKED ⇔ last_error is None`` consistency
        invariant holds for the new instance.
        """
        del by_owner_id, reason
        next_status = self._lookup_or_raise("cancel")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "last_error": None,
                "updated_at": updated_at,
            }
        )

    def block(
        self,
        reason: str,
        last_error: str,
        *,
        updated_at: datetime,
    ) -> Task:
        """IN_PROGRESS → BLOCKED, attach ``last_error`` (REQ-TS-007).

        ``reason`` is an application-layer audit annotation
        (recorded by ``TaskService`` before the ``audit_log`` write);
        only ``last_error`` reaches the aggregate. The model
        validator runs ``_validate_blocked_has_last_error`` against
        the NFC-normalized form so an empty / whitespace-only
        ``last_error`` is rejected at construction time.
        """
        del reason  # recorded by TaskService.block, not stored on Task.
        next_status = self._lookup_or_raise("block")
        return self._rebuild_with_state(
            {
                "status": next_status,
                # The field validator on ``last_error`` re-applies NFC
                # normalization on rebuild, so passing the raw value
                # through is fine.
                "last_error": last_error,
                "updated_at": updated_at,
            }
        )

    def unblock_retry(self, *, updated_at: datetime) -> Task:
        """BLOCKED → IN_PROGRESS, clear ``last_error`` (REQ-TS-008, §確定 D)."""
        next_status = self._lookup_or_raise("unblock_retry")
        return self._rebuild_with_state(
            {
                "status": next_status,
                "last_error": None,
                "updated_at": updated_at,
            }
        )

    # ---- internal -------------------------------------------------------
    def _assert_not_terminal(self) -> None:
        """Reject behaviors invoked on DONE / CANCELLED Tasks (MSG-TS-001).

        Centralised here so all ten methods share the same Fail-Fast
        path; future readers can search for "terminal_violation" and
        find a single implementation. The terminal check runs *before*
        the state-machine lookup so a callable on a DONE Task gets
        the more specific ``MSG-TS-001`` message rather than the
        generic ``state_transition_invalid``.
        """
        if self.status not in (TaskStatus.DONE, TaskStatus.CANCELLED):
            return
        raise TaskInvariantViolation(
            kind="terminal_violation",
            message=(
                f"[FAIL] Task is in terminal state {self.status.value} "
                f"and cannot be modified: task_id={self.id}\n"
                f"Next: Check Task status before invoking behaviors; "
                f"DONE/CANCELLED Tasks are immutable."
            ),
            detail={
                "status": self.status.value,
                "task_id": str(self.id),
            },
        )

    def _lookup_or_raise(self, action: TaskAction) -> TaskStatus:
        """Combine terminal check + state-machine lookup for behaviors.

        Returns the ``next_status`` decided by the state machine. Any
        of the three failure paths
        (``terminal_violation`` / ``state_transition_invalid``)
        raises a :class:`TaskInvariantViolation` before
        :meth:`_rebuild_with_state` runs, so the original Task is
        guaranteed to be untouched on failure (pre-validate
        contract).
        """
        self._assert_not_terminal()
        try:
            return lookup(self.status, action)
        except KeyError as exc:
            allowed = list(allowed_actions_from(self.status))
            raise TaskInvariantViolation(
                kind="state_transition_invalid",
                message=(
                    f"[FAIL] Invalid state transition: {self.status.value} "
                    f"cannot perform '{action}' "
                    f"(allowed actions from {self.status.value}: {allowed})\n"
                    f"Next: Verify Task lifecycle; review state_machine.py "
                    f"for the allowed transitions table."
                ),
                detail={
                    "status": self.status.value,
                    "action": action,
                    "allowed_actions": allowed,
                    "task_id": str(self.id),
                },
            ) from exc

    def _rebuild_with_state(self, updates: dict[str, Any]) -> Task:
        """Pre-validate rebuild for behavior outputs (§確定 A).

        Same pattern as the M1 5 兄弟 (Empire / Workflow / Agent /
        Room / Directive). ``model_dump`` produces the canonical
        Python-mode payload, the dict swap applies the behavior's
        delta, and ``model_validate`` re-runs every field validator
        + the post-validator so structural invariants fire
        regardless of how the new state was reached.
        """
        state = self.model_dump()
        state.update(updates)
        return Task.model_validate(state)


__all__ = [
    "Task",
]
