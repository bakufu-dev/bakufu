"""Shared domain value objects and ID types.

This package hosts identifiers, enums, and reference VOs that other Aggregates
in the bakufu domain depend on. Per ``docs/design/domain-model/value-objects.md``,
ID types are conceptually distinct UUIDv4 values; they are exposed as PEP 695
``type`` aliases over ``UUID`` to keep the surface minimal and Pydantic
serialization unambiguous.

Sub-modules:
- :mod:`.identifiers` — ID type aliases (EmpireId, AgentId, etc.)
- :mod:`.enums` — StrEnum definitions (Role, GateDecision, etc.)
- :mod:`.gate_role` — GateRole validated slug type alias
- :mod:`.verdict` — Verdict VO and _VERDICT_COMMENT_MAX_CHARS
- :mod:`.helpers` — nfc_strip / mask_discord_webhook / NormalizedShortName etc.
- :mod:`.references` — RoomRef / AgentRef / CompletionPolicy / NotifyChannel / AuditEntry
- :mod:`.attachments` — Attachment / Deliverable VOs
"""

from __future__ import annotations

from bakufu.domain.value_objects.attachments import Attachment, Deliverable
from bakufu.domain.value_objects.enums import (
    AuditAction,
    GateDecision,
    LLMErrorKind,
    ProviderKind,
    ReviewDecision,
    Role,
    StageKind,
    TaskStatus,
    TransitionCondition,
    VerdictDecision,
)
from bakufu.domain.value_objects.gate_role import GateRole
from bakufu.domain.value_objects.helpers import (
    NormalizedAgentName,
    NormalizedShortName,
    mask_discord_webhook,
    mask_discord_webhook_in,
    nfc_strip,
)
from bakufu.domain.value_objects.identifiers import (
    AgentId,
    DirectiveId,
    EmpireId,
    GateId,
    InternalGateId,
    OwnerId,
    RoomId,
    SkillId,
    StageId,
    TaskId,
    TransitionId,
    WorkflowId,
)
from bakufu.domain.value_objects.references import (
    AgentRef,
    AuditEntry,
    CompletionPolicy,
    CompletionPolicyKind,
    NotifyChannel,
    NotifyChannelKind,
    RoomRef,
)
from bakufu.domain.value_objects.verdict import (
    _VERDICT_COMMENT_MAX_CHARS,
    Verdict,
)

__all__ = [
    "_VERDICT_COMMENT_MAX_CHARS",
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
    "GateDecision",
    "GateId",
    "GateRole",
    "InternalGateId",
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
    "Verdict",
    "VerdictDecision",
    "WorkflowId",
    "mask_discord_webhook",
    "mask_discord_webhook_in",
    "nfc_strip",
]
