"""Factories for the Workflow aggregate, its entities, and VOs.

Per ``docs/features/workflow/test-design.md`` (REQ-WF-001〜007, factories), each
factory:

* Returns a *valid* default instance built via the production constructor.
* Allows keyword overrides so individual tests can exercise specific edge
  cases without copy-pasting full kwargs.
* Registers the produced instance in :data:`_SYNTHETIC_REGISTRY` so
  :func:`is_synthetic` can later confirm "this object came from a factory".

Why a ``WeakValueDictionary`` over inline metadata?

* :class:`bakufu.domain.workflow.Workflow` / :class:`Stage` / :class:`Transition`
  and the workflow VOs (:class:`NotifyChannel`, :class:`CompletionPolicy`) are
  ``frozen=True`` Pydantic v2 models with ``extra='forbid'``: adding a
  ``_meta.synthetic`` attribute is physically impossible.
* A weak-value registry keyed by ``id(instance)`` flags instances externally;
  entries auto-evict on GC so id reuse on a freshly allocated, unrelated
  instance simply yields a cache miss instead of a false positive.

Production code MUST NOT import this module. The module mirrors empire's
factory pattern (single source of truth for the synthetic-vs-real boundary).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.value_objects import (
    CompletionPolicy,
    NotifyChannel,
    Role,
    StageId,
    StageKind,
    TransitionCondition,
)
from bakufu.domain.workflow import Stage, Transition, Workflow
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# Module-scope registry. Values are kept weakly so GC pressure stays neutral;
# we only want to know "did a factory produce this object" while it's alive.
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()

# A real-shape Discord webhook URL for tests that need a *valid* target.
# Token segment uses URL-safe characters (G7) and stays under 100 chars (G7).
DEFAULT_DISCORD_WEBHOOK = (
    "https://discord.com/api/webhooks/123456789012345678/SyntheticToken_-abcXYZ"
)


def is_synthetic(instance: BaseModel) -> bool:
    """Return ``True`` when ``instance`` was created by a factory in this module."""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """Record ``instance`` in the synthetic registry."""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# CompletionPolicy / NotifyChannel
# ---------------------------------------------------------------------------
def make_completion_policy(
    *,
    kind: str = "approved_by_reviewer",
    description: str = "review approval",
) -> CompletionPolicy:
    """Build a valid :class:`CompletionPolicy`."""
    policy = CompletionPolicy.model_validate({"kind": kind, "description": description})
    _register(policy)
    return policy


def make_notify_channel(
    *,
    target: str = DEFAULT_DISCORD_WEBHOOK,
) -> NotifyChannel:
    """Build a valid :class:`NotifyChannel` (kind='discord')."""
    channel = NotifyChannel(kind="discord", target=target)
    _register(channel)
    return channel


# ---------------------------------------------------------------------------
# Stage / Transition
# ---------------------------------------------------------------------------
def make_stage(
    *,
    stage_id: UUID | None = None,
    name: str = "ステージ",
    kind: StageKind = StageKind.WORK,
    required_role: frozenset[Role] | None = None,
    deliverable_template: str = "",
    completion_policy: CompletionPolicy | None = None,
    notify_channels: Sequence[NotifyChannel] | None = None,
) -> Stage:
    """Build a valid :class:`Stage`.

    Defaults choose ``kind=WORK`` with ``required_role={DEVELOPER}`` so the
    Stage's self-validator (REQ-WF-007) passes without further tweaking.
    Callers exercising EXTERNAL_REVIEW must supply ``notify_channels``.
    """
    if required_role is None:
        required_role = frozenset({Role.DEVELOPER})
    if completion_policy is None:
        completion_policy = make_completion_policy()
    # EXTERNAL_REVIEW requires non-empty notify_channels for the Stage self-check.
    if notify_channels is None:
        notify_channels = [make_notify_channel()] if kind is StageKind.EXTERNAL_REVIEW else []
    stage = Stage(
        id=stage_id if stage_id is not None else uuid4(),
        name=name,
        kind=kind,
        required_role=required_role,
        deliverable_template=deliverable_template,
        completion_policy=completion_policy,
        notify_channels=list(notify_channels),
    )
    _register(stage)
    return stage


def make_transition(
    *,
    transition_id: UUID | None = None,
    from_stage_id: StageId,
    to_stage_id: StageId,
    condition: TransitionCondition = TransitionCondition.APPROVED,
    label: str = "",
) -> Transition:
    """Build a valid :class:`Transition`."""
    transition = Transition(
        id=transition_id if transition_id is not None else uuid4(),
        from_stage_id=from_stage_id,
        to_stage_id=to_stage_id,
        condition=condition,
        label=label,
    )
    _register(transition)
    return transition


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------
def make_workflow(
    *,
    workflow_id: UUID | None = None,
    name: str = "テストワークフロー",
    stages: Sequence[Stage] | None = None,
    transitions: Sequence[Transition] | None = None,
    entry_stage_id: StageId | None = None,
) -> Workflow:
    """Build a valid :class:`Workflow`.

    With no overrides, returns a single-Stage workflow where ``entry == sink``
    (the simplest valid aggregate state per TC-UT-WF-001).
    """
    if stages is None:
        single = make_stage()
        stages = [single]
        if entry_stage_id is None:
            entry_stage_id = single.id
    elif entry_stage_id is None:
        entry_stage_id = stages[0].id
    if transitions is None:
        transitions = []
    workflow = Workflow(
        id=workflow_id if workflow_id is not None else uuid4(),
        name=name,
        stages=list(stages),
        transitions=list(transitions),
        entry_stage_id=entry_stage_id,
    )
    _register(workflow)
    return workflow


# ---------------------------------------------------------------------------
# V-model rendering example (transactions.md §レンダリング例)
# ---------------------------------------------------------------------------
# Stage names from the design book's V-model example. 13 stages: 4 work/review
# pairs (req analysis, req def, basic design, detail design) + 4 implementation
# work stages (impl, unit test, integ test, e2e test) + 1 final review.
_V_MODEL_STAGES: tuple[tuple[str, StageKind, frozenset[Role]], ...] = (
    ("要求分析", StageKind.WORK, frozenset({Role.LEADER})),
    ("要求分析レビュー", StageKind.EXTERNAL_REVIEW, frozenset({Role.REVIEWER})),
    ("要件定義", StageKind.WORK, frozenset({Role.LEADER, Role.UX})),
    ("要件定義レビュー", StageKind.EXTERNAL_REVIEW, frozenset({Role.REVIEWER})),
    ("基本設計", StageKind.WORK, frozenset({Role.DEVELOPER, Role.UX})),
    ("基本設計レビュー", StageKind.EXTERNAL_REVIEW, frozenset({Role.REVIEWER})),
    ("詳細設計", StageKind.WORK, frozenset({Role.DEVELOPER})),
    ("詳細設計レビュー", StageKind.EXTERNAL_REVIEW, frozenset({Role.REVIEWER})),
    ("実装", StageKind.WORK, frozenset({Role.DEVELOPER})),
    ("ユニットテスト", StageKind.WORK, frozenset({Role.TESTER})),
    ("結合テスト", StageKind.WORK, frozenset({Role.TESTER})),
    ("E2E テスト", StageKind.WORK, frozenset({Role.TESTER})),
    ("完了レビュー", StageKind.EXTERNAL_REVIEW, frozenset({Role.REVIEWER})),
)


def build_v_model_payload() -> dict[str, object]:
    """Return a ``Workflow.from_dict``-ready payload for the V-model preset.

    Contract:
        * 13 stages (matches transactions.md §レンダリング例).
        * 15 transitions: 12 APPROVED forward edges (stage[i] → stage[i+1])
          plus 3 REJECTED back edges from review → preceding work stage so the
          deterministic-condition check (one ``(from, condition)`` per pair)
          stays satisfied while still demonstrating non-trivial topology.
        * Final stage (``完了レビュー``) has no outgoing edge → satisfies the
          sink-exists invariant.
    """
    stages: list[dict[str, object]] = []
    stage_ids: list[UUID] = []
    for stage_name, stage_kind, role_set in _V_MODEL_STAGES:
        sid = uuid4()
        stage_ids.append(sid)
        stage_payload: dict[str, object] = {
            "id": str(sid),
            "name": stage_name,
            "kind": stage_kind.value,
            "required_role": [role.value for role in role_set],
            "deliverable_template": "",
            "completion_policy": {
                "kind": "approved_by_reviewer",
                "description": f"{stage_name} 完了判定",
            },
            "notify_channels": (
                [{"kind": "discord", "target": DEFAULT_DISCORD_WEBHOOK}]
                if stage_kind is StageKind.EXTERNAL_REVIEW
                else []
            ),
        }
        stages.append(stage_payload)

    transitions: list[dict[str, object]] = []
    # 12 forward APPROVED transitions (stage[i] → stage[i+1]).
    for index in range(len(stage_ids) - 1):
        transitions.append(
            {
                "id": str(uuid4()),
                "from_stage_id": str(stage_ids[index]),
                "to_stage_id": str(stage_ids[index + 1]),
                "condition": TransitionCondition.APPROVED.value,
                "label": "approve",
            }
        )
    # 3 REJECTED back edges from review → preceding work stage. Use indices
    # 1, 3, 5 (the early review stages) to vary the pattern.
    for review_index in (1, 3, 5):
        transitions.append(
            {
                "id": str(uuid4()),
                "from_stage_id": str(stage_ids[review_index]),
                "to_stage_id": str(stage_ids[review_index - 1]),
                "condition": TransitionCondition.REJECTED.value,
                "label": "reject",
            }
        )

    return {
        "id": str(uuid4()),
        "name": "V モデル開発フロー",
        "stages": stages,
        "transitions": transitions,
        "entry_stage_id": str(stage_ids[0]),
    }


__all__ = [
    "DEFAULT_DISCORD_WEBHOOK",
    "build_v_model_payload",
    "is_synthetic",
    "make_completion_policy",
    "make_notify_channel",
    "make_stage",
    "make_transition",
    "make_workflow",
]
