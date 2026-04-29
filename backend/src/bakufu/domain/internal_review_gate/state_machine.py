""":class:`InternalReviewGate` Aggregate のための決定計算。

internal-review-gate detailed-design §確定 B の most-pessimistic-wins ルールを
実装する:

1. 任意の :attr:`VerdictDecision.REJECTED` verdict → :attr:`GateDecision.REJECTED`
   （最優先。1 つの反対意見が即座に Gate をブロックする）。
2. 全 ``required_gate_roles`` が APPROVED verdict を持つ →
   :attr:`GateDecision.ALL_APPROVED`。
3. それ以外 → :attr:`GateDecision.PENDING`。

計算は副作用のない **純粋関数** で、再代入を pyright strict が拒否できるよう
``Final`` バインディングの背後にロックされている。

*遷移表*（action x state -> next_state）をモデル化する
:mod:`bakufu.domain.external_review_gate.state_machine` と異なり、
InternalReviewGate の決定は現在の ``verdicts`` コレクションと
``required_gate_roles`` 集合から **計算** される — 明示的なアクション
ディスパッチは存在せず、verdict タプルへの fold のみ。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final

from bakufu.domain.value_objects import GateDecision, VerdictDecision

if TYPE_CHECKING:
    from bakufu.domain.value_objects import GateRole, Verdict


def _compute_decision(
    verdicts: tuple[Verdict, ...],
    required_gate_roles: frozenset[GateRole],
) -> GateDecision:
    """現在の状態が含意する :class:`GateDecision` を返す。

    決定表（most-pessimistic-wins）:

    1. ``decision == REJECTED`` の verdict が存在 → ``REJECTED``
       （最初にチェック。1 つの反対意見が承認数に関わらず即座に Gate を閉じる）。
    2. ``required_gate_roles`` の全ロールが対応する APPROVED verdict を持つ →
       ``ALL_APPROVED``。
    3. それ以外 → ``PENDING``（required ロールの一部がまだ欠けている）。

    Args:
        verdicts: 現時点で集まった全 verdict。空であってもよい。
        required_gate_roles: Gate が ALL_APPROVED に到達するために **すべて**
            APPROVED 投票しなければならないロール slug の閉じた集合。
            非空でなければならない（本関数呼び出し前に
            :func:`bakufu.domain.internal_review_gate.aggregate_validators
            ._validate_required_gate_roles_nonempty` が強制する）。

    Returns:
        現在の verdict コレクションを最もよく表す :class:`GateDecision`。
    """
    # ルール 1: REJECTED verdict があれば → REJECTED（most pessimistic wins）。
    for verdict in verdicts:
        if verdict.decision == VerdictDecision.REJECTED:
            return GateDecision.REJECTED

    # ルール 2: 全 required ロールが APPROVED verdict を持つ → ALL_APPROVED。
    approved_roles = frozenset(
        verdict.role for verdict in verdicts if verdict.decision == VerdictDecision.APPROVED
    )
    if required_gate_roles.issubset(approved_roles):
        return GateDecision.ALL_APPROVED

    # ルール 3: 1 つ以上の required ロールをまだ待っている。
    return GateDecision.PENDING


compute_decision: Final[Callable[[tuple[Verdict, ...], frozenset[GateRole]], GateDecision]] = (
    _compute_decision
)
"""決定計算関数のパブリック エイリアス。

``Final`` でロックされているため、pyright strict は再代入の試みを捕捉する。
アプリケーション コードやテストからは ``_compute_decision`` ではなくこのシンボル
を import し、公開コントラクトを明示する。プライベート実装詳細は自由にリネーム
できる状態に保つ。
"""

__all__ = ["compute_decision"]
