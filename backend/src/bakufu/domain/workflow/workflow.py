"""Workflow Aggregate Root (REQ-WF-001〜006).

This module owns only the :class:`Workflow` class itself. The 10 invariant
helpers it dispatches over live in
:mod:`bakufu.domain.workflow.dag_validators`, and the inner Entities live in
:mod:`bakufu.domain.workflow.entities`. The directory split is the *physical*
ground for Confirmation F's twin-defense: aggregate-level checks cannot share
code with Stage self-validation because they don't even share a file.

Design contract (do not break without re-running design review):

* **Pre-validate rebuild (Confirmation A)** — every state-changing behavior
  serializes via ``model_dump()``, swaps the target collection, and re-runs
  ``Workflow.model_validate(...)``. ``model_copy(update=...)`` is intentionally
  avoided because Pydantic v2 defaults it to ``validate=False``.
* **NotifyChannel SSRF / token masking (Confirmation G)** — handled inside
  :class:`bakufu.domain.value_objects.NotifyChannel`; this module consumes
  the validated VO without re-checking URL shape.
"""

from __future__ import annotations

from typing import Any, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import (
    StageInvariantViolation,
    WorkflowInvariantViolation,
)
from bakufu.domain.value_objects import StageId, WorkflowId, nfc_strip
from bakufu.domain.workflow.dag_validators import (
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    _validate_capacity,
    _validate_dag_reachability,
    _validate_dag_sink_exists,
    _validate_entry_in_stages,
    _validate_external_review_notify,
    _validate_required_role_non_empty,
    _validate_stage_id_unique,
    _validate_transition_determinism,
    _validate_transition_id_unique,
    _validate_transition_refs,
)
from bakufu.domain.workflow.entities import Stage, Transition


