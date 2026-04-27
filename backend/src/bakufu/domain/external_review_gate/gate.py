"""ExternalReviewGate Aggregate Root (REQ-GT-001〜007).

Implements ``docs/features/external-review-gate/`` as the M1 7th and
final sibling. The aggregate follows the same shape established by
empire / workflow / agent / room / directive / task but is **scoped
much tighter**: 4 methods x 4 decision states = 16-cell dispatch
table with **7 ✓ transitions + 9 ✗ cells**. The narrow surface lines
up with the Gate's job — bind a single human review round to a
single Stage outcome, then freeze.

Two structural elements unique to the Gate's lifecycle:

* a **decision-table state machine** in
  :mod:`bakufu.domain.external_review_gate.state_machine`, locked by
  ``Final[Mapping]`` + :class:`types.MappingProxyType` per §確定 B; and
* **four dedicated behavior methods** whose names map 1:1 to the
  action names in the state-machine table per §確定 A (the same
  Steve R2 凍結 pattern that task #42 §確定 A-2 introduced).

Design contracts (do not break without re-running design review):

* **Pre-validate rebuild (§確定 E)** — every behavior calls
  :meth:`_rebuild_with_state` which goes through ``model_dump`` /
  ``swap`` / ``model_validate``. ``model_copy(update=...)`` is
  intentionally avoided.
* **State-machine bypass Fail-Fast (§確定 A)** — illegal
  ``(decision, action)`` pairs raise
  :class:`ExternalReviewGateInvariantViolation` with
  ``kind='decision_already_decided'`` so MSG-GT-001 lands with the
  "Next:" hint already populated (the Gate is single-decision by
  design).
* **Snapshot immutable (§確定 D)** — :meth:`_rebuild_with_state`
  does **not** accept a ``deliverable_snapshot`` argument; every
  rebuild path inherits the construction-time snapshot byte-for-byte.
  The structural absence is the strongest possible guarantee against
  accidental mutation.
* **Audit-trail append-only (§確定 C)** — every behavior appends
  exactly one new :class:`AuditEntry` at the end of the list.
  :meth:`_rebuild_with_state` runs
  :func:`_validate_audit_trail_append_only` against the previous
  trail before reconstructing, so a misbehaving rebuild path
  surfaces ``audit_trail_append_only`` (MSG-GT-005) before the new
  instance is constructed.
* **Webhook auto-mask (§確定 H)** —
  :class:`ExternalReviewGateInvariantViolation` applies
  ``mask_discord_webhook`` / ``mask_discord_webhook_in`` to
  ``message`` / ``detail`` at construction time so a webhook URL
  embedded in ``feedback_text`` cannot leak through the exception
  stream.
* **Aggregate boundary (§確定 J)** — the Gate does **not** import
  Task / Workflow / Stage methods. ``GateService.approve()`` →
  ``task.approve_review(...)`` (and the symmetric REJECTED /
  CANCELLED legs) is dispatched by the application layer, keeping
  the Gate ignorant of Task internals.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any, Self
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.external_review_gate.aggregate_validators import (
    _validate_audit_trail_append_only,
    _validate_decided_at_consistency,
    _validate_feedback_text_range,
    _validate_snapshot_immutable,
)
from bakufu.domain.external_review_gate.state_machine import (
    GateAction,
    allowed_actions_from,
    lookup,
)
from bakufu.domain.value_objects import (
    AuditAction,
    AuditEntry,
    Deliverable,
    GateId,
    OwnerId,
    ReviewDecision,
    StageId,
    TaskId,
)


class ExternalReviewGate(BaseModel):
    """One human-review checkpoint binding a Task's Stage to a Decision.

    A Gate is created in PENDING by ``GateService.create()`` (after
    Task.request_external_review fires), accumulates audit views via
    :meth:`record_view`, and terminates exactly once via
    :meth:`approve` / :meth:`reject` / :meth:`cancel`. The terminal
    states still permit :meth:`record_view` (audit reads of decided
    Gates are legitimate and tracked, §確定 G "誰がいつ何度見たか").

    Out-of-aggregate concerns (Task / Stage / Owner reference
    integrity, snapshot inline-copy persistence, Gate-to-Task
    dispatch) live in ``GateService`` per §確定 J.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: GateId
    task_id: TaskId
    stage_id: StageId
    deliverable_snapshot: Deliverable
    reviewer_id: OwnerId
    decision: ReviewDecision = ReviewDecision.PENDING
    feedback_text: str = ""
    audit_trail: list[AuditEntry] = []
    created_at: datetime
    decided_at: datetime | None = None

    # ---- pre-validation -------------------------------------------------
    @field_validator("created_at", mode="after")
    @classmethod
    def _require_created_at_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "ExternalReviewGate.created_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value

    @field_validator("decided_at", mode="after")
    @classmethod
    def _require_decided_at_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "ExternalReviewGate.decided_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value

    @field_validator("feedback_text", mode="before")
    @classmethod
    def _normalize_feedback_text(cls, value: object) -> object:
        """NFC-only normalization (§確定 F).

        ``strip`` is intentionally **not** applied — CEO-authored
        review comments may include indented quoting / multi-paragraph
        bodies whose leading whitespace carries meaning, the same
        precedent set by ``Persona.prompt_body`` /
        ``PromptKit.prefix_markdown`` / ``Directive.text`` /
        ``Task.last_error``.
        """
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Run the structural invariants (§確定 J kinds 2 + 4).

        ``decision_already_decided`` is enforced by the state-machine
        ``lookup`` path (raises before this validator runs);
        ``snapshot_immutable`` is enforced structurally by
        :meth:`_rebuild_with_state` not accepting a snapshot argument;
        ``audit_trail_append_only`` is enforced by
        :meth:`_rebuild_with_state` running the validator against the
        previous trail before constructing the new instance. What
        stays on the after-validator is the pair of single-instance
        invariants that hydration paths (Repository round-trip) must
        also satisfy.
        """
        _validate_decided_at_consistency(self.decision, self.decided_at)
        _validate_feedback_text_range(self.feedback_text)
        return self

    # ---- behaviors (Tell, Don't Ask) ------------------------------------
    def approve(
        self,
        by_owner_id: OwnerId,
        comment: str,
        *,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """PENDING → APPROVED, attach ``feedback_text`` + audit entry (REQ-GT-002).

        ``by_owner_id`` records the human who approved. The
        ``decided_at`` argument is taken explicitly (per §設計判断補足
        "なぜ decided_at を引数で受け取るか") so the aggregate stays
        time-pure and tests don't need ``freezegun``.
        """
        next_decision = self._lookup_or_raise("approve")
        return self._rebuild_with_state(
            new_audit_action=AuditAction.APPROVED,
            new_audit_actor=by_owner_id,
            new_audit_comment=comment,
            new_audit_at=decided_at,
            decision=next_decision,
            feedback_text=comment,
            decided_at=decided_at,
        )

    def reject(
        self,
        by_owner_id: OwnerId,
        comment: str,
        *,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """PENDING → REJECTED, attach ``feedback_text`` + audit entry (REQ-GT-003).

        Same shape as :meth:`approve` — the only differences are the
        target ``decision`` (REJECTED) and the audit row's
        :class:`AuditAction` discriminator.
        """
        next_decision = self._lookup_or_raise("reject")
        return self._rebuild_with_state(
            new_audit_action=AuditAction.REJECTED,
            new_audit_actor=by_owner_id,
            new_audit_comment=comment,
            new_audit_at=decided_at,
            decision=next_decision,
            feedback_text=comment,
            decided_at=decided_at,
        )

    def cancel(
        self,
        by_owner_id: OwnerId,
        reason: str,
        *,
        decided_at: datetime,
    ) -> ExternalReviewGate:
        """PENDING → CANCELLED, attach ``feedback_text`` + audit entry (REQ-GT-004).

        ``reason`` lands in both ``feedback_text`` (so the
        application layer can surface why the Gate was withdrawn)
        and the audit entry's ``comment`` (so the audit trail
        records the reasoning).
        """
        next_decision = self._lookup_or_raise("cancel")
        return self._rebuild_with_state(
            new_audit_action=AuditAction.CANCELLED,
            new_audit_actor=by_owner_id,
            new_audit_comment=reason,
            new_audit_at=decided_at,
            decision=next_decision,
            feedback_text=reason,
            decided_at=decided_at,
        )

    def record_view(
        self,
        by_owner_id: OwnerId,
        *,
        viewed_at: datetime,
    ) -> ExternalReviewGate:
        """Append a VIEWED audit entry; permitted in **every** decision state (REQ-GT-005, §確定 G).

        ``decision`` / ``decided_at`` / ``feedback_text`` are
        deliberately *not* updated — record_view is purely an audit
        operation. Idempotency is **not** offered (§確定 G "冪等性
        なし"): two calls with the same ``(by_owner_id, viewed_at)``
        produce two distinct entries because the audit requirement is
        "誰がいつ何度見たか" — collapsing duplicates would discard
        the very signal the audit trail is supposed to preserve.
        """
        # State-machine lookup confirms the action is legal from the
        # current decision; the result is the same value (self-loop)
        # but the call documents the contract.
        self._lookup_or_raise("record_view")
        return self._rebuild_with_state(
            new_audit_action=AuditAction.VIEWED,
            new_audit_actor=by_owner_id,
            new_audit_comment="",
            new_audit_at=viewed_at,
        )

    # ---- internal -------------------------------------------------------
    def _lookup_or_raise(self, action: GateAction) -> ReviewDecision:
        """State-machine lookup, translating ``KeyError`` into MSG-GT-001.

        Returns the ``next_decision`` for the (current_decision,
        action) pair. The four PENDING-only actions (``approve`` /
        ``reject`` / ``cancel``) raise here when the Gate has already
        been decided — the lookup table simply has no row for
        ``(APPROVED, 'approve')`` etc.
        """
        try:
            return lookup(self.decision, action)
        except KeyError as exc:
            allowed = list(allowed_actions_from(self.decision))
            raise ExternalReviewGateInvariantViolation(
                kind="decision_already_decided",
                message=(
                    f"[FAIL] Gate decision is already decided: "
                    f"gate_id={self.id}, current_decision={self.decision.value}\n"
                    f"Next: A Gate can only be decided once "
                    f"(PENDING -> APPROVED/REJECTED/CANCELLED); "
                    f"issue a new directive for re-review."
                ),
                detail={
                    "gate_id": str(self.id),
                    "current_decision": self.decision.value,
                    "attempted_action": action,
                    "allowed_actions": allowed,
                },
            ) from exc

    def _rebuild_with_state(
        self,
        *,
        new_audit_action: AuditAction,
        new_audit_actor: OwnerId,
        new_audit_comment: str,
        new_audit_at: datetime,
        decision: ReviewDecision | None = None,
        feedback_text: str | None = None,
        decided_at: datetime | None = None,
    ) -> ExternalReviewGate:
        """Pre-validate rebuild for behavior outputs (§確定 E).

        The rebuild path is the **only** legal way to mutate the
        Gate's audit_trail / decision / feedback_text / decided_at
        fields. ``deliverable_snapshot`` is intentionally absent
        from the keyword-only argument list so no rebuild path can
        replace it (§確定 D).

        Step order:

        1. Build the new :class:`AuditEntry` — every behavior
           appends exactly one entry, so the constructor lives here
           rather than at every call site.
        2. Compose ``new_audit_trail = self.audit_trail + [new]`` and
           validate it against the previous trail
           (:func:`_validate_audit_trail_append_only`). Failure
           here surfaces *before* a potentially-broken instance is
           constructed — Fail-Fast on programming bugs that
           accidentally drop or reorder existing entries.
        3. ``model_dump`` the current state, swap in the supplied
           field deltas, and re-construct via ``model_validate`` so
           ``_check_invariants`` re-fires.
        """
        new_entry = AuditEntry(
            id=uuid4(),
            actor_id=new_audit_actor,
            action=new_audit_action,
            comment=new_audit_comment,
            occurred_at=new_audit_at,
        )
        new_audit_trail = [*self.audit_trail, new_entry]
        _validate_audit_trail_append_only(self.audit_trail, new_audit_trail)

        state: dict[str, Any] = self.model_dump()
        if decision is not None:
            state["decision"] = decision
        if feedback_text is not None:
            state["feedback_text"] = feedback_text
        if decided_at is not None:
            state["decided_at"] = decided_at
        state["audit_trail"] = [entry.model_dump() for entry in new_audit_trail]
        # ``deliverable_snapshot`` carries through ``model_dump`` /
        # ``model_validate`` byte-for-byte: the snapshot pinned at
        # construction time is what the rebuilt Gate sees too
        # (§確定 D §不変条件).
        rebuilt = ExternalReviewGate.model_validate(state)
        # §確定 D 3 重防衛 safety net: the keyword-only signature above
        # is the *structural* guarantee (no rebuild path can pass a new
        # snapshot), but Steve R-S1 requires the validator be **active**
        # so a future refactor that breaks the structural guarantee is
        # caught here too. With the structural guarantee in place this
        # call is a no-op on the happy path and Fail-Fast otherwise —
        # exactly what a defense-in-depth safety net should be.
        _validate_snapshot_immutable(self.deliverable_snapshot, rebuilt.deliverable_snapshot)
        return rebuilt


__all__ = ["ExternalReviewGate"]
