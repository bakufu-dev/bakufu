"""InternalReviewGate Aggregate Root.

Implements the internal (agent-to-agent) review gate for
``INTERNAL_REVIEW`` Stage completion. The aggregate collects per-role
:class:`Verdict` objects submitted by agents, derives the overall
:class:`GateDecision` from them via the state machine, and enforces
four structural invariants via ``model_validator(mode='after')``.

Design contracts (do not break without re-running design review):

* **Pre-validate rebuild** — ``submit_verdict`` uses ``model_dump`` /
  dict-update / ``model_validate`` (not ``model_copy(update=...)``),
  mirroring the ExternalReviewGate §確定 E pattern.
* **Frozen aggregate** — all fields are immutable; every behavior
  returns a **new** instance.
* **Comment NFC-only** — the ``comment`` field on :class:`Verdict` is
  NFC-normalized but never stripped (multi-line review comments whose
  leading whitespace carries meaning).
* **Decision computed, not stored independently** — ``gate_decision``
  stored in the aggregate must always equal ``compute_decision(verdicts,
  required_gate_roles)``; this is enforced by both the behavior method
  and the aggregate invariant validator.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.internal_review_gate.state_machine import compute_decision
from bakufu.domain.value_objects import (
    _VERDICT_COMMENT_MAX_CHARS,
    AgentId,
    GateDecision,
    GateRole,
    InternalGateId,
    StageId,
    TaskId,
    Verdict,
    VerdictDecision,
)


class InternalReviewGate(BaseModel):
    """Multi-role internal review checkpoint for ``INTERNAL_REVIEW`` Stages.

    A Gate is created in ``GateDecision.PENDING`` with an empty
    ``verdicts`` tuple and a non-empty ``required_gate_roles`` set.
    Agents submit verdicts via :meth:`submit_verdict`; the Gate
    transitions to ``ALL_APPROVED`` when every required role has
    approved, or to ``REJECTED`` as soon as any verdict is
    ``VerdictDecision.REJECTED`` (most-pessimistic-wins rule).

    The aggregate is frozen — every behavior returns a **new**
    :class:`InternalReviewGate` instance, leaving the original
    unchanged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=False)

    id: InternalGateId
    task_id: TaskId
    stage_id: StageId
    required_gate_roles: frozenset[GateRole]
    verdicts: tuple[Verdict, ...]
    gate_decision: GateDecision
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def _require_created_at_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "InternalReviewGate.created_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> InternalReviewGate:
        """Run the four structural invariants (internal-review-gate §確定 J).

        Importing inside the method breaks the circular dependency
        between this module and ``aggregate_validators`` (which imports
        this class for its type annotation).
        """
        from bakufu.domain.internal_review_gate.aggregate_validators import validate_all

        validate_all(self)
        return self

    # ---- behaviors (Tell, Don't Ask) -------------------------------------

    def submit_verdict(
        self,
        *,
        role: GateRole,
        agent_id: AgentId,
        decision: VerdictDecision,
        comment: str,
        decided_at: datetime,
    ) -> InternalReviewGate:
        """Append one agent verdict and recompute the gate decision.

        Step order (§確定 A 8 ステップ厳守):

        1. Guard: ``gate_decision`` must be PENDING (decided Gates are
           immutable).
        2. Guard: ``role`` must not already have a verdict in
           ``self.verdicts`` (one verdict per role per Gate).
        3. NFC-normalize ``comment`` (strip is **not** applied).
        4. Guard: ``role`` must be in ``required_gate_roles``
           (invalid roles are rejected before Verdict construction).
        5. Guard: NFC-normalized ``comment`` length must not exceed
           5000 characters.
        6. Build the new :class:`Verdict` and append to the tuple.
        7. Compute the new :class:`GateDecision` via
           :func:`compute_decision`.
        8. Reconstruct via ``model_dump`` / dict-update /
           ``model_validate`` so ``_check_invariants`` re-fires
           (pre-validate rebuild pattern, §確定 E), then return the
           new instance.

        Args:
            role: The GateRole the submitting agent is acting as.
                Must be in ``required_gate_roles`` (enforced by
                invariant 2 in ``_check_invariants``).
            agent_id: UUID of the submitting agent.
            decision: APPROVED or REJECTED.
            comment: Free-form review comment, 0〜5000 NFC chars.
                Strip is **not** applied.
            decided_at: UTC tz-aware moment of submission.

        Returns:
            A new :class:`InternalReviewGate` with the verdict
            appended and ``gate_decision`` recomputed.

        Raises:
            :class:`InternalReviewGateInvariantViolation`:
                ``gate_already_decided`` — the Gate is no longer PENDING.
                ``role_already_submitted`` — the role already has a verdict.
                ``invalid_role`` — role not in required_gate_roles.
                ``comment_too_long`` — NFC-normalized comment exceeds 5000 chars.
                (The last two are also caught by ``_check_invariants`` on
                rebuild, but are checked early here for user-friendly messages.)
        """
        # Step 1: gate must be PENDING.
        if self.gate_decision != GateDecision.PENDING:
            raise InternalReviewGateInvariantViolation(
                kind="gate_already_decided",
                message=(
                    f"[FAIL] InternalReviewGate は既に判断確定済みです"
                    f"（{self.gate_decision.value}）。\n"  # noqa: RUF001
                    f"Next: 新しい Gate が生成されるまでお待ちください。"
                ),
                detail={
                    "gate_id": str(self.id),
                    "gate_decision": self.gate_decision.value,
                },
            )

        # Step 2: role must not already have a verdict.
        existing_roles = frozenset(v.role for v in self.verdicts)
        if role in existing_roles:
            raise InternalReviewGateInvariantViolation(
                kind="role_already_submitted",
                message=(
                    f'[FAIL] GateRole "{role}" は既に判定を提出済みです。\n'
                    f"Next: 別の GateRole エージェントとして判定を提出してください。"
                ),
                detail={
                    "gate_id": str(self.id),
                    "role": role,
                },
            )

        # Step 3: NFC-normalize comment (strip is intentionally not applied).
        normalized_comment = unicodedata.normalize("NFC", comment)

        # Step 4: validate role membership before building Verdict.
        # Behavior 層での早期チェック:
        # invariant 層 (_validate_verdict_roles_in_required) でも同一条件を検査するが、
        # MSG-IRG-004 の日本語エラーメッセージを返すためにここで先に raise する。
        # invariant 層は InternalReviewGateInvariantViolation の
        # kind='verdict_role_invalid' を raise するが、submit_verdict 経由の caller には
        # kind='invalid_role' + 日本語 MSG が期待される。
        if role not in self.required_gate_roles:
            raise InternalReviewGateInvariantViolation(
                kind="invalid_role",
                message=(
                    f'[FAIL] GateRole "{role}" は本 Gate の required_gate_roles に'
                    f"含まれていません。\n"
                    f"Next: 有効な GateRole（{sorted(self.required_gate_roles)}）"  # noqa: RUF001
                    f"で提出してください。"
                ),
                detail={
                    "gate_id": str(self.id),
                    "role": role,
                    "required_gate_roles": sorted(self.required_gate_roles),
                },
            )

        # Step 5: comment length check (NFC-normalized, no strip).
        comment_length = len(normalized_comment)
        if comment_length > _VERDICT_COMMENT_MAX_CHARS:
            raise InternalReviewGateInvariantViolation(
                kind="comment_too_long",
                message=(
                    f"[FAIL] コメントが文字数上限（5000文字）を超えています"  # noqa: RUF001
                    f"（{comment_length}文字）。\n"  # noqa: RUF001
                    f"Next: 5000文字以内に短縮してください。"
                ),
                detail={
                    "gate_id": str(self.id),
                    "length": comment_length,
                    "max_length": _VERDICT_COMMENT_MAX_CHARS,
                },
            )

        # Step 6: build new Verdict and append to tuple.
        new_verdict = Verdict(
            role=role,
            agent_id=agent_id,
            decision=decision,
            comment=comment,
            decided_at=decided_at,
        )
        new_verdicts = (*self.verdicts, new_verdict)

        # Step 7: compute new gate_decision.
        new_gate_decision = compute_decision(new_verdicts, self.required_gate_roles)

        # Step 8: pre-validate rebuild (model_dump → update → model_validate)
        # so _check_invariants re-fires, then return the new instance.
        state: dict[str, Any] = self.model_dump()
        state["verdicts"] = [v.model_dump() for v in new_verdicts]
        state["gate_decision"] = new_gate_decision
        return InternalReviewGate.model_validate(state)


__all__ = ["InternalReviewGate"]
