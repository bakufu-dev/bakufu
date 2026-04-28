"""Shared domain value objects and ID types.

This module hosts identifiers, enums, and reference VOs that other Aggregates
in the bakufu domain depend on. Per ``docs/design/domain-model/value-objects.md``,
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
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
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
via ``task_id``; the Task aggregate itself ships in :mod:`bakufu.domain.task`."""

type OwnerId = UUID
"""Owner / Reviewer identifier (UUIDv4 per domain-model/value-objects.md).

Used by Task Aggregate behaviors that record an external-review actor
(``approve_review`` / ``reject_review`` / ``advance_to_next`` / ``complete`` /
``cancel``). The ``OwnerId`` is treated as opaque from the domain's point of
view; user-account binding is the application layer's job."""

type GateId = UUID
"""ExternalReviewGate aggregate identifier (UUIDv4).

The Gate is independent of Task (it has its own lifecycle, Tx
boundary, and supports multiple review rounds), so it carries its
own UUID rather than inheriting the parent ``TaskId`` —
external-review-gate detailed-design §確定 R1-A."""


# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------
class Role(StrEnum):
    """Roles an :class:`AgentRef` can take.

    Mirrors the canonical list in ``docs/design/domain-model/value-objects.md``.
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


class TaskStatus(StrEnum):
    """Task lifecycle status per ``domain-model/value-objects.md`` §列挙型一覧.

    Six values, frozen by ``docs/features/task/detailed-design.md`` §確定 A-2
    dispatch table. The ordering here matches the natural lifecycle progression
    (PENDING → IN_PROGRESS → terminal) so iterating over the enum in tests
    hits the realistic state walk.
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_EXTERNAL_REVIEW = "AWAITING_EXTERNAL_REVIEW"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class LLMErrorKind(StrEnum):
    """Coarse LLM-Adapter error classification per ``domain-model/value-objects.md``.

    Used by application-layer dispatch / monitoring to decide retry vs
    Task BLOCK. The Task aggregate itself does not reference this enum —
    the value reaches it as a pre-built ``last_error`` string — but it
    lives in the shared VO module because the Adapter feature and the
    Admin CLI both need the same enum surface.
    """

    SESSION_LOST = "SESSION_LOST"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class ReviewDecision(StrEnum):
    """ExternalReviewGate decision outcome per ``domain-model/value-objects.md``.

    Four values, frozen by
    ``docs/features/external-review-gate/detailed-design.md`` §確定 A
    dispatch table. ``PENDING`` → 1 of {``APPROVED`` / ``REJECTED`` /
    ``CANCELLED``} once-only; the three terminal values may not
    transition further (the state machine table refuses any
    ``approve`` / ``reject`` / ``cancel`` action from non-PENDING).
    ``record_view`` self-loops on every value (audit trail allows
    reads even after a Gate is decided — §確定 G).
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AuditAction(StrEnum):
    """Audit log action discriminator per ``domain-model/value-objects.md``.

    The MVP needs four values for the ExternalReviewGate aggregate
    (``VIEWED`` from ``record_view`` plus ``APPROVED`` / ``REJECTED``
    / ``CANCELLED`` mirroring the decision transitions); the
    remaining six values frozen in
    ``docs/design/domain-model/value-objects.md`` §列挙型一覧
    (``RETRIED`` / ``ADMIN_RETRY_TASK`` / ``ADMIN_CANCEL_TASK`` /
    ``ADMIN_RETRY_EVENT`` / ``ADMIN_LIST_BLOCKED`` /
    ``ADMIN_LIST_DEAD_LETTERS``) join when the Admin CLI feature
    lands. Adding them here ahead of time would advertise an enum
    contract no production code consumes yet — wait until they're
    needed (YAGNI, agent feature §確定 I 同方針).
    """

    VIEWED = "VIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


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


# ---------------------------------------------------------------------------
# Attachment / Deliverable VOs (Task feature §確定 R1-E)
# ---------------------------------------------------------------------------
# §Attachment storage.md 凍結値. Mirror them as module-level constants so the
# field validators read clearly and tests can import the same source.
_ATTACHMENT_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_ATTACHMENT_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MiB
_ATTACHMENT_MAX_FILENAME_CHARS: int = 255
_ATTACHMENT_FILENAME_REJECTED_CHARS: frozenset[str] = frozenset(
    {"/", "\\", "\0"} | {chr(c) for c in range(0x00, 0x20)} | {chr(0x7F)}
)
# Windows reserved device names — case-insensitive, with or without extensions.
_ATTACHMENT_WINDOWS_RESERVED: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
# Whitelist per storage.md §MIME タイプ検証 (text/html / text/csv 拒否).
_ATTACHMENT_MIME_WHITELIST: frozenset[str] = frozenset(
    {
        "text/markdown",
        "text/plain",
        "application/json",
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
        "application/octet-stream",
    }
)
_DELIVERABLE_BODY_MAX_CHARS: int = 1_000_000


class Attachment(BaseModel):
    """File reference held inside :class:`Deliverable`.

    Implements the storage.md §filename サニタイズ規則 6 段階, the MIME
    whitelist, the 10 MiB byte cap, and the 64-hex sha256 contract per
    Task detailed-design §VO: Attachment. The Aggregate (Task) does not
    re-validate these — the VO ``model_validator(mode='after')`` is the
    single gate so a hydration path (Repository round-trip) hits the same
    checks as construction time.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    sha256: str
    filename: str
    mime_type: str
    size_bytes: int

    @field_validator("sha256", mode="after")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if not _ATTACHMENT_SHA256_RE.fullmatch(value):
            raise ValueError(
                "Attachment.sha256 must match ^[a-f0-9]{64}$ (lowercase hex, 64 chars)"
            )
        return value

    @field_validator("filename", mode="before")
    @classmethod
    def _normalize_filename(cls, value: object) -> object:
        # Storage.md §filename サニタイズ規則 step 1-2: NFC normalize first
        # so the length / character checks below see the canonical form.
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value

    @field_validator("filename", mode="after")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        # Step 1: length (NFC-normalized code-point count).
        length = len(value)
        if not (1 <= length <= _ATTACHMENT_MAX_FILENAME_CHARS):
            raise ValueError(
                f"Attachment.filename must be 1-{_ATTACHMENT_MAX_FILENAME_CHARS} "
                f"NFC-normalized characters (got length={length})"
            )
        # Step 3: rejected characters (path separators, NUL, control chars).
        bad_chars = sorted({ch for ch in value if ch in _ATTACHMENT_FILENAME_REJECTED_CHARS})
        if bad_chars:
            raise ValueError(
                f"Attachment.filename contains rejected characters: {bad_chars!r} "
                "(path separators / NUL / ASCII control chars are not allowed)"
            )
        # Step 4: rejected sequences.
        if ".." in value:
            raise ValueError("Attachment.filename must not contain '..' (path traversal sequence)")
        if value.startswith(".") or value.endswith("."):
            raise ValueError(
                "Attachment.filename must not start or end with '.' "
                "(Windows / POSIX hidden / extension trick)"
            )
        if value != value.strip():
            raise ValueError("Attachment.filename must not start or end with whitespace")
        if ":" in value:
            raise ValueError(
                "Attachment.filename must not contain ':' (Windows ADS / drive-letter trick)"
            )
        # Step 5: Windows reserved device names (with or without extension).
        stem = value.split(".", 1)[0].upper()
        if stem in _ATTACHMENT_WINDOWS_RESERVED:
            raise ValueError(f"Attachment.filename uses a reserved Windows device name: {stem!r}")
        # Step 6: basename round-trip (path-traversal double-defense).
        # ``PurePosixPath`` reads ``/`` as a separator regardless of the
        # host OS, mirroring the storage.md sanitization rule which
        # rejects POSIX path components by design.
        if PurePosixPath(value).name != value:
            raise ValueError(
                "Attachment.filename must equal its basename (path components are not allowed)"
            )
        return value

    @field_validator("mime_type", mode="after")
    @classmethod
    def _validate_mime(cls, value: str) -> str:
        if value not in _ATTACHMENT_MIME_WHITELIST:
            raise ValueError(
                f"Attachment.mime_type must be one of "
                f"{sorted(_ATTACHMENT_MIME_WHITELIST)!r} (got {value!r}); "
                "text/html and text/csv are rejected by storage.md."
            )
        return value

    @field_validator("size_bytes", mode="after")
    @classmethod
    def _validate_size(cls, value: int) -> int:
        if not (0 <= value <= _ATTACHMENT_MAX_BYTES):
            raise ValueError(
                f"Attachment.size_bytes must satisfy 0 <= size <= "
                f"{_ATTACHMENT_MAX_BYTES} (got {value})"
            )
        return value


