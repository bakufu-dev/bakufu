"""Verdict value object for InternalReviewGate.

A Verdict represents one agent's review decision submitted to an
InternalReviewGate. Verdicts are append-only within the aggregate; each
entry corresponds to exactly one role.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bakufu.domain.value_objects.enums import VerdictDecision
from bakufu.domain.value_objects.gate_role import GateRole
from bakufu.domain.value_objects.identifiers import AgentId

# ---------------------------------------------------------------------------
# Verdict VO (InternalReviewGate feature)
# ---------------------------------------------------------------------------
_VERDICT_COMMENT_MAX_CHARS: int = 5_000


class Verdict(BaseModel):
    """One agent's verdict submitted to an :class:`InternalReviewGate`.

    Stored as a ``tuple[Verdict, ...]`` inside the aggregate; the
    tuple is append-only (frozen aggregate rebuild pattern) and each
    entry corresponds to exactly one :attr:`role` — duplicate roles
    are rejected by ``aggregate_validators._validate_no_duplicate_roles``.

    Fields:

    * ``role`` — the :data:`GateRole` slug the submitting agent is
      acting as.
    * ``agent_id`` — the UUID of the submitting agent.
    * ``decision`` — :class:`VerdictDecision` (APPROVED / REJECTED).
    * ``comment`` — free-form NFC-normalized text, 0〜5000 chars;
      **strip is not applied** (multi-line review comments whose
      leading whitespace carries meaning must be preserved — same
      precedent as ``AuditEntry.comment`` / ``Directive.text``).
    * ``decided_at`` — UTC tz-aware moment the verdict was submitted.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    role: GateRole
    agent_id: AgentId
    decision: VerdictDecision
    comment: str = Field(default="", max_length=_VERDICT_COMMENT_MAX_CHARS)
    decided_at: datetime

    @field_validator("comment", mode="before")
    @classmethod
    def _normalize_comment(cls, value: object) -> object:
        """NFC normalization only — strip is intentionally **not** applied."""
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("decided_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Verdict.decided_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value


__all__ = [
    "_VERDICT_COMMENT_MAX_CHARS",
    "Verdict",
]
