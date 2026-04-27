"""Shared domain value objects and ID types.

This module hosts identifiers, enums, and reference VOs that other Aggregates
in the bakufu domain depend on. Per ``docs/architecture/domain-model/value-objects.md``,
ID types are conceptually distinct UUIDv4 values; they are exposed as PEP 695
``type`` aliases over ``UUID`` to keep the surface minimal and Pydantic
serialization unambiguous. Future features may refine them via ``NewType``
without changing field shapes.

Two cross-cutting helpers live here so every Aggregate (Empire / Workflow /
Agent / ...) can share **single** implementations:

* :func:`nfc_strip` — name normalization pipeline (NFC → strip → length),
  fulfilling Empire detailed-design §Confirmation B and Workflow §Confirmation B.
* :func:`mask_discord_webhook` — replaces the secret ``token`` segment of a
  Discord webhook URL with ``<REDACTED:DISCORD_WEBHOOK>`` while preserving the
  ``id`` segment for audit traceability. Required by Workflow detailed-design
  §Confirmation G "target のシークレット扱い" and applied by Workflow exceptions
  + ``NotifyChannel.field_serializer(when_used='json')``.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Annotated, Literal, cast
from urllib.parse import urlparse
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

# ---------------------------------------------------------------------------
# Identifier types
# ---------------------------------------------------------------------------
type EmpireId = UUID
"""Empire aggregate identifier (UUIDv4 per domain-model/value-objects.md)."""

type RoomId = UUID
"""Room aggregate identifier (UUIDv4)."""

type AgentId = UUID
"""Agent aggregate identifier (UUIDv4)."""

type WorkflowId = UUID
"""Workflow aggregate identifier (UUIDv4)."""

type StageId = UUID
"""Stage entity identifier (within Workflow aggregate)."""

type TransitionId = UUID
"""Transition entity identifier (within Workflow aggregate)."""

type SkillId = UUID
"""Skill identifier (referenced by :class:`SkillRef` inside Agent aggregate)."""

type DirectiveId = UUID
"""Directive aggregate identifier (UUIDv4)."""

type TaskId = UUID
"""Task aggregate identifier (UUIDv4). Referenced by :class:`Directive`
via ``task_id``; the Task aggregate itself ships in a later feature."""


# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------
class Role(StrEnum):
    """Roles an :class:`AgentRef` can take.

    Mirrors the canonical list in ``docs/architecture/domain-model/value-objects.md``.
    Stored as ``str`` (StrEnum) so SQLite/JSON serialization is trivial in later
    persistence features without wrappers.
    """

    LEADER = "LEADER"
    DEVELOPER = "DEVELOPER"
    TESTER = "TESTER"
    REVIEWER = "REVIEWER"
    UX = "UX"
    SECURITY = "SECURITY"
    ASSISTANT = "ASSISTANT"
    DISCUSSANT = "DISCUSSANT"
    WRITER = "WRITER"
    SITE_ADMIN = "SITE_ADMIN"


class StageKind(StrEnum):
    """Workflow Stage kind per ``domain-model/value-objects.md`` §列挙型一覧."""

    WORK = "WORK"
    INTERNAL_REVIEW = "INTERNAL_REVIEW"
    EXTERNAL_REVIEW = "EXTERNAL_REVIEW"


class TransitionCondition(StrEnum):
    """Workflow Transition firing condition per ``domain-model/value-objects.md``."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONDITIONAL = "CONDITIONAL"
    TIMEOUT = "TIMEOUT"


class ProviderKind(StrEnum):
    """LLM provider per ``domain-model/value-objects.md`` §列挙型一覧.

    All six values are defined upfront so adding a new provider in Phase 2
    requires only an Adapter implementation + a ``BAKUFU_IMPLEMENTED_PROVIDERS``
    update — never an enum migration that would force every persisted Agent
    to be rebuilt (Agent feature §確定 I).
    """

    CLAUDE_CODE = "CLAUDE_CODE"
    CODEX = "CODEX"
    GEMINI = "GEMINI"
    OPENCODE = "OPENCODE"
    KIMI = "KIMI"
    COPILOT = "COPILOT"


