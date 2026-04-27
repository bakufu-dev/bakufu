"""Room Aggregate Root package.

Implements ``REQ-RM-001``〜``REQ-RM-006`` per ``docs/features/room``. Split
into three sibling modules along the design's responsibility lines so each
file stays well under the 270-line readability budget and the file-level
boundary mirrors the agent / workflow precedent:

* :mod:`bakufu.domain.room.value_objects` — :class:`AgentMembership` and
  :class:`PromptKit` Pydantic VOs with their self-checks.
* :mod:`bakufu.domain.room.aggregate_validators` — four module-level
  invariant helpers covering name range / description length / member
  uniqueness / member capacity.
* :mod:`bakufu.domain.room.room` — :class:`Room` Aggregate Root that
  dispatches over the helpers in deterministic order.

This ``__init__`` re-exports the public surface plus the underscore-prefixed
helpers tests need to invoke directly (same pattern Norman approved for the
agent package).
"""

from __future__ import annotations

from bakufu.domain.room.aggregate_validators import (
    MAX_DESCRIPTION_LENGTH,
    MAX_MEMBERS,
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    _validate_description_length,
    _validate_member_capacity,
    _validate_member_unique,
    _validate_name_range,
)
from bakufu.domain.room.room import Room
from bakufu.domain.room.value_objects import (
    PROMPT_KIT_PREFIX_MAX,
    AgentMembership,
    PromptKit,
)

__all__ = [
    "MAX_DESCRIPTION_LENGTH",
    "MAX_MEMBERS",
    "MAX_NAME_LENGTH",
    "MIN_NAME_LENGTH",
    "PROMPT_KIT_PREFIX_MAX",
    "AgentMembership",
    "PromptKit",
    "Room",
    "_validate_description_length",
    "_validate_member_capacity",
    "_validate_member_unique",
    "_validate_name_range",
]
