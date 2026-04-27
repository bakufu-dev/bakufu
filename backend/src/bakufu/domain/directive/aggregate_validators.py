"""Aggregate-level invariant helpers for :class:`Directive`.

Each helper is a **module-level pure function** so tests can ``import``
and invoke directly — same testability pattern Norman / Steve approved
for the agent ``aggregate_validators.py`` and the room
``aggregate_validators.py``.

Helpers:

1. :func:`_validate_text_range` — ``1 ≤ NFC(text) ≤ 10000``. Length is
   judged on the **NFC-normalized** text without ``strip``; CEO
   directives may carry meaningful leading / trailing whitespace and
   newlines (multi-paragraph briefs).
2. :func:`_validate_task_link_immutable` — Fail Fast when ``link_task``
   is invoked on a Directive that already has a non-``None``
   ``task_id``. The constructor path (used by Repository hydration)
   accepts any ``TaskId | None`` value because a permanent attribute
   value is not a *transition*; only ``link_task`` watches for
   transition violations (see Directive detailed-design §確定 C).

Naming follows the agent / room precedent (``_validate_*``).
"""

from __future__ import annotations

from uuid import UUID

from bakufu.domain.exceptions import DirectiveInvariantViolation

# Confirmation B: text length bounds (1〜10000 after NFC normalization).
MIN_TEXT_LENGTH: int = 1
MAX_TEXT_LENGTH: int = 10_000


def _validate_text_range(text: str) -> None:
    """``Directive.text`` must fall in 1〜10000 characters (MSG-DR-001).

    Length is judged on the **NFC-normalized** string (the field
    validator runs the pipeline before this helper is invoked) without
    ``strip`` — CEO directives may include leading / trailing
    whitespace + multi-paragraph blocks that carry meaning.
    """
    length = len(text)
    if not (MIN_TEXT_LENGTH <= length <= MAX_TEXT_LENGTH):
        raise DirectiveInvariantViolation(
            kind="text_range",
            message=(
                f"[FAIL] Directive text must be "
                f"{MIN_TEXT_LENGTH}-{MAX_TEXT_LENGTH} characters (got {length})\n"
                f"Next: Trim directive content to <={MAX_TEXT_LENGTH} "
                f"NFC-normalized characters; for richer prompts use "
                f"multiple directives or attach a deliverable."
            ),
            detail={"length": length},
        )


def _validate_task_link_immutable(
    *,
    directive_id: UUID,
    existing_task_id: UUID | None,
    attempted_task_id: UUID,
) -> None:
    """Reject a ``link_task`` call against an already-linked Directive.

    Confirmation C / D / Norman 凍結: 1 Directive maps to 1 Task by
    design; a second ``link_task`` call is **always** a Fail Fast
    rather than a no-op, regardless of whether the new TaskId equals
    the existing one. The simpler contract avoids special cases in the
    aggregate validator and matches the business rule "re-issuing a
    directive means creating a *new* Directive."

    Raises:
        DirectiveInvariantViolation: ``kind='task_already_linked'``
            (MSG-DR-002) when ``existing_task_id is not None``.
    """
    if existing_task_id is None:
        return
    raise DirectiveInvariantViolation(
        kind="task_already_linked",
        message=(
            f"[FAIL] Directive already has a linked Task: "
            f"directive_id={directive_id}, "
            f"existing_task_id={existing_task_id}\n"
            f"Next: Issue a new Directive instead of re-linking; one "
            f"Directive maps to one Task by design."
        ),
        detail={
            "directive_id": str(directive_id),
            "existing_task_id": str(existing_task_id),
            "attempted_task_id": str(attempted_task_id),
        },
    )


__all__ = [
    "MAX_TEXT_LENGTH",
    "MIN_TEXT_LENGTH",
    "_validate_task_link_immutable",
    "_validate_text_range",
]
