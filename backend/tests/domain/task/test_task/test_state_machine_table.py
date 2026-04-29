"""Task state machine: テーブルロック + 13 許可遷移。

TC-UT-TS-039 (§確定 B table immutability) + TC-UT-TS-003 / 008 /
030〜035 + cancel x 4 (§確定 A-2 dispatch table 13 ✓ cells)。

``docs/features/task/test-design.md`` に従う。``test_state_machine.py``
から Norman R-N1 に従い分割 (633 → 3 ファイル)。関連ファイルは
**47 ✗ cells** と **ライフサイクル統合** をカバー:

* :mod:`...test_task.test_state_terminal_and_invalid` — 20 ターミナル
  ✗ + 27 illegal-non-terminal ✗ cells (MSG-TS-001 / MSG-TS-002)。
* :mod:`...test_task.test_state_lifecycle` — BLOCKED 契約 +
  pre-validate + multi-method integration scenarios + updated_at
  単調性。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from bakufu.domain.task import Task
from bakufu.domain.task.state_machine import TRANSITIONS
from bakufu.domain.value_objects import Deliverable, TaskStatus

from tests.domain.task.test_task._helpers import (
    make_task_in_status,
    next_ts,
)
from tests.factories.task import (
    make_blocked_task,
    make_deliverable,
    make_in_progress_task,
    make_task,
)


# ---------------------------------------------------------------------------
# §確定 B: state machine TABLE shape + immutability (TC-UT-TS-039)
# ---------------------------------------------------------------------------
class TestStateMachineTableLocked:
    """TC-UT-TS-039: ``TRANSITIONS`` が 13 エントリを持ち mutation を reject。"""

    def test_table_size_is_thirteen(self) -> None:
        """§確定 A-2 dispatch table は 13 個の許可遷移を freeze。"""
        assert len(TRANSITIONS) == 13, (
            f"[FAIL] state machine table size が drift: got {len(TRANSITIONS)}, expected 13.\n"
            f"Next: docs/features/task/detailed-design.md §確定 A-2 が 13 transitions を freeze; "
            f"design を更新せずに state_machine.py を編集することは契約違反。"
        )

    def test_table_setitem_rejected_at_runtime(self) -> None:
        """``TRANSITIONS[k] = v`` が ``TypeError`` を raise (MappingProxyType lock)。"""
        with pytest.raises(TypeError):
            TRANSITIONS[(TaskStatus.DONE, "assign")] = TaskStatus.IN_PROGRESS  # pyright: ignore[reportIndexIssue]


# ---------------------------------------------------------------------------
# 13 許可遷移 — ✓ cell ごと 1 つのポジティブケース
# ---------------------------------------------------------------------------
class TestThirteenAllowedTransitions:
    """TC-UT-TS-003 / 008 / 030〜035 + cancel x 4 = 13 ✓ cells。"""

    # PENDING → IN_PROGRESS（assign 経由）
    def test_assign_pending_to_in_progress(self) -> None:
        """TC-UT-TS-003: PENDING で ``assign`` が IN_PROGRESS に移行。"""
        task = make_task()
        agent_a = uuid4()
        out = task.assign([agent_a], updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.assigned_agent_ids == [agent_a]
        # 元のタスク変更なし (frozen + pre-validate)
        assert task.status == TaskStatus.PENDING

    # IN_PROGRESS の self-loop（commit_deliverable 経由）
    def test_commit_deliverable_self_loop(self) -> None:
        """TC-UT-TS-030: IN_PROGRESS で ``commit_deliverable`` がステータス保持、エントリ追加。"""
        task = make_in_progress_task()
        deliverable = make_deliverable(stage_id=task.current_stage_id)
        out = task.commit_deliverable(
            stage_id=task.current_stage_id,
            deliverable=deliverable,
            by_agent_id=task.assigned_agent_ids[0],
            updated_at=next_ts(task),
        )
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.deliverables[task.current_stage_id] == deliverable
        assert out.updated_at > task.updated_at

    # IN_PROGRESS → AWAITING（request_external_review 経由）
    def test_request_external_review_to_awaiting(self) -> None:
        """TC-UT-TS-031: IN_PROGRESS → AWAITING_EXTERNAL_REVIEW。"""
        task = make_in_progress_task()
        out = task.request_external_review(updated_at=next_ts(task))
        assert out.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

    # AWAITING → IN_PROGRESS（approve_review 経由、Gate APPROVED）
    def test_approve_review_back_to_in_progress(self) -> None:
        """TC-UT-TS-032: ``approve_review`` が current_stage_id を前進。"""
        task = make_task_in_status(TaskStatus.AWAITING_EXTERNAL_REVIEW)
        next_stage = uuid4()
        out = task.approve_review(uuid4(), uuid4(), next_stage, updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.current_stage_id == next_stage

    # AWAITING → IN_PROGRESS（reject_review 経由、Gate REJECTED）
    def test_reject_review_back_to_in_progress(self) -> None:
        """TC-UT-TS-032b: ``reject_review`` が current_stage_id をロールバック。"""
        task = make_task_in_status(TaskStatus.AWAITING_EXTERNAL_REVIEW)
        rollback_stage = uuid4()
        out = task.reject_review(uuid4(), uuid4(), rollback_stage, updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.current_stage_id == rollback_stage

    # IN_PROGRESS の self-loop（advance_to_next 経由）
    def test_advance_to_next_keeps_in_progress(self) -> None:
        """TC-UT-TS-032c: ``advance_to_next`` が current_stage_id を更新、ステータス変更なし。"""
        task = make_in_progress_task()
        next_stage = uuid4()
        out = task.advance_to_next(uuid4(), uuid4(), next_stage, updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.current_stage_id == next_stage

    # IN_PROGRESS → DONE（complete 経由）
    def test_complete_terminates_at_done(self) -> None:
        """TC-UT-TS-033: ``complete`` はターミナル遷移。

        ``current_stage_id`` は意図的にそのまま残して、
        ダウンストリーム consumer が最後のステージを読める。
        """
        task = make_in_progress_task()
        original_stage = task.current_stage_id
        out = task.complete(uuid4(), uuid4(), updated_at=next_ts(task))
        assert out.status == TaskStatus.DONE
        assert out.current_stage_id == original_stage

    # IN_PROGRESS → BLOCKED（block 経由）
    def test_block_attaches_last_error(self) -> None:
        """TC-UT-TS-035: ``block`` は non-empty last_error が必須。"""
        task = make_in_progress_task()
        out = task.block("auth retry exhausted", "AuthExpired: ...", updated_at=next_ts(task))
        assert out.status == TaskStatus.BLOCKED
        assert out.last_error == "AuthExpired: ..."

    # BLOCKED → IN_PROGRESS（unblock_retry 経由、last_error はクリア、§確定 D）
    def test_unblock_retry_clears_last_error(self) -> None:
        """TC-UT-TS-008: ``unblock_retry`` が last_error を None にクリア (§確定 D)。"""
        task = make_blocked_task(last_error="AuthExpired: synthetic")
        out = task.unblock_retry(updated_at=next_ts(task))
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.last_error is None

    # 4 つの非ターミナル状態それぞれからの cancel（§確定 E）
    @pytest.mark.parametrize(
        "starting_status",
        [
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.AWAITING_EXTERNAL_REVIEW,
            TaskStatus.BLOCKED,
        ],
        ids=lambda s: s.value,
    )
    def test_cancel_from_each_of_four_states(self, starting_status: TaskStatus) -> None:
        """TC-UT-TS-034: ``cancel`` が PENDING/IN_PROG/AWAITING/BLOCKED から CANCELLED に到達。

        §確定 E はこれらの 4 つの開始状態を列挙；
        ``last_error`` は None にリセットして整合性 invariant を満たす。
        """
        task = make_task_in_status(starting_status)
        out = task.cancel(uuid4(), "manual abort", updated_at=next_ts(task))
        assert out.status == TaskStatus.CANCELLED
        assert out.last_error is None


# Deliverable / Task をダウンストリームの型チェッカ用にインポート
_ = Deliverable, Task
