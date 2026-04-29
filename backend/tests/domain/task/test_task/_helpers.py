"""Task ステートマシンテスト分割のための共有ヘルパ.

元の test_state_machine.py は 633 行。Norman R-N1 に従い 3 つの
兄弟ファイル（test_state_machine_table.py /
test_state_terminal_and_invalid.py / test_state_lifecycle.py）に分割。
以下の 5 つのモジュールレベルヘルパは各 2～3 ファイルから参照。
ここで抽出してすべて 500 行ルール以下に保持。~80 行の fixture
機構を複製しない。

アンダースコア プレフィックス（_helpers.py）はモジュールを
パッケージプライベートに指定。pytest discovery は test_ プレフィックス
がないファイルを照合しないため、ヘルパは自動的に収集テスト セットから
外れる。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from bakufu.domain.task import Task
from bakufu.domain.task.state_machine import TaskAction
from bakufu.domain.value_objects import TaskStatus

from tests.factories.task import (
    make_awaiting_review_task,
    make_blocked_task,
    make_cancelled_task,
    make_deliverable,
    make_done_task,
    make_in_progress_task,
    make_task,
)

# All 10 action names — must match Task method names 1:1 (§確定 A-2).
ALL_ACTIONS: list[TaskAction] = [
    "assign",
    "commit_deliverable",
    "request_external_review",
    "approve_review",
    "reject_review",
    "advance_to_next",
    "complete",
    "block",
    "unblock_retry",
    "cancel",
]

# All 6 status values — sanity bound for the 60-cell matrix.
ALL_STATUSES: list[TaskStatus] = list(TaskStatus)


def next_ts(task: Task) -> datetime:
    """updated_at 用に厳密に未来の UTC タイムスタンプを返す."""
    return task.updated_at + timedelta(seconds=1)


def invoke_action(task: Task, action: TaskAction, *, agent_id: UUID | None = None) -> Task:
    """使い捨ての妥当な引数で task に action をディスパッチ.

    アクションごとのシグネチャを集約。parametrize された
    「全ての違法セルが例外を発火」テストが 10 メソッドを
    均一に呼び出せるようにする。メソッド固有の引数形状を
    繰り返さない。
    """
    ts = next_ts(task)
    if action == "assign":
        return task.assign([agent_id or uuid4()], updated_at=ts)
    if action == "commit_deliverable":
        return task.commit_deliverable(
            stage_id=task.current_stage_id,
            deliverable=make_deliverable(),
            by_agent_id=agent_id or uuid4(),
            updated_at=ts,
        )
    if action == "request_external_review":
        return task.request_external_review(updated_at=ts)
    if action == "approve_review":
        return task.approve_review(uuid4(), uuid4(), uuid4(), updated_at=ts)
    if action == "reject_review":
        return task.reject_review(uuid4(), uuid4(), uuid4(), updated_at=ts)
    if action == "advance_to_next":
        return task.advance_to_next(uuid4(), uuid4(), uuid4(), updated_at=ts)
    if action == "complete":
        return task.complete(uuid4(), uuid4(), updated_at=ts)
    if action == "block":
        return task.block("synthetic reason", "synthetic last_error", updated_at=ts)
    if action == "unblock_retry":
        return task.unblock_retry(updated_at=ts)
    # cancel
    return task.cancel(uuid4(), "synthetic cancel reason", updated_at=ts)


def make_task_in_status(status: TaskStatus) -> Task:
    """指定状態の Task を対応するファクトリで構築."""
    if status == TaskStatus.PENDING:
        return make_task()
    if status == TaskStatus.IN_PROGRESS:
        return make_in_progress_task()
    if status == TaskStatus.AWAITING_EXTERNAL_REVIEW:
        return make_awaiting_review_task()
    if status == TaskStatus.BLOCKED:
        return make_blocked_task()
    if status == TaskStatus.DONE:
        return make_done_task()
    return make_cancelled_task()


__all__ = [
    "ALL_ACTIONS",
    "ALL_STATUSES",
    "invoke_action",
    "make_task_in_status",
    "next_ts",
]
