""":class:`Workflow` の Aggregate レベル不変条件バリデータ（Confirmation F）。

各ヘルパは **モジュールレベルの純粋関数** として実装する。理由:

1. テストから ``import`` して直接呼べる（TC-UT-WF-060）。これにより、Aggregate
   経路が :class:`Stage` 自己検証とコードを共有しないことを証明できる — Confirmation F
   の twin-defense（TC-UT-WF-006a vs 006b）の物理的根拠。
2. :class:`Workflow.model_validator` は 10 個のチェックの薄いディスパッチに留まり、
   失敗箇所の特定のために順序が文書化されている（capacity → 構造形状 → 参照整合性 →
   意味 → グラフ トポロジ）。

:mod:`dag_validators`（:mod:`bakufu.domain.workflow.entities` および ``workflow``
とは別ファイル）に置くことで、関数プレフィックスだけでなくディレクトリ レベルでも
twin-defense 境界を可視化する — Norman のレビュー フィードバック。
"""

from __future__ import annotations

from collections import deque

from bakufu.domain.exceptions import WorkflowInvariantViolation
from bakufu.domain.value_objects import StageId, StageKind, TransitionCondition, TransitionId
from bakufu.domain.workflow.entities import Stage, Transition

# ---------------------------------------------------------------------------
# モジュール レベル定数（Workflow §Confirmation E と名前境界）
# ---------------------------------------------------------------------------
MAX_STAGES: int = 30
MAX_TRANSITIONS: int = 60
MIN_NAME_LENGTH: int = 1
MAX_NAME_LENGTH: int = 80


# ---------------------------------------------------------------------------
# ヘルパ（各々 Stage._check_self_invariants とコードを共有しない）
# ---------------------------------------------------------------------------
def _validate_capacity(
    stages: list[Stage],
    transitions: list[Transition],
) -> None:
    """T2 DoS ガード。BFS の前に巨大ペイロードを短絡させるため **最初** に実行。"""
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
        # 1〜30 がコントラクト。stage 0 個では entry_stage_id を満たせない。
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
    """2 つの Stage が同じ id を共有してはならない（MSG-WF-008）。"""
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
    """2 つの Transition が同じ id を共有してはならない（``_validate_stage_id_unique`` と対称）。

    detailed-design 行「transitions: 0〜60 件、transition_id の重複なし」が要求する。
    これがないと、同 id の異なる 2 エッジが通過し、永続化層の UNIQUE 制約が後で捕捉
    することになる。Steve の PR #16 レビューがこのギャップを指摘し、対称性のため
    ヘルパを ``_validate_stage_id_unique`` と並べて配置することを要求した。
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
    """``entry_stage_id`` は既知の Stage を参照しなければならない（MSG-WF-002）。"""
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
    """全 Transition の from/to は既知の Stage を指していなければならない（MSG-WF-009）。"""
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
    """``(from_stage_id, condition)`` は Transition 全体で一意でなければならない（MSG-WF-005）。"""
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
    """全 ``EXTERNAL_REVIEW`` Stage は notify_channels を宣言しなければならない（MSG-WF-006）。

    ``Stage._check_self_invariants`` の Aggregate 側 twin。テスト（TC-UT-WF-006b）は
    自己検証をバイパスした stages を渡してこれを呼び出し、Aggregate 経路が独立して
    違反を捕捉することを証明する。
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
    """全 Stage の ``required_role`` は非空でなければならない（MSG-WF-007）。

    Aggregate 側の twin-defense（:class:`Stage` 自己チェックと対称）。
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
    """transition グラフ上で ``entry`` から BFS を行い、孤立 stage を拒否する（MSG-WF-003）。

    ``collections.deque`` がメモリを抑え、循環グラフでも安全に終了する（visited
    集合が再エンキューを拒否）。
    """
    adjacency: dict[StageId, list[StageId]] = {stage.id: [] for stage in stages}
    for transition in transitions:
        # 防御: 宙吊り参照はスキップ。``_validate_transition_refs`` がここより前に
        # 走って例外を送出するはずだが、呼び元がヘルパを不正入力で直接呼ぶ場合でも
        # BFS が頑健に動くようにする。
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
    """少なくとも 1 つの Stage は外向き Transition を持たないこと（MSG-WF-004）。

    純粋な循環のみのワークフローは sink が 0 となり、Task の終了が不可能になる —
    これを拒否する。
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
