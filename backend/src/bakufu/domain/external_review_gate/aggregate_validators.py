"""Aggregate-level invariant helpers for :class:`ExternalReviewGate`.

Each helper is a **module-level pure function** so tests can ``import``
and invoke directly — the same testability pattern Norman / Steve
approved for the agent / room / directive / task aggregate validators.

Helpers (5 total, matching detailed-design.md §確定 J):

1. :func:`_validate_decided_at_consistency` — ``decision == PENDING``
   ⇔ ``decided_at is None``; the four other states must carry a
   tz-aware decided_at.
2. :func:`_validate_snapshot_immutable` — placeholder; the structural
   guard is the absence of ``deliverable_snapshot`` in
   ``_rebuild_with_state``'s argument set (§確定 D). The function
   stays for symmetry with the validator dispatch and to provide a
   well-defined failure path if a rebuild ever supplies a different
   snapshot.
3. :func:`_validate_feedback_text_range` — NFC code-point length
   0〜10000.
4. :func:`_validate_audit_trail_append_only` — checked at rebuild
   time by comparing the new list against the previous one (§確定 C
   inputs/expectations table).

The decision-immutability invariant (PENDING → 1 transition only) is
enforced inside the state-machine ``lookup`` path; this module owns
only the structural invariants that fire on every
``model_validate``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.value_objects import ReviewDecision

if TYPE_CHECKING:
    from bakufu.domain.value_objects import AuditEntry, Deliverable

# Confirmation F: feedback_text length bounds (NFC, no strip).
MIN_FEEDBACK_LENGTH: int = 0
MAX_FEEDBACK_LENGTH: int = 10_000


def _validate_decided_at_consistency(
    decision: ReviewDecision,
    decided_at: datetime | None,
) -> None:
    """``decision == PENDING`` ⇔ ``decided_at is None`` (MSG-GT-002).

    Detects Repository row corruption such as
    ``decision=APPROVED, decided_at=None`` (terminal Gate without a
    decided_at timestamp) or the reverse, ``decision=PENDING`` with a
    populated ``decided_at`` — both shapes are structurally illegal
    and catching them at hydration means the application layer
    cannot be handed an inconsistent Gate.
    """
    is_pending = decision == ReviewDecision.PENDING
    has_timestamp = decided_at is not None
    if is_pending == (not has_timestamp):
        return
    decided_at_state = "set" if has_timestamp else "None"
    raise ExternalReviewGateInvariantViolation(
        kind="decided_at_inconsistent",
        message=(
            f"[FAIL] Gate decided_at consistency violation: "
            f"decision={decision.value}, decided_at={decided_at_state}\n"
            f"Next: decided_at must be None when decision==PENDING, "
            f"and a UTC tz-aware datetime otherwise; "
            f"check Repository row integrity."
        ),
        detail={
            "decision": decision.value,
            "decided_at_present": decided_at_state,
        },
    )


def _validate_feedback_text_range(feedback_text: str) -> None:
    """``0 <= len(NFC(feedback_text)) <= 10000`` (MSG-GT-004)."""
    length = len(feedback_text)
    if not (MIN_FEEDBACK_LENGTH <= length <= MAX_FEEDBACK_LENGTH):
        raise ExternalReviewGateInvariantViolation(
            kind="feedback_text_range",
            message=(
                f"[FAIL] Gate feedback_text must be "
                f"{MIN_FEEDBACK_LENGTH}-{MAX_FEEDBACK_LENGTH} characters "
                f"(got {length})\n"
                f"Next: Trim the comment/reason to "
                f"<={MAX_FEEDBACK_LENGTH} NFC-normalized characters."
            ),
            detail={"length": length},
        )


def _validate_audit_trail_append_only(
    previous: list[AuditEntry] | None,
    current: list[AuditEntry],
) -> None:
    """Existing entries must stay byte-equal and at the head of the list (MSG-GT-005).

    Construction (``previous is None``) accepts any list — the
    aggregate's first instance simply locks in whatever Repository
    hydration / the issuing application service hands over. Every
    subsequent ``_rebuild_with_state`` call must satisfy:

    1. ``len(current) >= len(previous)`` (no deletions).
    2. ``current[: len(previous)] == previous`` (no edits, no
       reorderings, no prepends, no middle inserts).

    The §確定 C inputs/expectations table is the canonical reference
    for the failure cases this guards against.
    """
    if previous is None:
        return
    n = len(previous)
    if len(current) < n:
        raise ExternalReviewGateInvariantViolation(
            kind="audit_trail_append_only",
            message=(
                "[FAIL] Gate audit_trail violates append-only contract: "
                "existing entries cannot be modified or reordered\n"
                "Next: Only append new AuditEntry instances at the end; "
                "never edit, prepend, or delete existing entries."
            ),
            detail={
                "previous_length": n,
                "current_length": len(current),
                "violation": "deletion",
            },
        )
    if current[:n] != previous:
        raise ExternalReviewGateInvariantViolation(
            kind="audit_trail_append_only",
            message=(
                "[FAIL] Gate audit_trail violates append-only contract: "
                "existing entries cannot be modified or reordered\n"
                "Next: Only append new AuditEntry instances at the end; "
                "never edit, prepend, or delete existing entries."
            ),
            detail={
                "previous_length": n,
                "current_length": len(current),
                "violation": "modification_or_reorder",
            },
        )


def _validate_snapshot_immutable(
    previous: Deliverable | None,
    current: Deliverable,
) -> None:
    """The construction-time ``deliverable_snapshot`` may not be replaced (MSG-GT-003).

    Construction (``previous is None``) accepts any Deliverable — the
    aggregate's first instance pins whatever the application service
    or Repository hydration supplies. Subsequent ``_rebuild_with_state``
    calls **must not** pass a different snapshot; the implementation
    contract (§確定 D) is to leave ``deliverable_snapshot`` out of
    the rebuild's argument set entirely so the value carries through
    unchanged. This validator is the failure-path safety net if that
    contract ever leaks.
    """
    if previous is None:
        return
    if current != previous:
        raise ExternalReviewGateInvariantViolation(
            kind="snapshot_immutable",
            message=(
                "[FAIL] Gate deliverable_snapshot is immutable after construction\n"
                "Next: deliverable_snapshot is frozen at Gate creation; "
                "do not pass it to _rebuild_with_state. "
                "Issue a new Gate for a new deliverable."
            ),
            detail={
                "violation": "snapshot_changed",
            },
        )


__all__ = [
    "MAX_FEEDBACK_LENGTH",
    "MIN_FEEDBACK_LENGTH",
    "_validate_audit_trail_append_only",
    "_validate_decided_at_consistency",
    "_validate_feedback_text_range",
    "_validate_snapshot_immutable",
]
