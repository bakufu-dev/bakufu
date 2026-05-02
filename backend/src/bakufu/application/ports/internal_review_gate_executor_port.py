"""InternalReviewGateExecutorPort — INTERNAL_REVIEW Stage 実行委譲 Port（REQ-ME-007）。

M5-B（#164）はこの Protocol を実装する ``InternalReviewGateExecutor`` を
``infrastructure/reviewers/`` に配置する。Protocol を使うことで M5-B が
``application/`` を import しない（依存方向の保全）。

設計書: docs/features/stage-executor/application/detailed-design.md §確定 G
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from bakufu.domain.value_objects import GateRole, StageId, TaskId


@runtime_checkable
class InternalReviewGateExecutorPort(Protocol):
    """INTERNAL_REVIEW Stage の実行委譲インターフェース（REQ-ME-007）。

    ``execute()`` は Gate 判定完了（全 GateRole が APPROVED または 1 件でも
    REJECTED）まで ``await`` する **long-running coroutine**（§確定 G）。
    呼び出し元 StageWorker は ``await execute()`` の返却をもって Semaphore を
    release する。タイムアウト・エラー時は例外を送出し、呼び出し元の
    REQ-ME-002 エラーハンドリングが Task.block() に帰着させる。

    M5-A では ``_NullInternalReviewGateExecutor``（NotImplementedError）を使用する。
    M5-B でこの Protocol の実装を追加する。
    """

    async def execute(
        self,
        task_id: TaskId,
        stage_id: StageId,
        required_gate_roles: frozenset[GateRole],
    ) -> None:
        """INTERNAL_REVIEW Gate を実行し、判定完了まで待機する（§確定 G）。

        Args:
            task_id: 対象 Task の識別子。
            stage_id: 対象 INTERNAL_REVIEW Stage の識別子。
            required_gate_roles: Gate 判定に必要な GateRole の集合。

        Raises:
            NotImplementedError: M5-A の null stub 実装。
            任意の例外: エラー発生時に送出し、呼び出し元が Task.block() に帰着させる。
        """
        ...


__all__ = ["InternalReviewGateExecutorPort"]
