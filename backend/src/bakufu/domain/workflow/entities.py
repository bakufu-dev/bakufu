"""Workflow inner Entities: :class:`Stage` and :class:`Transition`.

Both are Pydantic v2 frozen models. They live separately from
:mod:`bakufu.domain.workflow.workflow` so the file-level boundary mirrors the
*responsibility* boundary the design document calls out:

* Entities own **self**-invariants (Stage's ``required_role`` non-empty and
  ``EXTERNAL_REVIEW`` notify_channels rule). These fire even when the entity
  is constructed standalone (preset definition, factory) so violations are
  caught before a Workflow ever sees the value.
* The Aggregate Root owns **collection** invariants (DAG, uniqueness,
  capacity). Those are implemented as pure functions in
  :mod:`bakufu.domain.workflow.dag_validators` so the file-level boundary
  enforces "Stage self-validation does not share code with the aggregate
  helpers" — the physical ground for Confirmation F's twin-defense.
"""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import StageInvariantViolation
from bakufu.domain.value_objects import (
    CompletionPolicy,
    NotifyChannel,
    Role,
    StageId,
    StageKind,
    TransitionCondition,
    TransitionId,
    nfc_strip,
)


class Stage(BaseModel):
    """Workflow stage with **self**-invariants checked in ``model_validator``.

    Self-check raises :class:`StageInvariantViolation` so a Stage built outside
    a Workflow (e.g. preset definition, factory) still surfaces violations
    early. The Workflow aggregate later re-validates the same conditions in
    :func:`bakufu.domain.workflow.dag_validators._validate_external_review_notify`
    and ``_validate_required_role_non_empty`` — the dual path is by design
    (Confirmation F twin-defense).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: StageId
    name: str = Field(min_length=1, max_length=80)
    kind: StageKind
    required_role: frozenset[Role]
    deliverable_template: str = Field(default="", max_length=10_000)
    completion_policy: CompletionPolicy
    notify_channels: list[NotifyChannel] = []

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_self_invariants(self) -> Self:
        # REQ-WF-007-① required_role non-empty (MSG-WF-007).
        if not self.required_role:
            raise StageInvariantViolation(
                kind="empty_required_role",
                message=f"[FAIL] Stage {self.id} required_role must not be empty",
                detail={"stage_id": str(self.id)},
            )
        # REQ-WF-007-② EXTERNAL_REVIEW must declare notify_channels (MSG-WF-006).
        if self.kind is StageKind.EXTERNAL_REVIEW and not self.notify_channels:
            raise StageInvariantViolation(
                kind="missing_notify",
                message=(
                    f"[FAIL] EXTERNAL_REVIEW stage {self.id} must have at least one notify_channel"
                ),
                detail={"stage_id": str(self.id)},
            )
        return self


class Transition(BaseModel):
    """Directed edge between two Stages. Reference integrity is the aggregate's job.

    Transition holds no self-invariants beyond Pydantic field-level type
    coercion: its meaning depends on the surrounding ``stages`` collection,
    so structural validation lives in
    :func:`bakufu.domain.workflow.dag_validators._validate_transition_refs`
    and ``_validate_transition_determinism``.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: TransitionId
    from_stage_id: StageId
    to_stage_id: StageId
    condition: TransitionCondition
    label: str = Field(default="", max_length=80)


__all__ = [
    "Stage",
    "Transition",
]
