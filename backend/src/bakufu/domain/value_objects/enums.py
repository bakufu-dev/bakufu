"""StrEnum definitions shared across the bakufu domain.

All enums here are ``StrEnum`` so SQLite/JSON serialization is trivial without
wrappers. Ordering within each enum matches the natural lifecycle progression
where applicable (PENDING → terminal) so iteration in tests hits the realistic
state walk.
"""

from __future__ import annotations

from enum import StrEnum


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


class GateDecision(StrEnum):
    """InternalReviewGate overall decision per ``domain-model/value-objects.md``.

    Three values matching the internal-review-gate state machine:

    * ``PENDING`` — one or more required roles have not submitted a
      verdict yet, or no REJECTED verdict has been received.
    * ``ALL_APPROVED`` — every required GateRole has submitted an
      APPROVED verdict and none has rejected.
    * ``REJECTED`` — at least one verdict carries
      :attr:`VerdictDecision.REJECTED` (most-pessimistic-wins rule).

    Unlike :class:`ReviewDecision`, there is no ``CANCELLED`` value
    because InternalReviewGate cancellation (Stage reassignment) is
    handled at the Workflow / Task layer, not inside the Gate itself.
    """

    PENDING = "PENDING"
    ALL_APPROVED = "ALL_APPROVED"
    REJECTED = "REJECTED"


class VerdictDecision(StrEnum):
    """Per-role verdict submitted to an :class:`InternalReviewGate`.

    Two values only — an agent either approves or rejects the
    deliverable. Abstaining is not supported; the state machine
    treats a missing verdict the same as "not yet submitted"
    (``GateDecision.PENDING`` until all required roles vote).
    """

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


__all__ = [
    "AuditAction",
    "GateDecision",
    "LLMErrorKind",
    "ProviderKind",
    "ReviewDecision",
    "Role",
    "StageKind",
    "TaskStatus",
    "TransitionCondition",
    "VerdictDecision",
]
