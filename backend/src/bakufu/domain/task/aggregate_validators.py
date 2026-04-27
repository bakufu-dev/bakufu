"""Aggregate-level invariant helpers for :class:`Task`.

Each helper is a **module-level pure function** so tests can ``import``
and invoke directly — same testability pattern Norman / Steve approved
for the agent / room / directive ``aggregate_validators.py`` modules
(M1 5 兄弟).

Helpers:

1. :func:`_validate_assigned_agents_unique` — no duplicate ``AgentId`` in
   ``assigned_agent_ids``.
2. :func:`_validate_assigned_agents_capacity` — at most 5 agents per Task.
3. :func:`_validate_last_error_consistency` — ``status == BLOCKED`` ⇔
   ``last_error`` is a non-empty string; otherwise ``last_error is None``.
   Detects Repository-side row corruption at hydration time.
4. :func:`_validate_blocked_has_last_error` — when ``status == BLOCKED``,
   ``last_error`` length (NFC code-points) must be 1〜10000. Bridges the
   §確定 R1-C "no strip" rule with the structural consistency check.
5. :func:`_validate_timestamp_order` — ``created_at <= updated_at``.

All helpers raise :class:`TaskInvariantViolation` with the matching
``kind`` discriminator from §確定 J. ``message`` strings follow the
two-line "[FAIL] ... / Next: ..." structure (§確定 J § MSG ID 確定文言)
so the CI assertion ``assert "Next:" in str(exc)`` (TC-UT-TS-046〜052)
fires consistently across all paths.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from uuid import UUID

from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.value_objects import TaskStatus

# Confirmation A: hard caps frozen by detailed-design §クラス設計.
MAX_ASSIGNED_AGENTS: int = 5
MIN_LAST_ERROR_LENGTH: int = 1
MAX_LAST_ERROR_LENGTH: int = 10_000


def _validate_assigned_agents_unique(assigned_agent_ids: list[UUID]) -> None:
    """``assigned_agent_ids`` may not contain duplicate values (MSG-TS-003)."""
    counts = Counter(assigned_agent_ids)
    duplicates = sorted({str(agent_id) for agent_id, count in counts.items() if count > 1})
    if duplicates:
        raise TaskInvariantViolation(
            kind="assigned_agents_unique",
            message=(
                f"[FAIL] Task assigned_agent_ids must not contain duplicates: "
                f"duplicates={duplicates}\n"
                f"Next: Deduplicate the agent_ids list before calling assign(); "
                f"each Agent may appear at most once."
            ),
            detail={"duplicates": duplicates},
        )


def _validate_assigned_agents_capacity(assigned_agent_ids: list[UUID]) -> None:
    """``len(assigned_agent_ids) <= MAX_ASSIGNED_AGENTS`` (MSG-TS-004)."""
    count = len(assigned_agent_ids)
    if count > MAX_ASSIGNED_AGENTS:
        raise TaskInvariantViolation(
            kind="assigned_agents_capacity",
            message=(
                f"[FAIL] Task assigned_agent_ids exceeds capacity: "
                f"got {count}, max {MAX_ASSIGNED_AGENTS}\n"
                f"Next: Reduce the number of assigned agents to "
                f"<={MAX_ASSIGNED_AGENTS}; split work into multiple Tasks "
                f"if more parallelism is needed."
            ),
            detail={"count": count, "max": MAX_ASSIGNED_AGENTS},
        )


def _validate_last_error_consistency(
    status: TaskStatus,
    last_error: str | None,
) -> None:
    """``status == BLOCKED`` ⇔ ``last_error`` is non-empty string (MSG-TS-005).

    Detects Repository row corruption such as
    ``status=DONE, last_error='AuthExpired: ...'`` (terminal Task with
    leftover error text) — that combination is structurally illegal and
    catching it here means hydration paths cannot smuggle an inconsistent
    state into the application layer.
    """
    is_blocked = status == TaskStatus.BLOCKED
    has_error = isinstance(last_error, str) and last_error != ""
    if is_blocked == has_error:
        return
    last_error_present = "non-empty" if has_error else ("empty" if last_error == "" else "None")
    raise TaskInvariantViolation(
        kind="last_error_consistency",
        message=(
            f"[FAIL] Task last_error consistency violation: "
            f"status={status.value} but last_error={last_error_present}\n"
            f"Next: last_error must be a non-empty string when status==BLOCKED, "
            f"and None otherwise; check Repository row integrity."
        ),
        detail={
            "status": status.value,
            "last_error_present": last_error_present,
        },
    )


def _validate_blocked_has_last_error(
    status: TaskStatus,
    last_error: str | None,
) -> None:
    """When ``status == BLOCKED``, ``last_error`` length must be 1〜10000 (MSG-TS-006).

    The check operates on the **NFC-normalized** string per §確定 R1-C —
    callers (``Task.block()``) run normalization upstream, so this helper
    sees the canonical form. ``strip`` is intentionally **not** applied:
    LLM stack traces rely on leading whitespace for indentation.
    """
    if status != TaskStatus.BLOCKED:
        return
    # ``None`` falls through with length 0 so the kind=blocked_requires_last_error
    # message stays specific to "BLOCKED but the string is empty";
    # ``_validate_last_error_consistency`` already catches the structural form.
    length = 0 if last_error is None else len(last_error)
    if not (MIN_LAST_ERROR_LENGTH <= length <= MAX_LAST_ERROR_LENGTH):
        raise TaskInvariantViolation(
            kind="blocked_requires_last_error",
            message=(
                f"[FAIL] Task block() requires non-empty last_error "
                f"(got NFC-normalized length={length})\n"
                f"Next: Provide a non-empty last_error string "
                f"({MIN_LAST_ERROR_LENGTH}-{MAX_LAST_ERROR_LENGTH} chars) "
                f"describing why the Task is blocked; an empty string is rejected."
            ),
            detail={
                "length": length,
                "min": MIN_LAST_ERROR_LENGTH,
                "max": MAX_LAST_ERROR_LENGTH,
            },
        )


def _validate_timestamp_order(created_at: datetime, updated_at: datetime) -> None:
    """``created_at <= updated_at`` (MSG-TS-007)."""
    if created_at > updated_at:
        raise TaskInvariantViolation(
            kind="timestamp_order",
            message=(
                f"[FAIL] Task timestamp order violation: "
                f"created_at={created_at.isoformat()} > "
                f"updated_at={updated_at.isoformat()}\n"
                f"Next: Verify timestamp generation; updated_at must be "
                f">= created_at, both UTC tz-aware."
            ),
            detail={
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat(),
            },
        )


__all__ = [
    "MAX_ASSIGNED_AGENTS",
    "MAX_LAST_ERROR_LENGTH",
    "MIN_LAST_ERROR_LENGTH",
    "_validate_assigned_agents_capacity",
    "_validate_assigned_agents_unique",
    "_validate_blocked_has_last_error",
    "_validate_last_error_consistency",
    "_validate_timestamp_order",
]
