"""Workflow Aggregate Root + ``Stage`` / ``Transition`` entities.

Implements ``REQ-WF-001``〜``REQ-WF-007`` per ``docs/features/workflow``.

Design contract (do not break without re-running design review):

* **Pre-validate rebuild (Confirmation A)** — every state-changing behavior
  serializes via ``model_dump()``, swaps the target collection, and re-runs
  ``Workflow.model_validate(...)``. ``model_copy(update=...)`` is intentionally
  avoided because Pydantic v2 defaults it to ``validate=False``.
* **Module-level invariant helpers (Confirmation F)** — each aggregate-level
  invariant lives in a private ``_validate_*`` pure function so that:
  1. Tests can ``import`` them and invoke directly (TC-UT-WF-060) to prove
     the aggregate path does not share code with ``Stage`` self-validation
     (twin-defense independence, TC-UT-WF-006a vs 006b).
  2. ``Workflow.model_validator`` stays a thin dispatch over the seven+ checks.
* **DAG safety (Confirmation B)** — ``_validate_dag_reachability`` uses
  ``collections.deque`` BFS so Python's recursion ceiling (1000) cannot bite
  on large workflows, and cycles do not loop infinitely.
* **Capacity (Confirmation E)** — ``len(stages) ≤ 30`` and ``len(transitions) ≤ 60``.
  Checked **first** to fail fast on T2 DoS payloads before any O(V+E) scan.
* **NotifyChannel SSRF / token masking (Confirmation G)** — handled inside
  ``NotifyChannel`` (see :mod:`bakufu.domain.value_objects`); this module
  consumes the validated VO without re-checking URL shape.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Self, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from bakufu.domain.exceptions import (
    StageInvariantViolation,
    WorkflowInvariantViolation,
)
from bakufu.domain.value_objects import (
    CompletionPolicy,
    NotifyChannel,
    Role,
    StageId,
    StageKind,
    TransitionCondition,
    TransitionId,
    WorkflowId,
    nfc_strip,
)

# ---------------------------------------------------------------------------
# Module-level constants (Workflow §Confirmation E + name bounds)
# ---------------------------------------------------------------------------
MAX_STAGES: int = 30
MAX_TRANSITIONS: int = 60
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 80


# ---------------------------------------------------------------------------
# Stage entity (within Workflow aggregate)
# ---------------------------------------------------------------------------
class Stage(BaseModel):
    """Workflow stage with **self**-invariants checked in ``model_validator``.

    Self-check raises :class:`StageInvariantViolation` so a Stage built outside
    a Workflow (e.g. preset definition, factory) still surfaces violations
    early. The Workflow aggregate later re-validates the same conditions in
    :func:`_validate_external_review_notify` and
    :func:`_validate_required_role_non_empty` — the dual path is by design
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


# ---------------------------------------------------------------------------
# Transition entity (within Workflow aggregate)
# ---------------------------------------------------------------------------
class Transition(BaseModel):
    """Directed edge between two Stages. Reference integrity is the aggregate's job."""

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


# ---------------------------------------------------------------------------
# Aggregate-level invariant helpers (Workflow §Confirmation F)
# ---------------------------------------------------------------------------
# Each helper:
#  * is a module-level private function (no class binding) so tests import
#    and call them directly without constructing a Workflow,
#  * shares zero code with ``Stage._check_self_invariants`` (the design
#    contract for twin-defense — TC-UT-WF-006a vs 006b proves independence),
#  * raises :class:`WorkflowInvariantViolation` with the ``_aggregate``
#    discriminator suffix so a stack trace makes the source path obvious.


def _validate_capacity(
    stages: list[Stage],
    transitions: list[Transition],
) -> None:
    """T2 DoS guard. Run **first** so huge payloads short-circuit before BFS."""
    stages_count = len(stages)
    if stages_count > MAX_STAGES:
        raise WorkflowInvariantViolation(
            kind="capacity_exceeded",
            message=(
                f"[FAIL] Workflow invariant violation: stages capacity "
                f"{MAX_STAGES} exceeded (got {stages_count})"
            ),
            detail={"stages_count": stages_count, "max_stages": MAX_STAGES},
        )
    if stages_count < 1:
        # 1〜30 is the contract; zero stages cannot satisfy entry_stage_id.
        raise WorkflowInvariantViolation(
            kind="capacity_exceeded",
            message=(
                f"[FAIL] Workflow invariant violation: stages must contain at "
                f"least 1 stage (got {stages_count})"
            ),
            detail={"stages_count": stages_count, "min_stages": 1},
        )
    transitions_count = len(transitions)
    if transitions_count > MAX_TRANSITIONS:
        raise WorkflowInvariantViolation(
            kind="capacity_exceeded",
            message=(
                f"[FAIL] Workflow invariant violation: transitions capacity "
                f"{MAX_TRANSITIONS} exceeded (got {transitions_count})"
            ),
            detail={
                "transitions_count": transitions_count,
                "max_transitions": MAX_TRANSITIONS,
            },
        )


def _validate_stage_id_unique(stages: list[Stage]) -> None:
    """No two Stages may share an id (MSG-WF-008)."""
    seen: set[StageId] = set()
    for stage in stages:
        if stage.id in seen:
            raise WorkflowInvariantViolation(
                kind="stage_duplicate",
                message=f"[FAIL] Stage id duplicate: {stage.id}",
                detail={"stage_id": str(stage.id)},
            )
        seen.add(stage.id)


