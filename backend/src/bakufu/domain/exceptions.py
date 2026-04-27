"""Domain exceptions for the bakufu domain layer.

Each violation carries a structured ``kind`` discriminator alongside a
human-readable ``message`` and a ``detail`` dict for programmatic introspection
(used by HTTP API mappers and tests).

* :class:`EmpireInvariantViolation` — empire feature, see
  ``docs/features/empire/detailed-design.md`` §Exception.
* :class:`WorkflowInvariantViolation` — workflow feature, see
  ``docs/features/workflow/detailed-design.md`` §Exception.
* :class:`StageInvariantViolation` — workflow Stage entity-level violation,
  inherits from :class:`WorkflowInvariantViolation` so callers can ``except``
  the parent and still receive the more-specific subclass.
* :class:`AgentInvariantViolation` — agent feature, see
  ``docs/features/agent/detailed-design.md`` §Exception.
* :class:`RoomInvariantViolation` — room feature, see
  ``docs/features/room/detailed-design.md`` §Exception.

Workflow / Agent / Room violations automatically apply
:func:`mask_discord_webhook_in` to both ``message`` and ``detail`` so a
webhook secret can never leak through exception text or its diagnostic
payload — multi-layer defense covering webhook URLs that may slip into
``NotifyChannel.target`` / ``Persona.prompt_body`` / ``SkillRef.path`` /
``PromptKit.prefix_markdown`` / ``Room.{name,description}``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from bakufu.domain.value_objects import mask_discord_webhook, mask_discord_webhook_in

type EmpireViolationKind = Literal[
    "name_range",
    "agent_duplicate",
    "room_duplicate",
    "room_not_found",
    "capacity_exceeded",
]
"""Discriminator for ``EmpireInvariantViolation`` matching detailed-design §Exception."""


# Domain naming convention follows DDD: "Violation" expresses an invariant breach,
# not a programming error. The N818 "Error suffix" rule does not apply here.
class EmpireInvariantViolation(Exception):  # noqa: N818
    """Raised when an :class:`Empire` aggregate invariant is violated.

    Pydantic v2's ``model_validator(mode='after')`` re-raises non-``ValueError`` /
    non-``AssertionError`` exceptions without wrapping them in ``ValidationError``,
    so callers receive this exception directly with full ``kind`` / ``detail``
    structure intact.

    Attributes:
        kind: One of the canonical violation discriminators in
            :data:`EmpireViolationKind`. Stable string values used by tests
            and HTTP API mappers; never localized.
        message: The full ``[FAIL] ...`` user-facing string per
            ``MSG-EM-001``〜``MSG-EM-005`` in detailed-design §MSG.
        detail: Structured context (UUIDs, lengths, counts) for diagnostics
            and audit logging. Stored as a fresh ``dict`` copy to keep the
            exception immutable from the caller's view.
    """

    def __init__(
        self,
        *,
        kind: EmpireViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: EmpireViolationKind = kind
        self.message: str = message
        self.detail: dict[str, object] = dict(detail) if detail else {}


type WorkflowViolationKind = Literal[
    "name_range",
    "entry_not_in_stages",
    "transition_ref_invalid",
    "transition_duplicate",
    "transition_id_duplicate",
    "unreachable_stage",
    "no_sink_stage",
    "capacity_exceeded",
    "stage_duplicate",
    "cannot_remove_entry",
    "stage_not_found",
    "missing_notify_aggregate",
    "empty_required_role_aggregate",
    "from_dict_invalid",
]
"""Discriminator for :class:`WorkflowInvariantViolation` matching workflow
detailed-design §Exception. The list extends the design's 11 canonical kinds
with three operational discriminators that surface in MSG-WF-001 / MSG-WF-008
(``name_range`` / ``stage_duplicate``) and the symmetric ``transition_id_duplicate``
that mirrors ``stage_duplicate`` for the Transition collection contract
(detailed-design §Aggregate Root: Workflow row ``transitions: 0〜60 件、
transition_id の重複なし``)."""


type StageViolationKind = Literal[
    "empty_required_role",
    "missing_notify",
]
"""Discriminator for :class:`StageInvariantViolation` (Workflow detailed-design)."""


# DDD: "Violation" describes an invariant breach, not a programming bug, so
# the N818 "Error suffix" rule does not apply here.
class WorkflowInvariantViolation(Exception):  # noqa: N818
    """Raised when a :class:`Workflow` aggregate invariant is violated.

    All ``message`` / ``detail`` strings are passed through
    :func:`mask_discord_webhook_in` at construction time so the secret
    ``token`` segment of any embedded Discord webhook URL is replaced with
    ``<REDACTED:DISCORD_WEBHOOK>``. This makes it impossible for downstream
    log/audit consumers to leak a webhook credential just by serializing
    the exception (Workflow detailed-design §確定 G "target のシークレット扱い"
    line "例外 message / detail").
    """

    def __init__(
        self,
        *,
        kind: WorkflowViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: WorkflowViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


# Subclass so ``except WorkflowInvariantViolation`` catches Stage-level
# violations too (the aggregate path may delegate to Stage's own validator,
# and callers should handle both uniformly).
class StageInvariantViolation(WorkflowInvariantViolation):
    """Raised by :class:`Stage` self-validation (independent of the aggregate).

    ``kind`` narrows to :data:`StageViolationKind` but the surrounding
    ``WorkflowInvariantViolation`` type contract is preserved — including
    secret masking on ``message`` / ``detail``.
    """

    def __init__(
        self,
        *,
        kind: StageViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        # Forward to parent so masking and the discriminator field are
        # populated identically. Re-narrow self.kind for the static type.
        super().__init__(
            kind=kind,  # type: ignore[arg-type]
            message=message,
            detail=detail,
        )
        self.kind: StageViolationKind = kind  # type: ignore[assignment]


type AgentViolationKind = Literal[
    "name_range",
    "no_provider",
    "default_not_unique",
    "provider_duplicate",
    "persona_too_long",
    "provider_not_found",
    "skill_duplicate",
    "skill_not_found",
    "skill_path_invalid",
    "archetype_too_long",
    "display_name_range",
    "provider_not_implemented",
    "skill_capacity_exceeded",
    "provider_capacity_exceeded",
]
"""Discriminator for :class:`AgentInvariantViolation` per Agent detailed-design
§Exception. Extends the design's 12 documented kinds with two operational
``*_capacity_exceeded`` discriminators that surface the §確定 C bounds
(providers ≤ 10, skills ≤ 20) — without them the same MSG would have to
double up an existing kind and lose discrimination at the HTTP API layer."""


# DDD: "Violation" describes an invariant breach, not a programming bug, so
# the N818 "Error suffix" rule does not apply here.
class AgentInvariantViolation(Exception):  # noqa: N818
    """Raised when an :class:`Agent` aggregate invariant is violated.

    Mirrors :class:`EmpireInvariantViolation` in shape (``kind`` + ``message``
    + ``detail`` + immutable copy of detail) and applies the same Discord
    webhook secret masking that :class:`WorkflowInvariantViolation` uses, so
    if a SkillRef.path or Persona.prompt_body ever happens to contain a
    Discord webhook URL fragment it cannot leak through exception text.
    """

    def __init__(
        self,
        *,
        kind: AgentViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: AgentViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type RoomViolationKind = Literal[
    "name_range",
    "description_too_long",
    "member_duplicate",
    "capacity_exceeded",
    "member_not_found",
    "room_archived",
]
"""Discriminator for :class:`RoomInvariantViolation` per Room detailed-design
§Exception (§確定 I 例外型統一規約).

