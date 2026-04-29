""":class:`InternalReviewGate` のための Aggregate レベル不変条件ヘルパ。

各ヘルパは **モジュール レベルの純粋関数** であるため、テストから ``import``
して直接呼べる — agent / room / directive / task / external_review_gate の
Aggregate バリデータと同じテスタビリティ パターン。

internal-review-gate detailed-design §確定 J に対応する 4 つの不変条件:

1. :func:`_validate_required_gate_roles_nonempty` — ``required_gate_roles``
   は少なくとも 1 つのロールを含まなければならない。空集合では設計上
   ALL_APPROVED に到達できなくなり、ワークフロー作成者の間違いが即座に表面化
   すべきである。
2. :func:`_validate_verdict_roles_in_required` — 各 verdict の ``role`` は
   ``required_gate_roles`` に含まれなければならない。認識されないロールから
   の verdict は、stale または誤構成のエージェントを示しており、決定に影響を
   与える前に拒否すべきである。
3. :func:`_validate_no_duplicate_roles` — 各 GateRole は最大 1 つの verdict
   しか持てない。重複提出は拒否される（エージェントは振る舞い層でも
   ``submit_verdict`` でガードされなければならないが、Aggregate バリデータは
   水和時に第二の防御線を提供する）。
4. :func:`_validate_gate_decision_consistency` — 保存された ``gate_decision``
   は現在の ``verdicts`` と ``required_gate_roles`` から ``compute_decision``
   が生成する値と等しくなければならない。リポジトリ行破損や誤動作する振る舞い
   メソッドを検出する。

パブリックな :func:`validate_all` 関数は全 4 つを順序通りに実行し、
:meth:`InternalReviewGate._check_invariants` から呼ばれる。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bakufu.domain.exceptions import InternalReviewGateInvariantViolation
from bakufu.domain.internal_review_gate.state_machine import compute_decision

if TYPE_CHECKING:
    from bakufu.domain.internal_review_gate.internal_review_gate import InternalReviewGate


def _validate_required_gate_roles_nonempty(gate: InternalReviewGate) -> None:
    """``required_gate_roles`` は空であってはならない（不変条件 1）。

    空集合では ``GateDecision.ALL_APPROVED`` が構造的に到達不可能になる（承認
    すべきロールが無いことは state machine の観点では「全 required ロールが
    承認」条件が真空に真となるが、ビジネス ルールは少なくとも 1 つの人間
    レビュアー カテゴリが参加することを意図している）。構築時にここで送出する
    ことで、ワークフロー作成者の間違いがエージェントが Gate と相互作用する前に
    表面化する。
    """
    if not gate.required_gate_roles:
        raise InternalReviewGateInvariantViolation(
            kind="required_gate_roles_empty",
            message=(
                "[FAIL] InternalReviewGate.required_gate_roles が空です。\n"
                "Next: 少なくとも 1 つの GateRole を required_gate_roles に設定してください。"
            ),
            detail={"gate_id": str(gate.id)},
        )


def _validate_verdict_roles_in_required(gate: InternalReviewGate) -> None:
    """全 verdict のロールは ``required_gate_roles`` に含まれなければならない（不変条件 2）。

    ``role`` が ``required_gate_roles`` に不在の verdict は、stale な Gate 構成
    （Gate 作成後にロールが削除された）または誤構成のエージェント（付与されて
    いないロールを名乗る）のいずれかを示す。どちらのケースも Gate 決定計算前に
    表面化すべきデータ整合性違反。
    """
    required = gate.required_gate_roles
    for verdict in gate.verdicts:
        if verdict.role not in required:
            raise InternalReviewGateInvariantViolation(
                kind="verdict_role_invalid",
                message=(
                    f'[FAIL] Verdict の GateRole "{verdict.role}" は '
                    f"required_gate_roles に含まれていません。\n"
                    f"Next: 有効な GateRole（{sorted(required)}）の verdict のみ "
                    f"InternalReviewGate に追加してください。"
                ),
                detail={
                    "gate_id": str(gate.id),
                    "invalid_role": verdict.role,
                    "required_gate_roles": sorted(required),
                },
            )


def _validate_no_duplicate_roles(gate: InternalReviewGate) -> None:
    """各 GateRole は ``verdicts`` 内に最大 1 回しか現れてはならない（不変条件 3）。

    重複ロール verdict はプログラミング エラー — ``submit_verdict`` が振る舞い層
    で再提出をガードするが、Aggregate バリデータは水和時にも同じ不変条件を強制
    するため、破損したリポジトリ行がサイレントに一貫性のない Gate を生成しない。
    """
    seen: set[str] = set()
    for verdict in gate.verdicts:
        if verdict.role in seen:
            raise InternalReviewGateInvariantViolation(
                kind="duplicate_role_verdict",
                message=(
                    f'[FAIL] GateRole "{verdict.role}" の verdict が重複しています。\n'
                    f"Next: 各 GateRole の verdict は 1 件のみ許可されています。"
                ),
                detail={
                    "gate_id": str(gate.id),
                    "duplicate_role": verdict.role,
                },
            )
        seen.add(verdict.role)


def _validate_gate_decision_consistency(gate: InternalReviewGate) -> None:
    """``gate_decision`` は ``compute_decision(...)`` と等しくなければならない（不変条件 4）。

    リポジトリ行破損（例 verdict が存在しないのに ``gate_decision=ALL_APPROVED``）
    や、state machine を経由せずに decision フィールドを更新する誤動作な振る舞い
    メソッドを検出する。
    """
    expected = compute_decision(gate.verdicts, gate.required_gate_roles)
    if gate.gate_decision != expected:
        raise InternalReviewGateInvariantViolation(
            kind="gate_decision_inconsistent",
            message=(
                f"[FAIL] gate_decision が不整合です "
                f"（stored={gate.gate_decision.value}, "
                f"computed={expected.value}）。\n"
                f"Next: Repository 行の整合性を確認してください。"
            ),
            detail={
                "gate_id": str(gate.id),
                "stored_decision": gate.gate_decision.value,
                "computed_decision": expected.value,
            },
        )


def validate_all(gate: InternalReviewGate) -> None:
    """4 つの Aggregate 不変条件を順序通りに実行する。

    :meth:`InternalReviewGate._check_invariants` から呼ばれるため、すべての構築
    経路（直接インスタンス化、``model_validate``、リポジトリ水和）で同じチェック
    が走る。不変条件は安価な順から最も高価な順に並ぶ:

    1. 非空ロール（O(1) 集合真偽チェック）。
    2. Verdict ロールの部分集合チェック（verdict 数 n に対し O(n)）。
    3. 重複ロール検出（``set`` アキュムレータで O(n)）。
    4. 決定の一貫性（O(n) ``compute_decision`` 畳み込み）。
    """
    _validate_required_gate_roles_nonempty(gate)
    _validate_verdict_roles_in_required(gate)
    _validate_no_duplicate_roles(gate)
    _validate_gate_decision_consistency(gate)


__all__ = [
    "_validate_gate_decision_consistency",
    "_validate_no_duplicate_roles",
    "_validate_required_gate_roles_nonempty",
    "_validate_verdict_roles_in_required",
    "validate_all",
]
