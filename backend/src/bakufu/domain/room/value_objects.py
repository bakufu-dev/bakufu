"""Room-specific Value Objects (:class:`AgentMembership` / :class:`PromptKit`).

These VOs live in the ``room/`` package rather than the global
:mod:`bakufu.domain.value_objects` so the file-level boundary mirrors the
responsibility boundary — same pattern Norman approved for the agent /
workflow packages. ``Role`` and ``AgentId`` remain in the global module
because they cross feature boundaries.

``PromptKit.prefix_markdown`` applies **NFC only** (no strip): the field
holds Markdown text where leading/trailing newlines are semantically
significant for the downstream prompt renderer. Same rule the agent
``Persona.prompt_body`` follows (Agent §確定 E / Room §確定 B).
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bakufu.domain.value_objects import AgentId, Role

# ---------------------------------------------------------------------------
# AgentMembership (Room §確定 F — (agent_id, role) pair as the unique key)
# ---------------------------------------------------------------------------


class AgentMembership(BaseModel):
    """Frozen membership entry: an :class:`Agent` taking on a :class:`Role`.

    The Room aggregate stores a ``list[AgentMembership]`` and enforces
    ``(agent_id, role)`` pair uniqueness — **not** ``agent_id`` alone — so a
    single agent can hold multiple roles (e.g. LEADER + REVIEWER). Storing
    ``joined_at`` per-role lets the UI surface "joined as LEADER on X, then
    added REVIEWER on Y" naturally.

    Stored under ``docs/design/domain-model/value-objects.md`` §AgentMembership;
    Room is the only feature that composes this VO today.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    agent_id: AgentId
    role: Role
    joined_at: datetime


# ---------------------------------------------------------------------------
# PromptKit (Room §確定 G — single-attribute VO, retained for Phase-2 growth)
# ---------------------------------------------------------------------------
PROMPT_KIT_PREFIX_MAX: int = 10_000


class PromptKit(BaseModel):
    """Room-scoped system-prompt preamble (Markdown text).

    Single-attribute VO today; the structure exists so Phase 2 can extend it
    with ``variables``, ``role_specific_prefix``, or ``sections`` without
    forcing a schema migration on :class:`Room` (Room §確定 G).

    The persistence layer applies secret masking to ``prefix_markdown``
    *before* it lands in the SQLite ``rooms`` row — see
    ``docs/design/domain-model/storage.md`` §シークレットマスキング規則.
    The aggregate keeps the raw user input so the UI can read it back
    unchanged; the masking gateway is **only** at the persistence boundary.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    prefix_markdown: str = ""

    @field_validator("prefix_markdown", mode="before")
    @classmethod
    def _normalize_prefix(cls, value: object) -> object:
        # NFC only — preserves leading/trailing Markdown whitespace (Room §確定 B).
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @model_validator(mode="after")
    def _check_self_invariants(self) -> Self:
        """Length cap raises :class:`pydantic.ValidationError` (MSG-RM-007).

        Room detailed-design §確定 I freezes that PromptKit length violations
        surface as ``ValidationError`` — not ``RoomInvariantViolation`` —
        because the failure happens *before* any Room aggregate is in scope.
        ``RoomService.update_prompt_kit`` then catches in two layers (VO
        construction → ``ValidationError``; aggregate behavior → archived
        terminal etc.).
        """
        length = len(self.prefix_markdown)
        if length > PROMPT_KIT_PREFIX_MAX:
            raise ValueError(
                f"[FAIL] PromptKit.prefix_markdown must be 0-{PROMPT_KIT_PREFIX_MAX} "
                f"characters (got {length})\n"
                f"Next: Trim PromptKit content to <={PROMPT_KIT_PREFIX_MAX} "
                f"NFC-normalized characters; for richer prompts use Phase 2 "
                f"sections (variables / role_specific_prefix / sections)."
            )
        return self


__all__ = [
    "PROMPT_KIT_PREFIX_MAX",
    "AgentMembership",
    "PromptKit",
]