# ---------------------------------------------------------------------------
# Name normalization (Confirmation B)
# ---------------------------------------------------------------------------
def nfc_strip(value: object) -> object:
    """Apply NFC normalization and ``strip`` per detailed-design §Confirmation B.

    Public so sibling Aggregates (Empire / Workflow / Agent / ...) can share
    the **single** implementation of the normalization pipeline. Operates only
    on ``str`` inputs; non-string values are passed through unchanged so
    Pydantic's downstream type validation reports them with its standard error
    shape rather than silently coercing.
    """
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value).strip()
    return value


# Public alias used by sibling VOs/Aggregates that adopt the same pipeline.
type NormalizedShortName = Annotated[
    str,
    BeforeValidator(nfc_strip),
    Field(min_length=1, max_length=80),
]
"""``str`` annotated with NFC+strip BeforeValidator and 1〜80-char Field bounds.

Used by :class:`RoomRef` and any future VO with the 80-char short-name contract.
"""

type NormalizedAgentName = Annotated[
    str,
    BeforeValidator(nfc_strip),
    Field(min_length=1, max_length=40),
]
"""1〜40-char variant for :class:`AgentRef` (Agent.name regulation)."""


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
# Discord webhook secret masking (Workflow §Confirmation G)
# ---------------------------------------------------------------------------
# Capture id (numeric) separately so it stays visible in audit/log output
# while only the token segment is redacted. Anchored loosely (no ^/$) so the
# pattern matches when the URL is embedded inside larger strings (exception
# detail dicts, JSON payloads, log lines).
_DISCORD_WEBHOOK_PATTERN = re.compile(
    r"https://discord\.com/api/webhooks/([0-9]+)/([A-Za-z0-9_\-]+)"
)
_DISCORD_WEBHOOK_REDACTED_TOKEN = "<REDACTED:DISCORD_WEBHOOK>"


def mask_discord_webhook(text: str) -> str:
    """Replace the secret ``token`` segment of every Discord webhook URL.

    Retains the snowflake ``id`` for traceability (audit_log can identify
    *which* webhook was involved) while redacting the credential segment.
    Idempotent: applying it twice yields the same result.
    """
    return _DISCORD_WEBHOOK_PATTERN.sub(
        rf"https://discord.com/api/webhooks/\1/{_DISCORD_WEBHOOK_REDACTED_TOKEN}",
        text,
    )


def mask_discord_webhook_in(value: object) -> object:
    """Recursively apply :func:`mask_discord_webhook` to strings within a value.

    Walks ``str`` / ``list`` / ``tuple`` / ``dict`` structures so nested
    diagnostic payloads (used in exception ``detail``) cannot leak a token
    via a list element or dict value. ``cast`` calls give pyright strict the
    element typing it cannot infer from a bare ``isinstance`` narrowing.
    """
    if isinstance(value, str):
        return mask_discord_webhook(value)
    if isinstance(value, list):
        items_list = cast("list[object]", value)
        return [mask_discord_webhook_in(item) for item in items_list]
    if isinstance(value, tuple):
        items_tuple = cast("tuple[object, ...]", value)
        return tuple(mask_discord_webhook_in(item) for item in items_tuple)
    if isinstance(value, dict):
        items_dict = cast("dict[object, object]", value)
        return {key: mask_discord_webhook_in(val) for key, val in items_dict.items()}
    return value


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


__all__ = [
    "AgentId",
    "AgentRef",
    "CompletionPolicy",
    "CompletionPolicyKind",
    "DirectiveId",
    "EmpireId",
    "NormalizedAgentName",
    "NormalizedShortName",
    "NotifyChannel",
    "NotifyChannelKind",
    "ProviderKind",
    "Role",
    "RoomId",
    "RoomRef",
    "SkillId",
    "StageId",
    "StageKind",
    "TaskId",
    "TransitionCondition",
    "TransitionId",
    "WorkflowId",
    "mask_discord_webhook",
    "mask_discord_webhook_in",
    "nfc_strip",
]
