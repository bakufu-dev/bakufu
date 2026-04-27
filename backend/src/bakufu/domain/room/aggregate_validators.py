"""Aggregate-level invariant helpers for :class:`Room`.

Each helper is a **module-level pure function** so tests can ``import`` and
invoke directly — same testability pattern Norman / Steve approved for the
agent ``aggregate_validators.py`` and the workflow ``dag_validators.py``.
The Aggregate Root in :mod:`bakufu.domain.room.room` stays a thin dispatch
over them; rule changes touch only the helper, never the orchestration code.

Helpers (run in this order in :class:`Room.model_validator`):

1. :func:`_validate_name_range` — ``1 ≤ NFC+strip(name) ≤ 80``
2. :func:`_validate_description_length` — ``0 ≤ NFC+strip(description) ≤ 500``
3. :func:`_validate_member_unique` — no duplicate ``(agent_id, role)`` pair
4. :func:`_validate_member_capacity` — ``len(members) ≤ 50``

Naming follows the agent / workflow precedent (``_validate_*_unique`` for
collection uniqueness checks). Boy Scout: every collection contract that says
"no duplicate (a, b) pair" gets a dedicated helper so the rule survives
future refactors (Steve's twin-defense symmetry rule from PR #16).
"""

from __future__ import annotations

from bakufu.domain.exceptions import RoomInvariantViolation
from bakufu.domain.room.value_objects import AgentMembership

# Confirmation B: name length bounds (1〜80 after NFC + strip).
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 80

# Confirmation B: description length bounds (0〜500 after NFC + strip).
MAX_DESCRIPTION_LENGTH: int = 500

# Confirmation C: member capacity (≤ 50).
MAX_MEMBERS: int = 50


def _validate_name_range(name: str) -> None:
    """``Room.name`` must fall in 1〜80 characters after NFC + strip (MSG-RM-001).

    Length is judged on the *normalized* string (the field validator runs the
    pipeline before this helper is invoked), so the count reflects what the
    user will see in audit logs and UI labels.
    """
    length = len(name)
    if not (MIN_NAME_LENGTH <= length <= MAX_NAME_LENGTH):
        raise RoomInvariantViolation(
            kind="name_range",
            message=(
                f"[FAIL] Room name must be "
                f"{MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} characters (got {length})\n"
                f"Next: Provide a name with {MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} "
                f"NFC-normalized characters; trim leading/trailing whitespace."
            ),
            detail={"length": length},
        )


def _validate_description_length(description: str) -> None:
    """``Room.description`` must fall in 0〜500 characters after NFC + strip (MSG-RM-002)."""
    length = len(description)
    if length > MAX_DESCRIPTION_LENGTH:
        raise RoomInvariantViolation(
            kind="description_too_long",
            message=(
                f"[FAIL] Room description must be 0-{MAX_DESCRIPTION_LENGTH} "
                f"characters (got {length})\n"
                f"Next: Shorten the description to <={MAX_DESCRIPTION_LENGTH} "
                f"characters; move long content to PromptKit.prefix_markdown "
                f"(10000 char limit)."
            ),
            detail={"length": length},
        )


def _validate_member_unique(members: list[AgentMembership]) -> None:
    """No two memberships may share the same ``(agent_id, role)`` pair (MSG-RM-003).

    Allowing the same agent to hold multiple roles (LEADER + REVIEWER, etc.)
    is a Room §確定 F design choice — the unique key is the **pair**, not
    ``agent_id`` alone. ``joined_at`` participates in equality of the VO but
    is intentionally **not** part of the uniqueness key here, so re-adding
    the same pair at a later timestamp is still rejected as a duplicate.
    """
    seen: set[tuple[object, str]] = set()
    for membership in members:
        key = (membership.agent_id, membership.role.value)
        if key in seen:
            raise RoomInvariantViolation(
                kind="member_duplicate",
                message=(
                    f"[FAIL] Duplicate member: "
                    f"agent_id={membership.agent_id}, role={membership.role.value}\n"
                    f"Next: Either skip this add (already a member) or use a "
                    f"different role to add the same agent in another capacity "
                    f"(e.g. leader + reviewer)."
                ),
                detail={
                    "agent_id": str(membership.agent_id),
                    "role": membership.role.value,
                },
            )
        seen.add(key)


def _validate_member_capacity(members: list[AgentMembership]) -> None:
    """Cap members at :data:`MAX_MEMBERS` (MSG-RM-004 / Room §確定 C)."""
    count = len(members)
    if count > MAX_MEMBERS:
        raise RoomInvariantViolation(
            kind="capacity_exceeded",
            message=(
                f"[FAIL] Room members capacity exceeded "
                f"(got {count}, max {MAX_MEMBERS})\n"
                f"Next: Remove unused members (e.g. archived agents) before "
                f"adding more, or split the work across multiple Rooms."
            ),
            detail={"members_count": count, "max_members": MAX_MEMBERS},
        )


__all__ = [
    "MAX_DESCRIPTION_LENGTH",
    "MAX_MEMBERS",
    "MAX_NAME_LENGTH",
    "MIN_NAME_LENGTH",
    "_validate_description_length",
    "_validate_member_capacity",
    "_validate_member_unique",
    "_validate_name_range",
]