The set is **closed at six kinds**: ``prompt_kit_too_long`` is *intentionally
omitted* because the PromptKit VO raises :class:`pydantic.ValidationError`
on its own ``model_validator`` before any Room invariant check fires. Adding
it here would create a dead-code path that ``RoomInvariantViolation`` cannot
reach by construction — see Room detailed-design §確定 I 2 段階 catch.
"""


# DDD: "Violation" describes an invariant breach, not a programming bug, so
# the N818 "Error suffix" rule does not apply here.
class RoomInvariantViolation(Exception):  # noqa: N818
    """Raised when a :class:`Room` aggregate invariant is violated.

    Mirrors :class:`AgentInvariantViolation` / :class:`WorkflowInvariantViolation`
    in shape (``kind`` + ``message`` + ``detail`` + immutable copy of detail) and
    applies the same Discord webhook secret masking. ``Room.name`` /
    ``Room.description`` / ``PromptKit.prefix_markdown`` may all carry user-pasted
    text that contains a webhook URL, so masking ``message`` / ``detail`` at
    construction time means callers cannot leak a token by serializing the
    exception (multi-layer defense, see Room detailed-design §確定 H).
    """

    def __init__(
        self,
        *,
        kind: RoomViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: RoomViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type DirectiveViolationKind = Literal[
    "text_range",
    "task_already_linked",
]
"""Discriminator for :class:`DirectiveInvariantViolation` per Directive
detailed-design §確定 F.

