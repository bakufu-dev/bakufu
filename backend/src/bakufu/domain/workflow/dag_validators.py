"""Aggregate-level invariant validators for :class:`Workflow` (Confirmation F).

Each helper is a **module-level pure function** so:

1. Tests can ``import`` them and invoke directly (TC-UT-WF-060) to prove the
   aggregate path does not share code with :class:`Stage` self-validation —
   the physical ground for Confirmation F's twin-defense (TC-UT-WF-006a vs
   006b).
2. :class:`Workflow.model_validator` stays a thin dispatch over the ten
   checks, with order documented for failure attribution (capacity →
   structural shape → reference integrity → semantic → graph topology).

Living in :mod:`dag_validators` (separate file from
:mod:`bakufu.domain.workflow.entities` and ``workflow``) makes the
twin-defense boundary visible at the directory level, not just the function
prefix — Norman's review feedback.
"""

from __future__ import annotations

from collections import deque

from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import StageId, StageKind, TransitionCondition, TransitionId
from bakufu.domain.workflow.entities import Stage, Transition

# ---------------------------------------------------------------------------
# Module-level constants (Workflow §Confirmation E + name bounds)
# ---------------------------------------------------------------------------
MAX_STAGES: int = 30
MAX_TRANSITIONS: int = 60
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 80


# ---------------------------------------------------------------------------
# Helpers (each shares zero code with Stage._check_self_invariants)
# ---------------------------------------------------------------------------
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


def _validate_transition_id_unique(transitions: list[Transition]) -> None:
    """No two Transitions may share an id (symmetric to ``_validate_stage_id_unique``).

    The detailed-design row "transitions: 0〜60 件、transition_id の重複なし"
    requires this; without it, two distinct edges with the same id slip
    through and only the persistence-layer UNIQUE constraint catches them
    later. Steve's PR #16 review caught this gap and required the helper to
    sit alongside ``_validate_stage_id_unique`` for symmetry.
    """
    seen: set[TransitionId] = set()
    for transition in transitions:
        if transition.id in seen:
            raise WorkflowInvariantViolation(
                kind="transition_id_duplicate",
                message=f"[FAIL] Transition id duplicate: {transition.id}",
                detail={"transition_id": str(transition.id)},
            )
        seen.add(transition.id)


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


__all__ = [
    "MAX_NAME_LENGTH",
    "MAX_STAGES",
    "MAX_TRANSITIONS",
    "MIN_NAME_LENGTH",
    "_validate_capacity",
    "_validate_dag_reachability",
    "_validate_dag_sink_exists",
    "_validate_entry_in_stages",
    "_validate_external_review_notify",
    "_validate_required_role_non_empty",
    "_validate_stage_id_unique",
    "_validate_transition_determinism",
    "_validate_transition_id_unique",
    "_validate_transition_refs",
]
