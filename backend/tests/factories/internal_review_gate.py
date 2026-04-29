"""InternalReviewGate アグリゲートと VO のファクトリ群.

``docs/features/internal-review-gate/domain/test-design.md`` §外部 I/O 依存マップ
準拠。M1 兄弟パターン (external_review_gate / agent / room / directive / task /
workflow) を踏襲: 各ファクトリは本番コンストラクタ経由で *妥当* なデフォルト
インスタンスを返し、キーワード上書きを許可し、結果を :class:`WeakValueDictionary`
に登録する。これにより :func:`is_synthetic` が後から、frozen Pydantic モデルを
変更せずにテスト由来オブジェクトをフラグ付けできる。

公開ファクトリ 4 種:

* :func:`make_verdict` ── 単一 APPROVED の :class:`Verdict` VO。
* :func:`make_gate` ── PENDING の :class:`InternalReviewGate` (verdicts 空)。
* :func:`make_all_approved_gate` ── 全 required role が投票した ALL_APPROVED Gate。
* :func:`make_rejected_gate` ── REJECTED verdict 1 件を持つ REJECTED Gate。

ファクトリは ``model_validate`` で直接構築する ── ``submit_verdict`` は **呼ばない**
── behavior メソッドのユニットテストにはメソッド駆動の事前変更なしの
クリーンな入口状態が必要なため。

本モジュールを本番コードから import してはならない。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.internal_review_gate import InternalReviewGate
from bakufu.domain.value_objects import (
    GateDecision,
    Verdict,
    VerdictDecision,
)
from pydantic import BaseModel

# モジュールスコープのレジストリ: 合成インスタンスを弱参照で追跡し、
# オブジェクト生存中の GC 圧を中立に保つ。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()

# PENDING / REJECTED ファクトリで共有するデフォルト role 集合。
_DEFAULT_ROLES: frozenset[str] = frozenset({"reviewer", "ux", "security"})
# ALL_APPROVED ファクトリで使う小さめの role 集合 (verdicts を最小に保つ)。
_APPROVED_ROLES: frozenset[str] = frozenset({"reviewer", "ux"})


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。

    検査は ID ベース (``id()``) ── 独立に生成された等値の 2 インスタンスは
    区別される。
    """
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# Verdict ファクトリ
# ---------------------------------------------------------------------------
def make_verdict(
    *,
    role: str = "reviewer",
    agent_id: UUID | None = None,
    decision: VerdictDecision = VerdictDecision.APPROVED,
    comment: str = "",
    decided_at: datetime | None = None,
) -> Verdict:
    """妥当な :class:`Verdict` VO を構築する。

    デフォルトは ``"reviewer"`` role からの APPROVED verdict、空 comment ──
    ユニットテストのセットアップに最適な最小の正当形。
    """
    verdict = Verdict(
        role=role,
        agent_id=agent_id if agent_id is not None else uuid4(),
        decision=decision,
        comment=comment,
        decided_at=decided_at if decided_at is not None else datetime.now(UTC),
    )
    _register(verdict)
    return verdict


# ---------------------------------------------------------------------------
# InternalReviewGate ファクトリ
# ---------------------------------------------------------------------------
def make_gate(
    *,
    gate_id: UUID | None = None,
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
    required_gate_roles: frozenset[str] | None = None,
    verdicts: list[Verdict] | None = None,
    gate_decision: GateDecision = GateDecision.PENDING,
    created_at: datetime | None = None,
) -> InternalReviewGate:
    """妥当な PENDING :class:`InternalReviewGate` を ``model_validate`` で直接構築する。

    デフォルト:
    * ``gate_decision = PENDING``
    * ``verdicts = []``
    * ``required_gate_roles = {"reviewer", "ux", "security"}``

    terminal 状態の Gate を構築する場合は ``verdicts`` と整合する
    ``gate_decision`` を渡す (専用 :func:`make_all_approved_gate` /
    :func:`make_rejected_gate` を優先するのが望ましい)。
    """
    now = datetime.now(UTC)
    roles = required_gate_roles if required_gate_roles is not None else _DEFAULT_ROLES
    raw_verdicts = verdicts if verdicts is not None else []
    gate = InternalReviewGate.model_validate(
        {
            "id": gate_id if gate_id is not None else uuid4(),
            "task_id": task_id if task_id is not None else uuid4(),
            "stage_id": stage_id if stage_id is not None else uuid4(),
            "required_gate_roles": roles,
            "verdicts": [v.model_dump() for v in raw_verdicts],
            "gate_decision": gate_decision,
            "created_at": created_at if created_at is not None else now,
        }
    )
    _register(gate)
    return gate


def make_all_approved_gate(
    *,
    required_gate_roles: frozenset[str] | None = None,
    gate_id: UUID | None = None,
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
) -> InternalReviewGate:
    """ALL_APPROVED :class:`InternalReviewGate` を構築する。

    デフォルトは ``required_gate_roles={"reviewer","ux"}`` ── 全コンセンサス
    (2 件の APPROVED verdict) を示す最小の妥当集合。required role 全てに
    APPROVED Verdict を割り当てる。
    """
    roles = required_gate_roles if required_gate_roles is not None else _APPROVED_ROLES
    ts = datetime.now(UTC)
    verdicts = [
        make_verdict(role=role, decision=VerdictDecision.APPROVED, decided_at=ts)
        for role in sorted(roles)
    ]
    return make_gate(
        gate_id=gate_id,
        task_id=task_id,
        stage_id=stage_id,
        required_gate_roles=roles,
        verdicts=verdicts,
        gate_decision=GateDecision.ALL_APPROVED,
    )


def make_rejected_gate(
    *,
    rejecting_role: str = "reviewer",
    required_gate_roles: frozenset[str] | None = None,
    comment: str = "バグを発見しました。",
    gate_id: UUID | None = None,
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
) -> InternalReviewGate:
    """REJECTED :class:`InternalReviewGate` を構築する。

    ``rejecting_role`` からの REJECTED Verdict 1 件 ── 残りの required role は
    *未提出* (pessimistic-wins ルールを示す: 未提出 role があっても即時 REJECTED)。
    """
    roles = required_gate_roles if required_gate_roles is not None else _DEFAULT_ROLES
    if rejecting_role not in roles:
        raise ValueError(
            f"rejecting_role '{rejecting_role}' must be present in required_gate_roles"
        )
    ts = datetime.now(UTC)
    verdict = make_verdict(
        role=rejecting_role,
        decision=VerdictDecision.REJECTED,
        comment=comment,
        decided_at=ts,
    )
    return make_gate(
        gate_id=gate_id,
        task_id=task_id,
        stage_id=stage_id,
        required_gate_roles=roles,
        verdicts=[verdict],
        gate_decision=GateDecision.REJECTED,
    )


__all__ = [
    "is_synthetic",
    "make_all_approved_gate",
    "make_gate",
    "make_rejected_gate",
    "make_verdict",
]
