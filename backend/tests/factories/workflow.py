"""Workflow アグリゲート、エンティティ、VO のファクトリ群.

``docs/features/workflow/test-design.md`` (REQ-WF-001〜007, factories) 準拠。
各ファクトリは:

* 本番コンストラクタ経由で *妥当* なデフォルトインスタンスを返す。
* キーワード上書きを許可し、個別テストが完全な kwargs を貼り付けずに
  特定の境界値を検証できるようにする。
* 生成したインスタンスを :data:`_SYNTHETIC_REGISTRY` に登録し、
  :func:`is_synthetic` で後から「ファクトリ由来か」を確認できるようにする。

``WeakValueDictionary`` をインラインメタデータより優先する理由:

* :class:`bakufu.domain.workflow.Workflow` / :class:`Stage` /
  :class:`Transition` および workflow の VO (:class:`NotifyChannel`,
  :class:`CompletionPolicy`) は ``frozen=True`` で ``extra='forbid'`` の
  Pydantic v2 モデル ── ``_meta.synthetic`` 属性追加が物理的に不可能。
* ``id(instance)`` をキーとする弱参照レジストリは外側からインスタンスに
  フラグ付けする。エントリは GC で自動失効するため、新規 allocate で
  id が再利用されても false positive ではなくキャッシュミスとなる。

本モジュールを本番コードから import してはならない。empire の
ファクトリパターンを踏襲し、合成 vs 実物境界の単一情報源を担う。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.value_objects import (
    CompletionPolicy,
    DeliverableRequirement,
    DeliverableTemplateRef,
    NotifyChannel,
    Role,
    SemVer,
    StageId,
    StageKind,
    TransitionCondition,
)
from bakufu.domain.workflow import Stage, Transition, Workflow
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

# モジュールスコープのレジストリ。値は弱参照で保持するので GC 圧は中立 ──
# 「このオブジェクトはファクトリ由来か」をオブジェクト生存中だけ知ればよい。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()

# *妥当* なターゲットを必要とするテスト向けの実形 Discord webhook URL。
# トークン部は URL-safe 文字 (G7) を使い、100 文字未満に収める (G7)。
DEFAULT_DISCORD_WEBHOOK = (
    "https://discord.com/api/webhooks/123456789012345678/SyntheticToken_-abcXYZ"
)


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。"""
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """``instance`` を合成レジストリに記録する。"""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# CompletionPolicy / NotifyChannel
# ---------------------------------------------------------------------------
def make_completion_policy(
    *,
    kind: str = "approved_by_reviewer",
    description: str = "review approval",
) -> CompletionPolicy:
    """妥当な :class:`CompletionPolicy` を構築する。"""
    policy = CompletionPolicy.model_validate({"kind": kind, "description": description})
    _register(policy)
    return policy


def make_notify_channel(
    *,
    target: str = DEFAULT_DISCORD_WEBHOOK,
) -> NotifyChannel:
    """妥当な :class:`NotifyChannel` (kind='discord') を構築する。"""
    channel = NotifyChannel(kind="discord", target=target)
    _register(channel)
    return channel


# ---------------------------------------------------------------------------
# DeliverableRequirement
# ---------------------------------------------------------------------------
def make_deliverable_requirement(
    *,
    template_id: UUID | None = None,
    optional: bool = False,
) -> DeliverableRequirement:
    """妥当な :class:`DeliverableRequirement` を構築する。

    TC-UT-RMS-001〜007 の validate_coverage テストで Stage.required_deliverables
    に含める成果物要件 VO を生成する。
    ``template_id`` 省略時は乱数 UUID を割り当てる（ユニークな要件のデフォルト）。
    ``optional=True`` を渡すと §確定 E（省略可能成果物は検証対象外）の境界値テストに
    使用できる。
    """
    ref = DeliverableTemplateRef(
        template_id=template_id if template_id is not None else uuid4(),
        minimum_version=SemVer(major=1, minor=0, patch=0),
    )
    dr = DeliverableRequirement(template_ref=ref, optional=optional)
    _register(dr)
    return dr


# ---------------------------------------------------------------------------
# Stage / Transition
# ---------------------------------------------------------------------------
def make_stage(
    *,
    stage_id: UUID | None = None,
    name: str = "ステージ",
    kind: StageKind = StageKind.WORK,
    required_role: frozenset[Role] | None = None,
    required_deliverables: tuple[DeliverableRequirement, ...] = (),
    completion_policy: CompletionPolicy | None = None,
    notify_channels: Sequence[NotifyChannel] | None = None,
) -> Stage:
    """妥当な :class:`Stage` を構築する。

    デフォルトは ``kind=WORK`` + ``required_role={DEVELOPER}``。これで
    Stage の自己バリデータ (REQ-WF-007) が追加調整なしに通過する。
    EXTERNAL_REVIEW を使う呼び出し側は ``notify_channels`` を渡すこと。
    ``required_deliverables`` は Issue #117 で追加された成果物要件タプル。
    """
    if required_role is None:
        required_role = frozenset({Role.DEVELOPER})
    if completion_policy is None:
        completion_policy = make_completion_policy()
    # EXTERNAL_REVIEW は Stage の自己チェックのため非空の notify_channels を要する。
    if notify_channels is None:
        notify_channels = [make_notify_channel()] if kind is StageKind.EXTERNAL_REVIEW else []
    stage = Stage(
        id=stage_id if stage_id is not None else uuid4(),
        name=name,
        kind=kind,
        required_role=required_role,
        required_deliverables=required_deliverables,
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
    """妥当な :class:`Transition` を構築する。"""
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
    """妥当な :class:`Workflow` を構築する。

    上書きなしの場合、``entry == sink`` の単一 Stage ワークフローを返す
    (TC-UT-WF-001 における最小妥当 aggregate 状態)。
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
# V モデルレンダリング例 (transactions.md §レンダリング例)
# ---------------------------------------------------------------------------
# 設計書の V モデル例による Stage 名。13 ステージ: 4 つの作業/レビュー対
# (要求分析、要件定義、基本設計、詳細設計) + 4 つの実装作業ステージ
# (実装、単体テスト、結合テスト、e2e テスト) + 最終レビュー 1 つ。
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
    """V モデルプリセット用に ``Workflow.from_dict`` 即可なペイロードを返す。

    契約:
        * 13 ステージ (transactions.md §レンダリング例 と一致)。
        * 15 transition: 12 件の APPROVED 順方向 (stage[i] → stage[i+1])
          + review → 直前 work ステージへの REJECTED 逆方向 3 件。
          これにより決定性条件チェック (各 ``(from, condition)`` が 1 件) を
          満たしつつ、非自明な topology を示す。
        * 最終ステージ (``完了レビュー``) は出辺を持たない → sink 存在不変条件を
          満たす。
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
            "required_deliverables": [],
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
    # 順方向 APPROVED transition 12 件 (stage[i] → stage[i+1])。
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
    # review → 直前 work ステージへの REJECTED 逆方向 3 件。
    # パターンを多様にするため、早期 review ステージのインデックス 1, 3, 5 を使う。
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
    "make_deliverable_requirement",
    "make_notify_channel",
    "make_stage",
    "make_transition",
    "make_workflow",
]