class Workflow(BaseModel):
    """V-model orchestration graph composed of Stages and Transitions."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=False,
    )

    id: WorkflowId
    name: str
    stages: list[Stage]
    transitions: list[Transition] = []
    entry_stage_id: StageId

    # ---- pre-validation -------------------------------------------------
    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        return nfc_strip(value)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        """Dispatch over the aggregate-level helpers in deterministic order.

        Order matters for failure attribution: capacity → uniqueness →
        reference integrity → semantic (notify / required_role) → graph
        topology. Earlier failures hide later ones, which keeps error
        messages focused on the *root* cause. Capacity is **first** so the
        T2 DoS payload cannot reach BFS.
        """
        self._check_name_range()
        _validate_capacity(self.stages, self.transitions)
        _validate_stage_id_unique(self.stages)
        _validate_transition_id_unique(self.transitions)
        _validate_entry_in_stages(self.stages, self.entry_stage_id)
        _validate_transition_refs(self.stages, self.transitions)
        _validate_transition_determinism(self.transitions)
        _validate_external_review_notify(self.stages)
        _validate_required_role_non_empty(self.stages)
        _validate_dag_reachability(self.stages, self.transitions, self.entry_stage_id)
        _validate_dag_sink_exists(self.stages, self.transitions, self.entry_stage_id)
        return self

    def _check_name_range(self) -> None:
        length = len(self.name)
        if not (MIN_NAME_LENGTH <= length <= MAX_NAME_LENGTH):
            raise WorkflowInvariantViolation(
                kind="name_range",
                message=(
                    f"[FAIL] Workflow name must be "
                    f"{MIN_NAME_LENGTH}-{MAX_NAME_LENGTH} characters "
                    f"(got {length})"
                ),
                detail={"length": length},
            )

    # ---- behaviors (Tell, Don't Ask) ------------------------------------
    def add_stage(self, stage: Stage) -> Workflow:
        """Return a new Workflow with ``stage`` appended (REQ-WF-002)."""
        return self._rebuild_with(stages=[*self.stages, stage])

    def add_transition(self, transition: Transition) -> Workflow:
        """Return a new Workflow with ``transition`` appended (REQ-WF-003)."""
        return self._rebuild_with(transitions=[*self.transitions, transition])

    def remove_stage(self, stage_id: StageId) -> Workflow:
        """Return a new Workflow with ``stage_id`` and its incident edges removed (REQ-WF-004).

        Raises:
            WorkflowInvariantViolation:
                * ``kind='cannot_remove_entry'`` (MSG-WF-010) if removing the entry stage.
                * ``kind='stage_not_found'`` (MSG-WF-012) if no Stage matches.
                * Any aggregate violation (e.g. ``unreachable_stage``) bubbling
                  out of the rebuild — original Workflow stays unchanged.
        """
        if stage_id == self.entry_stage_id:
            raise WorkflowInvariantViolation(
                kind="cannot_remove_entry",
                message=f"[FAIL] Cannot remove entry stage: {stage_id}",
                detail={"stage_id": str(stage_id)},
            )
        if not any(stage.id == stage_id for stage in self.stages):
            raise WorkflowInvariantViolation(
                kind="stage_not_found",
                message=f"[FAIL] Stage not found in workflow: stage_id={stage_id}",
                detail={"stage_id": str(stage_id)},
            )
        new_stages = [stage for stage in self.stages if stage.id != stage_id]
        new_transitions = [
            transition
            for transition in self.transitions
            if transition.from_stage_id != stage_id and transition.to_stage_id != stage_id
        ]
        return self._rebuild_with(stages=new_stages, transitions=new_transitions)

    @classmethod
    def from_dict(cls, payload: object) -> Workflow:
        """Bulk-import factory (REQ-WF-006).

        Accepts ``object`` so callers passing a non-dict still hit the
        structured ``WorkflowInvariantViolation`` path rather than crashing
        Pydantic with a confusing low-level error.

        Pydantic ``ValidationError`` (type, UUID, missing-field, NotifyChannel
        URL allow list G1〜G10, MVP ``kind`` constraint) propagates as-is so
        callers can introspect the loc/error structure.

        ``StageInvariantViolation`` is wrapped into
        ``WorkflowInvariantViolation(kind='from_dict_invalid')`` with the
        offending stage index attached to ``detail`` — fulfilling
        TC-UT-WF-027's debug-traceability contract from the design doc's
        "なぜ from_dict はクラスメソッドか" section.
        """
        if not isinstance(payload, dict):
            raise WorkflowInvariantViolation(
                kind="from_dict_invalid",
                message=(
                    f"[FAIL] from_dict payload invalid: "
                    f"payload must be dict, got {type(payload).__name__}"
                ),
                detail={"payload_type": type(payload).__name__},
            )
        payload_dict = cast("dict[str, Any]", payload)
        stages_payload = payload_dict.get("stages")
        if isinstance(stages_payload, list):
            stages_list = cast("list[Any]", stages_payload)
            for index, stage_payload in enumerate(stages_list):
                try:
                    Stage.model_validate(stage_payload)
                except StageInvariantViolation as exc:
                    detail: dict[str, object] = {
                        **exc.detail,
                        "stage_index": index,
                        "stage_violation_kind": exc.kind,
                    }
                    raise WorkflowInvariantViolation(
                        kind="from_dict_invalid",
                        message=f"[FAIL] from_dict payload invalid: {detail}",
                        detail=detail,
                    ) from exc
                except ValidationError:
                    # Let cls.model_validate produce the canonical Pydantic
                    # error with full loc paths so the caller can introspect.
                    pass
        return cls.model_validate(payload_dict)

    # ---- internal: pre-validate rebuild (Confirmation A) ----------------
    def _rebuild_with(
        self,
        *,
        stages: list[Stage] | None = None,
        transitions: list[Transition] | None = None,
    ) -> Workflow:
        """Re-construct via ``model_validate`` so ``_check_invariants`` re-fires."""
        state = self.model_dump()
        if stages is not None:
            state["stages"] = [stage.model_dump() for stage in stages]
        if transitions is not None:
            state["transitions"] = [transition.model_dump() for transition in transitions]
        return Workflow.model_validate(state)


__all__ = ["Workflow"]
