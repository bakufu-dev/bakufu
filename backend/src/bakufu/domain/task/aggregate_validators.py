""":class:`Task` のための Aggregate レベル不変条件ヘルパ。

各ヘルパは **モジュール レベルの純粋関数** であるため、テストから ``import``
して直接呼べる — Norman / Steve が agent / room / directive の
``aggregate_validators.py`` モジュール（M1 5 兄弟）で承認したのと同じテスタ
ビリティ パターン。

ヘルパ:

1. :func:`_validate_assigned_agents_unique` — ``assigned_agent_ids`` に重複
   ``AgentId`` を含めない。
2. :func:`_validate_assigned_agents_capacity` — Task あたり最大 5 エージェント。
3. :func:`_validate_last_error_consistency` — ``status == BLOCKED`` ⇔
   ``last_error`` が非空文字列。それ以外では ``last_error is None``。水和時に
   リポジトリ側の行破損を検出する。
4. :func:`_validate_blocked_has_last_error` — ``status == BLOCKED`` のとき、
   ``last_error`` の長さ（NFC コードポイント）は 1〜10000 でなければならない。
   §確定 R1-C「strip 無し」ルールと構造的一貫性チェックを橋渡しする。
5. :func:`_validate_timestamp_order` — ``created_at <= updated_at``。

すべてのヘルパは §確定 J に対応する ``kind`` 識別子を持つ
:class:`TaskInvariantViolation` を送出する。``message`` 文字列は 2 行の
「[FAIL] ... / Next: ...」構造（§確定 J § MSG ID 確定文言）に従うため、
CI アサート ``assert "Next:" in str(exc)``（TC-UT-TS-046〜052）が全経路で
一貫して発火する。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from uuid import UUID

from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.value_objects import TaskStatus

# Confirmation A: detailed-design §クラス設計 で凍結されたハード上限。
MAX_ASSIGNED_AGENTS: int = 5
MIN_LAST_ERROR_LENGTH: int = 1
MAX_LAST_ERROR_LENGTH: int = 10_000


def _validate_assigned_agents_unique(assigned_agent_ids: list[UUID]) -> None:
    """``assigned_agent_ids`` に重複値を含めない（MSG-TS-003）。"""
    counts = Counter(assigned_agent_ids)
    duplicates = sorted({str(agent_id) for agent_id, count in counts.items() if count > 1})
    if duplicates:
        raise TaskInvariantViolation(
            kind="assigned_agents_unique",
            message=(
                f"[FAIL] Task assigned_agent_ids must not contain duplicates: "
                f"duplicates={duplicates}\n"
                f"Next: Deduplicate the agent_ids list before calling assign(); "
                f"each Agent may appear at most once."
            ),
            detail={"duplicates": duplicates},
        )


def _validate_assigned_agents_capacity(assigned_agent_ids: list[UUID]) -> None:
    """``len(assigned_agent_ids) <= MAX_ASSIGNED_AGENTS``（MSG-TS-004）。"""
    count = len(assigned_agent_ids)
    if count > MAX_ASSIGNED_AGENTS:
        raise TaskInvariantViolation(
            kind="assigned_agents_capacity",
            message=(
                f"[FAIL] Task assigned_agent_ids exceeds capacity: "
                f"got {count}, max {MAX_ASSIGNED_AGENTS}\n"
                f"Next: Reduce the number of assigned agents to "
                f"<={MAX_ASSIGNED_AGENTS}; split work into multiple Tasks "
                f"if more parallelism is needed."
            ),
            detail={"count": count, "max": MAX_ASSIGNED_AGENTS},
        )


def _validate_last_error_consistency(
    status: TaskStatus,
    last_error: str | None,
) -> None:
    """``status == BLOCKED`` ⇔ ``last_error`` が非空文字列（MSG-TS-005）。

    ``status=DONE, last_error='AuthExpired: ...'`` のようなリポジトリ行破損
    （エラー テキストが残った終端 Task）を検出する — その組み合わせは構造的に
    違法であり、ここで捕捉することで水和経路が一貫性のない状態をアプリケーション
    層に持ち込めなくなる。
    """
    is_blocked = status == TaskStatus.BLOCKED
    has_error = isinstance(last_error, str) and last_error != ""
    if is_blocked == has_error:
        return
    last_error_present = "non-empty" if has_error else ("empty" if last_error == "" else "None")
    raise TaskInvariantViolation(
        kind="last_error_consistency",
        message=(
            f"[FAIL] Task last_error consistency violation: "
            f"status={status.value} but last_error={last_error_present}\n"
            f"Next: last_error must be a non-empty string when status==BLOCKED, "
            f"and None otherwise; check Repository row integrity."
        ),
        detail={
            "status": status.value,
            "last_error_present": last_error_present,
        },
    )


def _validate_blocked_has_last_error(
    status: TaskStatus,
    last_error: str | None,
) -> None:
    """``status == BLOCKED`` のとき ``last_error`` の長さは 1〜10000（MSG-TS-006）。

    §確定 R1-C に従い、チェックは **NFC 正規化済み** 文字列に対して行う —
    呼び元（``Task.block()``）が上流で正規化を実行するため、本ヘルパは正準形を
    見る。``strip`` は意図的に **適用しない**: LLM のスタック トレースは
    インデントのために先頭空白に依存する。
    """
    if status != TaskStatus.BLOCKED:
        return
    # ``None`` は長さ 0 で通過させる。これにより kind=blocked_requires_last_error の
    # メッセージは「BLOCKED だが文字列が空」に特化したものになる。
    # 構造形は ``_validate_last_error_consistency`` が既に捕捉している。
    length = 0 if last_error is None else len(last_error)
    if not (MIN_LAST_ERROR_LENGTH <= length <= MAX_LAST_ERROR_LENGTH):
        raise TaskInvariantViolation(
            kind="blocked_requires_last_error",
            message=(
                f"[FAIL] Task block() requires non-empty last_error "
                f"(got NFC-normalized length={length})\n"
                f"Next: Provide a non-empty last_error string "
                f"({MIN_LAST_ERROR_LENGTH}-{MAX_LAST_ERROR_LENGTH} chars) "
                f"describing why the Task is blocked; an empty string is rejected."
            ),
            detail={
                "length": length,
                "min": MIN_LAST_ERROR_LENGTH,
                "max": MAX_LAST_ERROR_LENGTH,
            },
        )


def _validate_timestamp_order(created_at: datetime, updated_at: datetime) -> None:
    """``created_at <= updated_at``（MSG-TS-007）。"""
    if created_at > updated_at:
        raise TaskInvariantViolation(
            kind="timestamp_order",
            message=(
                f"[FAIL] Task timestamp order violation: "
                f"created_at={created_at.isoformat()} > "
                f"updated_at={updated_at.isoformat()}\n"
                f"Next: Verify timestamp generation; updated_at must be "
                f">= created_at, both UTC tz-aware."
            ),
            detail={
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat(),
            },
        )


__all__ = [
    "MAX_ASSIGNED_AGENTS",
    "MAX_LAST_ERROR_LENGTH",
    "MIN_LAST_ERROR_LENGTH",
    "_validate_assigned_agents_capacity",
    "_validate_assigned_agents_unique",
    "_validate_blocked_has_last_error",
    "_validate_last_error_consistency",
    "_validate_timestamp_order",
]
