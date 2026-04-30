"""共有ドメイン Value Object および ID 型。

このパッケージは bakufu ドメイン内の他 Aggregate が依存する識別子、enum、
参照 VO を集約する。``docs/design/domain-model/value-objects.md`` によれば、
ID 型は概念的に区別される UUIDv4 値である。表面を最小に保ち Pydantic の
シリアライズを曖昧にしないため、これらは ``UUID`` 上の PEP 695 ``type``
エイリアスとして公開する。

サブモジュール:
- :mod:`.identifiers` — ID 型エイリアス（EmpireId、AgentId 等）
- :mod:`.enums` — StrEnum 定義（Role、GateDecision 等）
- :mod:`.gate_role` — GateRole 検証済み slug 型エイリアス
- :mod:`.verdict` — Verdict VO および _VERDICT_COMMENT_MAX_CHARS
- :mod:`.helpers` — nfc_strip / mask_discord_webhook / NormalizedShortName 等
- :mod:`.references` — RoomRef / AgentRef / CompletionPolicy / NotifyChannel /
  AuditEntry
- :mod:`.attachments` — Attachment / Deliverable VO
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
    TemplateType,
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
    DeliverableTemplateId,
    DirectiveId,
    EmpireId,
    GateId,
    InternalGateId,
    OwnerId,
    RoleProfileId,
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
from bakufu.domain.value_objects.template_vos import (
    AcceptanceCriterion,
    DeliverableRequirement,
    DeliverableTemplateRef,
    SemVer,
)
from bakufu.domain.value_objects.verdict import (
    _VERDICT_COMMENT_MAX_CHARS,
    Verdict,
)

__all__ = [
    "_VERDICT_COMMENT_MAX_CHARS",
    "AcceptanceCriterion",
    "AgentId",
    "AgentRef",
    "Attachment",
    "AuditAction",
    "AuditEntry",
    "CompletionPolicy",
    "CompletionPolicyKind",
    "Deliverable",
    "DeliverableRequirement",
    "DeliverableTemplateId",
    "DeliverableTemplateRef",
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
    "RoleProfileId",
    "RoomId",
    "RoomRef",
    "SemVer",
    "SkillId",
    "StageId",
    "StageKind",
    "TaskId",
    "TaskStatus",
    "TemplateType",
    "TransitionCondition",
    "TransitionId",
    "Verdict",
    "VerdictDecision",
    "WorkflowId",
    "mask_discord_webhook",
    "mask_discord_webhook_in",
    "nfc_strip",
]
