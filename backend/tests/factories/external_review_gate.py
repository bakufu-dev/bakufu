"""ExternalReviewGate アグリゲートと VO のファクトリ群.

``docs/features/external-review-gate/test-design.md`` §外部 I/O 依存
マップ 準拠。M1 の 6 兄弟パターン (empire / workflow / agent /
room / directive / task) を踏襲: 各ファクトリは本番コンストラクタ経由で
*妥当* なデフォルトインスタンスを返し、キーワード上書きを許可し、結果を
:class:`WeakValueDictionary` に登録する。これにより :func:`is_synthetic`
が後から、frozen Pydantic モデルを変更せずにテスト由来オブジェクトを
フラグ付けできる。

5 つの Gate ファクトリを公開する (``ReviewDecision`` ごと + PendingGateFactory
ベースライン)。これによりセットアップでステートマシンを歩かずに任意の
ライフサイクル位置へ到達できる。ファクトリは ``ExternalReviewGate.model_validate``
で直接構築する ── behavior メソッドは呼ばない ── behavior メソッドのテストには
メソッド駆動の事前変更なしのクリーンな入口状態が必要なため (加えて
§確定 C audit_trail append-only 契約により、ファクトリで設定した audit_trail
バイト列は後続のあらゆる mutation に対して固定される)。

本モジュールを本番コードから import してはならない ── 合成データ境界を
監査可能に保つため ``tests/`` 配下に配置されている。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

from bakufu.domain.external_review_gate import ExternalReviewGate
from bakufu.domain.value_objects import (
    AuditAction,
    AuditEntry,
    Deliverable,
    ReviewDecision,
)
from pydantic import BaseModel

from tests.factories.task import make_deliverable

if TYPE_CHECKING:
    from collections.abc import Sequence

# モジュールスコープのレジストリ。値は弱参照で保持するので GC 圧は中立 ──
# 「このオブジェクトはファクトリ由来か」をオブジェクト生存中だけ知ればよい。
_SYNTHETIC_REGISTRY: WeakValueDictionary[int, BaseModel] = WeakValueDictionary()


def is_synthetic(instance: BaseModel) -> bool:
    """``instance`` が本モジュールのファクトリで生成されたものなら ``True`` を返す。

    検査は構造的ではなく ID ベース (``id``)。これにより独立に生成された
    等値の 2 インスタンスは区別される ── ファクトリが返した実オブジェクトのみ
    合成印が付く。
    """
    cached = _SYNTHETIC_REGISTRY.get(id(instance))
    return cached is instance


def _register(instance: BaseModel) -> None:
    """``instance`` を合成レジストリに記録する。"""
    _SYNTHETIC_REGISTRY[id(instance)] = instance


# ---------------------------------------------------------------------------
# AuditEntry ファクトリ
# ---------------------------------------------------------------------------
def make_audit_entry(
    *,
    entry_id: UUID | None = None,
    actor_id: UUID | None = None,
    action: AuditAction = AuditAction.VIEWED,
    comment: str = "",
    occurred_at: datetime | None = None,
) -> AuditEntry:
    """妥当な :class:`AuditEntry` を構築する。

    デフォルトは VIEWED 監査エントリ ── 全ての Gate 状態が運べる最小の
    正当形。APPROVED / REJECTED / CANCELLED 監査行が要るテストは
    ``action`` を明示上書きする。
    """
    entry = AuditEntry(
        id=entry_id if entry_id is not None else uuid4(),
        actor_id=actor_id if actor_id is not None else uuid4(),
        action=action,
        comment=comment,
        occurred_at=occurred_at if occurred_at is not None else datetime.now(UTC),
    )
    _register(entry)
    return entry


# ---------------------------------------------------------------------------
# ExternalReviewGate ファクトリ ── ReviewDecision ごと + ベースライン
# ---------------------------------------------------------------------------
def make_gate(
    *,
    gate_id: UUID | None = None,
    task_id: UUID | None = None,
    stage_id: UUID | None = None,
    deliverable_snapshot: Deliverable | None = None,
    reviewer_id: UUID | None = None,
    decision: ReviewDecision = ReviewDecision.PENDING,
    feedback_text: str = "",
    audit_trail: Sequence[AuditEntry] | None = None,
    created_at: datetime | None = None,
    decided_at: datetime | None = None,
) -> ExternalReviewGate:
    """妥当な :class:`ExternalReviewGate` を ``model_validate`` 経由で直接構築する。

    デフォルトは監査エントリなし、feedback なし、``decided_at=None`` の
    PENDING Gate ── ``GateService.create()`` 直後 (Task.request_external_review
    後) の canonical な入口状態。

    注意: ``decision != PENDING`` は consistency invariant により非 None の
    ``decided_at`` を要する。terminal Gate が要るテストは
    :func:`make_approved_gate` / :func:`make_rejected_gate` /
    :func:`make_cancelled_gate` を使うこと。
    """
    now = datetime.now(UTC)
    gate = ExternalReviewGate.model_validate(
        {
            "id": gate_id if gate_id is not None else uuid4(),
            "task_id": task_id if task_id is not None else uuid4(),
            "stage_id": stage_id if stage_id is not None else uuid4(),
            "deliverable_snapshot": (
                deliverable_snapshot if deliverable_snapshot is not None else make_deliverable()
            ),
            "reviewer_id": reviewer_id if reviewer_id is not None else uuid4(),
            "decision": decision,
            "feedback_text": feedback_text,
            "audit_trail": list(audit_trail) if audit_trail is not None else [],
            "created_at": created_at if created_at is not None else now,
            "decided_at": decided_at,
        }
    )
    _register(gate)
    return gate


def make_approved_gate(
    *,
    feedback_text: str = "Approved by reviewer.",
    audit_trail: Sequence[AuditEntry] | None = None,
    decided_at: datetime | None = None,
    **overrides: object,
) -> ExternalReviewGate:
    """APPROVED Gate を構築する。consistency invariant のため ``decided_at`` 必須。"""
    decided_at = decided_at if decided_at is not None else datetime.now(UTC)
    if audit_trail is None:
        audit_trail = [
            make_audit_entry(action=AuditAction.APPROVED, occurred_at=decided_at),
        ]
    return make_gate(
        decision=ReviewDecision.APPROVED,
        feedback_text=feedback_text,
        audit_trail=audit_trail,
        decided_at=decided_at,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_rejected_gate(
    *,
    feedback_text: str = "Rejected: needs revision.",
    audit_trail: Sequence[AuditEntry] | None = None,
    decided_at: datetime | None = None,
    **overrides: object,
) -> ExternalReviewGate:
    """REJECTED Gate を構築する。"""
    decided_at = decided_at if decided_at is not None else datetime.now(UTC)
    if audit_trail is None:
        audit_trail = [
            make_audit_entry(action=AuditAction.REJECTED, occurred_at=decided_at),
        ]
    return make_gate(
        decision=ReviewDecision.REJECTED,
        feedback_text=feedback_text,
        audit_trail=audit_trail,
        decided_at=decided_at,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


def make_cancelled_gate(
    *,
    feedback_text: str = "Cancelled: directive withdrawn.",
    audit_trail: Sequence[AuditEntry] | None = None,
    decided_at: datetime | None = None,
    **overrides: object,
) -> ExternalReviewGate:
    """CANCELLED Gate を構築する。"""
    decided_at = decided_at if decided_at is not None else datetime.now(UTC)
    if audit_trail is None:
        audit_trail = [
            make_audit_entry(action=AuditAction.CANCELLED, occurred_at=decided_at),
        ]
    return make_gate(
        decision=ReviewDecision.CANCELLED,
        feedback_text=feedback_text,
        audit_trail=audit_trail,
        decided_at=decided_at,
        **overrides,  # pyright: ignore[reportArgumentType]
    )


__all__ = [
    "is_synthetic",
    "make_approved_gate",
    "make_audit_entry",
    "make_cancelled_gate",
    "make_gate",
    "make_rejected_gate",
]