def _validate_entry_in_stages(
    stages: list[Stage],
    entry_stage_id: StageId,
) -> None:
    """``entry_stage_id`` must reference a known Stage (MSG-WF-002)."""
    if not any(stage.id == entry_stage_id for stage in stages):
        raise WorkflowInvariantViolation(
            kind="entry_not_in_stages",
            message=f"[FAIL] entry_stage_id {entry_stage_id} not found in stages",
            detail={"entry_stage_id": str(entry_stage_id)},
        )


def _validate_transition_refs(
    stages: list[Stage],
    transitions: list[Transition],
) -> None:
    """Every Transition's from/to must point at a known Stage (MSG-WF-009)."""
    stage_ids: set[StageId] = {stage.id for stage in stages}
    for transition in transitions:
        if transition.from_stage_id not in stage_ids or transition.to_stage_id not in stage_ids:
            raise WorkflowInvariantViolation(
                kind="transition_ref_invalid",
                message=(
                    f"[FAIL] Transition references unknown stage: "
                    f"from={transition.from_stage_id}, to={transition.to_stage_id}"
                ),
                detail={
                    "transition_id": str(transition.id),
                    "from_stage_id": str(transition.from_stage_id),
                    "to_stage_id": str(transition.to_stage_id),
                },
            )


def _validate_transition_determinism(transitions: list[Transition]) -> None:
    """``(from_stage_id, condition)`` must be unique across Transitions (MSG-WF-005)."""
    seen: set[tuple[StageId, TransitionCondition]] = set()
    for transition in transitions:
        key = (transition.from_stage_id, transition.condition)
        if key in seen:
            raise WorkflowInvariantViolation(
                kind="transition_duplicate",
                message=(
                    f"[FAIL] Duplicate transition: "
                    f"from_stage={transition.from_stage_id}, "
                    f"condition={transition.condition}"
                ),
                detail={
                    "from_stage_id": str(transition.from_stage_id),
                    "condition": str(transition.condition),
                },
            )
        seen.add(key)


def _validate_external_review_notify(stages: list[Stage]) -> None:
    """All ``EXTERNAL_REVIEW`` Stages must declare notify_channels (MSG-WF-006).

    Aggregate-side twin of ``Stage._check_self_invariants``; tests
    (TC-UT-WF-006b) call this with stages whose self-validator was bypassed
    to prove the aggregate path catches the violation independently.
    """
    for stage in stages:
        if stage.kind is StageKind.EXTERNAL_REVIEW and not stage.notify_channels:
            raise WorkflowInvariantViolation(
                kind="missing_notify_aggregate",
                message=(
                    f"[FAIL] EXTERNAL_REVIEW stage {stage.id} must have at least one notify_channel"
                ),
                detail={"stage_id": str(stage.id)},
            )


def _validate_required_role_non_empty(stages: list[Stage]) -> None:
    """Every Stage's ``required_role`` must be non-empty (MSG-WF-007).

    Aggregate twin-defense (mirrors :class:`Stage` self-check).
    """
    for stage in stages:
        if not stage.required_role:
            raise WorkflowInvariantViolation(
                kind="empty_required_role_aggregate",
                message=f"[FAIL] Stage {stage.id} required_role must not be empty",
                detail={"stage_id": str(stage.id)},
            )


def _validate_dag_reachability(
    stages: list[Stage],
    transitions: list[Transition],
    entry_stage_id: StageId,
) -> None:
    """BFS from ``entry`` over the transition graph; reject orphan stages (MSG-WF-003).

    ``collections.deque`` keeps memory bounded and safely terminates even on
    cyclic graphs (visited set rejects re-enqueue).
    """
    adjacency: dict[StageId, list[StageId]] = {stage.id: [] for stage in stages}
    for transition in transitions:
        # Defensive: skip dangling refs; ``_validate_transition_refs`` runs
        # before this and would have raised, but keep BFS robust if a caller
        # invokes the helper directly with malformed input.
        if transition.from_stage_id in adjacency:
            adjacency[transition.from_stage_id].append(transition.to_stage_id)

    visited: set[StageId] = set()
    queue: deque[StageId] = deque([entry_stage_id])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                queue.append(neighbor)

    unreachable = [stage.id for stage in stages if stage.id not in visited]
    if unreachable:
        raise WorkflowInvariantViolation(
            kind="unreachable_stage",
            message=f"[FAIL] Unreachable stages from entry: {unreachable}",
            detail={"unreachable_stage_ids": [str(sid) for sid in unreachable]},
        )


def _validate_dag_sink_exists(
    stages: list[Stage],
    transitions: list[Transition],
    entry_stage_id: StageId,
) -> None:
    """At least one Stage must have no outgoing Transition (MSG-WF-004).

    Pure cycle-only workflows have zero sinks, which makes Task termination
    impossible — reject them.
    """
    has_outgoing: set[StageId] = {transition.from_stage_id for transition in transitions}
    if all(stage.id in has_outgoing for stage in stages):
        raise WorkflowInvariantViolation(
            kind="no_sink_stage",
            message=(f"[FAIL] No sink stage; workflow has cycles only (entry={entry_stage_id})"),
            detail={"entry_stage_id": str(entry_stage_id)},
        )


# ---------------------------------------------------------------------------
# Aggregate Root: Workflow
# ---------------------------------------------------------------------------
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

        Order matters for failure attribution: capacity → structural shape →
        reference integrity → semantic (notify / required_role) → graph
        topology. Earlier failures hide later ones, which keeps error
        messages focused on the *root* cause.
        """
        self._check_name_range()
        _validate_capacity(self.stages, self.transitions)
        _validate_stage_id_unique(self.stages)
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


__all__ = [
    "MAX_NAME_LENGTH",
    "MAX_STAGES",
    "MAX_TRANSITIONS",
    "MIN_NAME_LENGTH",
    "Stage",
    "Transition",
    "Workflow",
]