class Deliverable(BaseModel):
    """Per-Stage deliverable snapshot held inside :class:`Task`.

    The Aggregate Root keeps a ``dict[StageId, Deliverable]`` so the
    "Stage ごとに最新 1 件" contract (Task detailed-design §確定 R1-E)
    is enforced by Python dict semantics. ``body_markdown`` is the
    raw CEO/Agent-authored content — masking happens at the Repository
    layer (``MaskedText`` TypeDecorator on ``task_deliverables.body_markdown``,
    landed in ``feature/task-repository``).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    stage_id: StageId
    body_markdown: str = Field(default="", max_length=_DELIVERABLE_BODY_MAX_CHARS)
    attachments: list[Attachment] = []
    committed_by: AgentId
    committed_at: datetime

    @field_validator("committed_at", mode="after")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Deliverable.committed_at must be a timezone-aware UTC datetime "
                "(received a naive datetime)"
            )
        return value


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
    "AgentId",
    "AgentRef",
    "Attachment",
    "AuditAction",
    "AuditEntry",
    "CompletionPolicy",
    "CompletionPolicyKind",
    "Deliverable",
    "DirectiveId",
    "EmpireId",
    "GateId",
    "LLMErrorKind",
    "NormalizedAgentName",
    "NormalizedShortName",
    "NotifyChannel",
    "NotifyChannelKind",
    "OwnerId",
    "ProviderKind",
    "ReviewDecision",
    "Role",
    "RoomId",
    "RoomRef",
    "SkillId",
    "StageId",
    "StageKind",
    "TaskId",
    "TaskStatus",
    "TransitionCondition",
    "TransitionId",
    "WorkflowId",
    "mask_discord_webhook",
    "mask_discord_webhook_in",
    "nfc_strip",
]