The set is **closed at two kinds**. Type / required-field violations
surface as :class:`pydantic.ValidationError` (MSG-DR-003) and the
``$``-prefix normalization is an application-layer responsibility
(``DirectiveService.issue()``), so neither leaks into the aggregate's
discriminator namespace.
"""


# DDD: "Violation" describes an invariant breach, not a programming bug, so
# the N818 "Error suffix" rule does not apply here.
class DirectiveInvariantViolation(Exception):  # noqa: N818
    """Raised when a :class:`Directive` aggregate invariant is violated.

    Mirrors :class:`RoomInvariantViolation` / :class:`AgentInvariantViolation`
    in shape (``kind`` + ``message`` + ``detail`` + immutable copy of
    detail) and applies the same Discord webhook secret masking.
    ``Directive.text`` is user-pasted CEO directive content that may
    embed a webhook URL, so masking ``message`` / ``detail`` at
    construction time means callers cannot leak a token by serializing
    the exception (multi-layer defense, see Directive detailed-design
    §確定 E).
    """

    def __init__(
        self,
        *,
        kind: DirectiveViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: DirectiveViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type TaskViolationKind = Literal[
    "terminal_violation",
    "state_transition_invalid",
    "assigned_agents_unique",
    "assigned_agents_capacity",
    "last_error_consistency",
    "blocked_requires_last_error",
    "timestamp_order",
]
"""Discriminator for :class:`TaskInvariantViolation` per Task detailed-design
§確定 J. The closed set of seven kinds covers terminal violation, state-machine
bypass, the four structural invariants enforced by ``model_validator(mode='after')``,
and the timestamp-order check. Type / required-field violations surface as
``pydantic.ValidationError`` (MSG-TS-008 / MSG-TS-009) and never leak into this
discriminator namespace."""


# DDD: "Violation" describes an invariant breach, not a programming bug, so
# the N818 "Error suffix" rule does not apply here.
class TaskInvariantViolation(Exception):  # noqa: N818
    """Raised when a :class:`Task` aggregate invariant is violated.

    Mirrors :class:`DirectiveInvariantViolation` /
    :class:`RoomInvariantViolation` /
    :class:`AgentInvariantViolation` /
    :class:`WorkflowInvariantViolation` in shape (``kind`` + ``message``
    + ``detail`` + immutable copy of detail) and applies the same Discord
    webhook secret masking. ``Task.last_error`` may carry an LLM-Adapter
    stack trace that includes a webhook URL (the MVP runs Discord
    notifications), and ``Deliverable.body_markdown`` is CEO / Agent
    authored content; both can land in ``message`` / ``detail`` via
    ``state_transition_invalid`` or ``last_error_consistency`` paths, so
    masking ``message`` / ``detail`` at construction time means callers
    cannot leak a token by serializing the exception (multi-layer defense,
    see Task detailed-design §確定 I).
    """

    def __init__(
        self,
        *,
        kind: TaskViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: TaskViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


type ExternalReviewGateViolationKind = Literal[
    "decision_already_decided",
    "decided_at_inconsistent",
    "snapshot_immutable",
    "feedback_text_range",
    "audit_trail_append_only",
]
"""Discriminator for :class:`ExternalReviewGateInvariantViolation` per
external-review-gate detailed-design §確定 I. The closed set of five
kinds covers state-machine bypass (PENDING-only decision transitions),
the four ``model_validator(mode='after')`` structural invariants, and
the audit-trail append-only contract. Type / required-field violations
surface as :class:`pydantic.ValidationError` (MSG-GT-006) so they never
leak into this discriminator namespace."""


# DDD: "Violation" describes an invariant breach, not a programming bug, so
# the N818 "Error suffix" rule does not apply here.
class ExternalReviewGateInvariantViolation(Exception):  # noqa: N818
    """Raised when an :class:`ExternalReviewGate` aggregate invariant is violated.

    Mirrors :class:`TaskInvariantViolation` /
    :class:`DirectiveInvariantViolation` /
    :class:`RoomInvariantViolation` /
    :class:`AgentInvariantViolation` /
    :class:`WorkflowInvariantViolation` in shape (``kind`` +
    ``message`` + ``detail`` + immutable copy of detail) and applies
    the same Discord webhook secret masking. Gate ``feedback_text``
    and ``audit_trail.comment`` are CEO-authored fields that may
    embed a webhook URL pasted from a Discord channel; masking
    ``message`` / ``detail`` at construction time means callers
    cannot leak a token by serializing the exception (multi-layer
    defense, see external-review-gate detailed-design §確定 H).
    """

    def __init__(
        self,
        *,
        kind: ExternalReviewGateViolationKind,
        message: str,
        detail: Mapping[str, object] | None = None,
    ) -> None:
        masked_message = mask_discord_webhook(message)
        masked_detail: dict[str, object] = (
            {key: mask_discord_webhook_in(value) for key, value in detail.items()} if detail else {}
        )
        super().__init__(masked_message)
        self.kind: ExternalReviewGateViolationKind = kind
        self.message: str = masked_message
        self.detail: dict[str, object] = masked_detail


__all__ = [
    "AgentInvariantViolation",
    "AgentViolationKind",
    "DirectiveInvariantViolation",
    "DirectiveViolationKind",
    "EmpireInvariantViolation",
    "EmpireViolationKind",
    "ExternalReviewGateInvariantViolation",
    "ExternalReviewGateViolationKind",
    "RoomInvariantViolation",
    "RoomViolationKind",
    "StageInvariantViolation",
    "StageViolationKind",
    "TaskInvariantViolation",
    "TaskViolationKind",
    "WorkflowInvariantViolation",
    "WorkflowViolationKind",
]
