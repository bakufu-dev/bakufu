"""Reference value objects held inside aggregates.

Contains:
- :class:`RoomRef` — frozen reference to a Room aggregate (used in Empire).
- :class:`AgentRef` — frozen reference to an Agent aggregate (used in Empire).
- :class:`CompletionPolicy` — how a Stage is judged complete (Workflow VO).
- :class:`NotifyChannel` — webhook channel for ``EXTERNAL_REVIEW`` Stages.
- :class:`AuditEntry` — one row of an ExternalReviewGate audit trail.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from bakufu.domain.value_objects.enums import AuditAction, Role
from bakufu.domain.value_objects.helpers import (
    NormalizedAgentName,
    NormalizedShortName,
    mask_discord_webhook,
)
from bakufu.domain.value_objects.identifiers import AgentId, OwnerId, RoomId

# ---------------------------------------------------------------------------
# Reference value objects (held inside Empire aggregate)
# ---------------------------------------------------------------------------


class RoomRef(BaseModel):
    """Frozen reference to a Room aggregate, kept inside :class:`Empire`.

    Equality and hashing are structural (Pydantic auto-implementation over all
    fields including ``archived``), so two ``RoomRef`` values compare equal
    only when both ``room_id`` *and* archived state agree — required for
    correct list diffing during ``Empire.archive_room``.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    room_id: RoomId
    name: NormalizedShortName
    archived: bool = False


class AgentRef(BaseModel):
    """Frozen reference to an Agent aggregate, kept inside :class:`Empire`."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    agent_id: AgentId
    name: NormalizedAgentName
    role: Role


# ---------------------------------------------------------------------------
# CompletionPolicy VO
# ---------------------------------------------------------------------------
type CompletionPolicyKind = Literal[
    "approved_by_reviewer",
    "all_checklist_checked",
    "manual",
]


class CompletionPolicy(BaseModel):
    """How a :class:`Stage` is judged complete (Workflow detailed-design §VO)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    kind: CompletionPolicyKind
    description: str = Field(default="", min_length=0, max_length=200)


# ---------------------------------------------------------------------------
# NotifyChannel VO (Workflow §Confirmation G — SSRF / A10 hardening)
# ---------------------------------------------------------------------------
type NotifyChannelKind = Literal["discord"]
"""MVP only accepts ``'discord'``. ``'slack'`` / ``'email'`` are deferred to
Phase 2 once their target normalization, SSRF rules, and secret-masking
contracts are frozen — see Workflow detailed-design §確定 G."""

# G7: anchored regex for the Discord webhook URL path.
# id  = 1〜30 digits (Discord snowflake range)
# tok = 1〜100 URL-safe characters (Base64 alphabet + '-' + '_')
_DISCORD_WEBHOOK_PATH_RE = re.compile(r"^/api/webhooks/[0-9]{1,30}/[A-Za-z0-9_\-]{1,100}$")


class NotifyChannel(BaseModel):
    """Webhook channel attached to ``EXTERNAL_REVIEW`` Stages.

    Implements ``§Confirmation G`` rules **G1〜G10** as a single
    ``field_validator`` over ``target`` so any one violation produces a
    ``pydantic.ValidationError`` *before* an instance is observable. The
    serializer downgrade to ``mode='json'`` masks the secret ``token`` segment
    (G "target のシークレット扱い").
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    kind: NotifyChannelKind
    target: str = Field(min_length=1, max_length=500)

    # G1 / G2 / G3 / G4 / G5 / G6 / G7 / G8 / G9 / G10 — single gate.
    @field_validator("target", mode="after")
    @classmethod
    def _validate_target(cls, target: str) -> str:
        # G2: parse via urllib.parse.urlparse (no startswith / regex shortcuts).
        parsed = urlparse(target)
        # G3: HTTPS only (urlparse already lowercases scheme).
        if parsed.scheme != "https":
            raise ValueError(
                f"NotifyChannel.target violates G3 (scheme): expected 'https', "
                f"got {parsed.scheme!r}"
            )
        # G4: hostname must be exactly 'discord.com' (urlparse lowercases host).
        if parsed.hostname != "discord.com":
            raise ValueError(
                f"NotifyChannel.target violates G4 (hostname): expected "
                f"'discord.com', got {parsed.hostname!r}"
            )
        # G5: port must be unset or 443.
        if parsed.port not in (None, 443):
            raise ValueError(
                f"NotifyChannel.target violates G5 (port): expected None or 443, "
                f"got {parsed.port!r}"
            )
        # G6: no userinfo — blocks 'https://attacker@discord.com/...' tricks.
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(
                "NotifyChannel.target violates G6 (userinfo): URL must not "
                "contain user/password info"
            )
        # G7 + G10: path must fullmatch the Discord webhook regex (case-sensitive).
        if not _DISCORD_WEBHOOK_PATH_RE.fullmatch(parsed.path):
            raise ValueError(
                "NotifyChannel.target violates G7/G10 (path): expected "
                "/api/webhooks/<id>/<token> (lowercase 'api/webhooks')"
            )
        # G8: query must be empty.
        if parsed.query != "":
            raise ValueError("NotifyChannel.target violates G8 (query): expected empty")
        # G9: fragment must be empty.
        if parsed.fragment != "":
            raise ValueError("NotifyChannel.target violates G9 (fragment): expected empty")
        return target

    # Mask the secret token segment whenever the VO is serialized to JSON
    # (model_dump(mode='json') / model_dump_json()). Default model_dump()
    # in Python mode preserves the raw target for in-process Workflow
    # manipulation; persistence/log boundaries always go through JSON mode.
    @field_serializer("target", when_used="json")
    def _serialize_target_masked(self, target: str) -> str:
        return mask_discord_webhook(target)


# ---------------------------------------------------------------------------
# AuditEntry VO (ExternalReviewGate feature §確定 K)
# ---------------------------------------------------------------------------
_AUDIT_COMMENT_MAX_CHARS: int = 2_000


class AuditEntry(BaseModel):
    """One row of an :class:`ExternalReviewGate.audit_trail`.

    Stored append-only inside a Gate aggregate; see
    ``docs/features/external-review-gate/detailed-design.md`` §確定 C.
    The "誰がいつ何度見たか" requirement (§確定 G) means every
    ``record_view`` call yields a fresh entry — same actor, same
    moment, same comment is **not** deduplicated. Fields stay narrow:

    * ``id`` — UUIDv4 distinguishes otherwise-equal entries.
    * ``actor_id`` — :class:`OwnerId` of the human who triggered the
      action.
    * ``action`` — :class:`AuditAction` discriminator (VIEWED /
      APPROVED / REJECTED / CANCELLED at MVP).
    * ``comment`` — free-form NFC-normalized text, 0〜2000 chars,
      **strip not applied** (the LLM stack-trace precedent carried
      through directive / task / agent applies here too).
    * ``occurred_at`` — UTC tz-aware moment.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: UUID
    actor_id: OwnerId
    action: AuditAction
    comment: str = Field(default="", max_length=_AUDIT_COMMENT_MAX_CHARS)
    occurred_at: datetime

    @field_validator("comment", mode="before")
    @classmethod
    def _normalize_comment(cls, value: object) -> object:
        # NFC only — preserves leading whitespace / multi-line context
        # (CEO comments may include indented quoting).
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("occurred_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "AuditEntry.occurred_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value


__all__ = [
    "AgentRef",
    "AuditEntry",
    "CompletionPolicy",
    "CompletionPolicyKind",
    "NotifyChannel",
    "NotifyChannelKind",
    "RoomRef",
]
