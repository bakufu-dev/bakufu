"""Domain exceptions for the bakufu domain layer.

Per ``docs/features/empire/detailed-design.md`` §Exception, ``EmpireInvariantViolation``
carries a structured ``kind`` discriminator alongside a human-readable ``message`` and
a ``detail`` dict for programmatic introspection (used by HTTP API mappers and tests).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

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


__all__ = [
    "EmpireInvariantViolation",
    "EmpireViolationKind",
]
