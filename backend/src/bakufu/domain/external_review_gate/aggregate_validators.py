""":class:`ExternalReviewGate` のための Aggregate レベル不変条件ヘルパ。

各ヘルパは **モジュール レベルの純粋関数** であるため、テストから ``import``
して直接呼べる — Norman / Steve が agent / room / directive / task の Aggregate
バリデータで承認したのと同じテスタビリティ パターン。

ヘルパ（6 つ、detailed-design.md §確定 J に対応）:

1. :func:`_validate_decided_at_consistency` — ``decision == PENDING`` ⇔
   ``decided_at is None``。他 4 状態は tz-aware decided_at を持たなければならない。
2. :func:`_validate_snapshot_immutable` — プレースホルダ。構造的ガードは
   ``_rebuild_with_state`` の引数集合に ``deliverable_snapshot`` を含めないこと
   （§確定 D）。本関数はバリデータ ディスパッチとの対称性のため、また rebuild が
   万一異なるスナップショットを供給した場合に明確な失敗経路を提供するために
   残されている。
3. :func:`_validate_feedback_text_range` — NFC コードポイント長 0〜10000。
4. :func:`_validate_audit_trail_append_only` — rebuild 時に新リストを旧リストと
   比較してチェックする（§確定 C inputs/expectations 表）。
5. :func:`_validate_criteria_immutable` — プレースホルダ。構造的ガードは
   ``_rebuild_with_state`` の引数集合に ``required_deliverable_criteria`` を
   含めないこと（§確定 D'）。本関数は snapshot_immutable と完全対称の構造で、
   rebuild が万一 criteria を置き換えた場合に明確な失敗経路を提供する。

決定の不変性不変条件（PENDING → 1 遷移のみ）は state machine ``lookup`` 経路で
強制される。本モジュールはすべての ``model_validate`` で発火する構造的不変条件
のみを所有する。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from bakufu.domain.exceptions import ExternalReviewGateInvariantViolation
from bakufu.domain.value_objects import ReviewDecision

if TYPE_CHECKING:
    from bakufu.domain.value_objects import AcceptanceCriterion, AuditEntry, Deliverable

# Confirmation F: feedback_text 長境界（NFC、strip 無し）。
MIN_FEEDBACK_LENGTH: int = 0
MAX_FEEDBACK_LENGTH: int = 10_000


def _validate_decided_at_consistency(
    decision: ReviewDecision,
    decided_at: datetime | None,
) -> None:
    """``decision == PENDING`` ⇔ ``decided_at is None``（MSG-GT-002）。

    ``decision=APPROVED, decided_at=None``（decided_at 未設定の終端 Gate）または
    逆に ``decision=PENDING`` で ``decided_at`` が埋まっているといったリポジトリ
    行破損を検出する — どちらの形も構造的に違法。水和時に捕捉することで、
    アプリケーション層に一貫性のない Gate が渡されることを防ぐ。
    """
    is_pending = decision == ReviewDecision.PENDING
    has_timestamp = decided_at is not None
    if is_pending == (not has_timestamp):
        return
    decided_at_state = "set" if has_timestamp else "None"
    raise ExternalReviewGateInvariantViolation(
        kind="decided_at_inconsistent",
        message=(
            f"[FAIL] Gate decided_at consistency violation: "
            f"decision={decision.value}, decided_at={decided_at_state}\n"
            f"Next: decided_at must be None when decision==PENDING, "
            f"and a UTC tz-aware datetime otherwise; "
            f"check Repository row integrity."
        ),
        detail={
            "decision": decision.value,
            "decided_at_present": decided_at_state,
        },
    )


def _validate_feedback_text_range(feedback_text: str) -> None:
    """``0 <= len(NFC(feedback_text)) <= 10000``（MSG-GT-004）。"""
    length = len(feedback_text)
    if not (MIN_FEEDBACK_LENGTH <= length <= MAX_FEEDBACK_LENGTH):
        raise ExternalReviewGateInvariantViolation(
            kind="feedback_text_range",
            message=(
                f"[FAIL] Gate feedback_text must be "
                f"{MIN_FEEDBACK_LENGTH}-{MAX_FEEDBACK_LENGTH} characters "
                f"(got {length})\n"
                f"Next: Trim the comment/reason to "
                f"<={MAX_FEEDBACK_LENGTH} NFC-normalized characters."
            ),
            detail={"length": length},
        )


def _validate_audit_trail_append_only(
    previous: list[AuditEntry] | None,
    current: list[AuditEntry],
) -> None:
    """既存エントリはバイト等価のまま、リスト先頭に留まらなければならない（MSG-GT-005）。

    構築時（``previous is None``）は任意のリストを受理する — Aggregate の最初の
    インスタンスは、リポジトリ水和や発行側アプリケーション サービスが渡す内容を
    そのまま固定する。以降の ``_rebuild_with_state`` 呼び出しは下記を満たさな
    ければならない:

    1. ``len(current) >= len(previous)``（削除なし）。
    2. ``current[: len(previous)] == previous``（編集、並べ替え、prepend、
       中間挿入のいずれも無し）。

    §確定 C inputs/expectations 表が、本ガードが対象とする失敗ケースの正準参照。
    """
    if previous is None:
        return
    n = len(previous)
    if len(current) < n:
        raise ExternalReviewGateInvariantViolation(
            kind="audit_trail_append_only",
            message=(
                "[FAIL] Gate audit_trail violates append-only contract: "
                "existing entries cannot be modified or reordered\n"
                "Next: Only append new AuditEntry instances at the end; "
                "never edit, prepend, or delete existing entries."
            ),
            detail={
                "previous_length": n,
                "current_length": len(current),
                "violation": "deletion",
            },
        )
    if current[:n] != previous:
        raise ExternalReviewGateInvariantViolation(
            kind="audit_trail_append_only",
            message=(
                "[FAIL] Gate audit_trail violates append-only contract: "
                "existing entries cannot be modified or reordered\n"
                "Next: Only append new AuditEntry instances at the end; "
                "never edit, prepend, or delete existing entries."
            ),
            detail={
                "previous_length": n,
                "current_length": len(current),
                "violation": "modification_or_reorder",
            },
        )


def _validate_snapshot_immutable(
    previous: Deliverable | None,
    current: Deliverable,
) -> None:
    """構築時の ``deliverable_snapshot`` は置き換えられない（MSG-GT-003）。

    構築時（``previous is None``）は任意の Deliverable を受理する — Aggregate
    の最初のインスタンスは、アプリケーション サービスやリポジトリ水和が供給する
    値をそのまま固定する。以降の ``_rebuild_with_state`` 呼び出しは異なる
    スナップショットを渡しては **ならない**。実装コントラクト（§確定 D）は
    ``deliverable_snapshot`` を rebuild の引数集合から完全に外し、値が変更
    されないまま継承されるようにすること。本バリデータは、そのコントラクトが
    万一漏れた場合の失敗経路セーフティ ネット。
    """
    if previous is None:
        return
    if current != previous:
        raise ExternalReviewGateInvariantViolation(
            kind="snapshot_immutable",
            message=(
                "[FAIL] Gate deliverable_snapshot is immutable after construction\n"
                "Next: deliverable_snapshot is frozen at Gate creation; "
                "do not pass it to _rebuild_with_state. "
                "Issue a new Gate for a new deliverable."
            ),
            detail={
                "violation": "snapshot_changed",
            },
        )


def _validate_criteria_immutable(
    previous: tuple[AcceptanceCriterion, ...] | None,
    current: tuple[AcceptanceCriterion, ...],
) -> None:
    """構築時の ``required_deliverable_criteria`` は置き換えられない（MSG-GT-008）。

    構築時（``previous is None``）は任意のタプルを受理する — Aggregate の最初の
    インスタンスは、アプリケーション サービスやリポジトリ水和が供給する
    値をそのまま固定する。以降の ``_rebuild_with_state`` 呼び出しは異なる
    criteria を渡しては **ならない**。実装コントラクト（§確定 D'）は
    ``required_deliverable_criteria`` を rebuild の引数集合から完全に外し、値が
    変更されないまま継承されるようにすること。本バリデータは、そのコントラクトが
    万一漏れた場合の失敗経路セーフティ ネット（§確定 D の snapshot_immutable と
    完全対称の構造）。
    """
    if previous is None:
        return
    if current != previous:
        raise ExternalReviewGateInvariantViolation(
            kind="criteria_immutable",
            message=(
                "[FAIL] Gate required_deliverable_criteria is immutable after construction\n"
                "Next: required_deliverable_criteria is frozen at Gate creation; "
                "do not pass it to _rebuild_with_state. "
                "Issue a new Gate if criteria must change."
            ),
            detail={
                "violation": "criteria_changed",
            },
        )


__all__ = [
    "MAX_FEEDBACK_LENGTH",
    "MIN_FEEDBACK_LENGTH",
    "_validate_audit_trail_append_only",
    "_validate_criteria_immutable",
    "_validate_decided_at_consistency",
    "_validate_feedback_text_range",
    "_validate_snapshot_immutable",
]
