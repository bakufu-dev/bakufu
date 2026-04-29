"""Task ステートマシン: BLOCKED 契約 + pre-validate + ライフサイクル統合.

TC-UT-TS-007 (BLOCKED 非空 last_error 契約) + TC-UT-TS-038
(pre-validate は元 Task を変更しない) + TC-IT-TS-001〜005
(複数メソッドの統合シナリオ) + 13 ✓ 遷移全件における
``updated_at`` 単調増加。

``docs/features/task/test-design.md`` 準拠。Norman R-N1 に従い
``test_state_machine.py`` から分割 (633 → 3 ファイル)。
兄弟ファイルでテーブルロック + 13 ✓ セルおよび 47 ✗ セルを扱う。
"""

from __future__ import annotations

import contextlib
from uuid import uuid4

import pytest
from bakufu.domain.exceptions import TaskInvariantViolation
from bakufu.domain.task.state_machine import TRANSITIONS, TaskAction
from bakufu.domain.value_objects import TaskStatus

from tests.domain.task.test_task._helpers import (
    ALL_ACTIONS,
    invoke_action,
    make_task_in_status,
    next_ts,
)
from tests.factories.task import (
    make_deliverable,
    make_in_progress_task,
    make_task,
)


# ---------------------------------------------------------------------------
# TC-UT-TS-007: BLOCKED 契約 ── block() は空 last_error を拒絶する
# ---------------------------------------------------------------------------
class TestBlockRequiresNonEmptyLastError:
    """TC-UT-TS-007: ``block(reason, last_error='')`` は Fail-Fast。

    BUG-TSK-001 修正完了 (commit ``377366e``): ``Task._check_invariants``
    が ``_validate_blocked_has_last_error`` を
    ``_validate_last_error_consistency`` の **前** に走らせるようになり、
    空文字列経路では設計契約どおりの ``MSG-TS-006``
    (``blocked_requires_last_error``) ──「block() は非空 last_error を要する」
    の Next-action ヒントを発火する。下の単一 kind アサートで契約を固定し、
    順序を戻すリグレッションをここで検出する (寛容な ``or`` 集合の裏に
    隠れない)。
    """

    def test_block_with_empty_last_error_raises_blocked_requires_last_error(self) -> None:
        """``block(last_error='')`` は ``blocked_requires_last_error`` (MSG-TS-006) を発火する。"""
        task = make_in_progress_task()
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.block("retry exhausted", "", updated_at=next_ts(task))
        assert exc_info.value.kind == "blocked_requires_last_error", (
            f"[FAIL] block(empty last_error) raised {exc_info.value.kind!r}, expected "
            f"'blocked_requires_last_error' (MSG-TS-006).\n"
            f"Next: verify ``Task._check_invariants`` runs "
            f"``_validate_blocked_has_last_error`` BEFORE "
            f"``_validate_last_error_consistency`` — see BUG-TSK-001 fix "
            f"(commit 377366e)."
        )

    def test_block_with_too_long_last_error_raises(self) -> None:
        """10001 文字の ``last_error`` は MAX 超過で blocked_requires_last_error を発火する。

        過大長経路では consistency チェックは通過し
        (BLOCKED + 非空文字列は構造的に OK)、長さチェックが発火する ──
        BUG-TSK-001 修正後は空文字列経路と同じ kind になる。
        """
        task = make_in_progress_task()
        too_long = "x" * 10_001
        with pytest.raises(TaskInvariantViolation) as exc_info:
            task.block("oops", too_long, updated_at=next_ts(task))
        assert exc_info.value.kind == "blocked_requires_last_error"


# ---------------------------------------------------------------------------
# TC-UT-TS-038: assign 失敗時に元 Task は不変 (§確定 A)
# ---------------------------------------------------------------------------
class TestPreValidateLeavesOriginalUntouched:
    """TC-UT-TS-038: 失敗した behavior 呼び出しは元 Task を変更しない。

    §確定 A の pre-validate rebuild 経路は、behavior が新 Task を返すか
    例外を発するかのいずれかで、元インスタンスを部分的に変更しない。
    違法アクションを試みた後で、元 Task の全属性集合を検査することで
    保証を確認する。
    """

    def test_failed_assign_on_in_progress_keeps_original_unchanged(self) -> None:
        """IN_PROGRESS に対する ``assign`` は例外を発し、元 Task に触れない。"""
        original = make_in_progress_task()
        snapshot = original.model_dump()

        with pytest.raises(TaskInvariantViolation):
            original.assign([uuid4()], updated_at=next_ts(original))

        # 失敗呼び出し後も全フィールドはバイト等価。
        assert original.model_dump() == snapshot


# ---------------------------------------------------------------------------
# 統合シナリオ (TC-IT-TS-001〜005)
# ---------------------------------------------------------------------------
class TestLifecycleIntegration:
    """Aggregate 内部「統合」── 複数メソッドのラウンドトリップシナリオ。"""

    def test_pending_to_done_full_lifecycle(self) -> None:
        """TC-IT-TS-002: PENDING → IN_PROGRESS → AWAITING → IN_PROGRESS → DONE。

        §確定 A-2 の 4 メソッド分離 (approve_review + complete) を
        端から端まで歩く。最終 DONE 状態は後続全アクションを拒絶せねばならない。
        """
        task = make_task()
        agent_a = uuid4()
        stage_a = task.current_stage_id

        # Step 1: assign → IN_PROGRESS
        task = task.assign([agent_a], updated_at=next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS

        # Step 2: commit_deliverable
        d1 = make_deliverable(stage_id=stage_a)
        task = task.commit_deliverable(
            stage_id=stage_a,
            deliverable=d1,
            by_agent_id=agent_a,
            updated_at=next_ts(task),
        )
        assert task.deliverables[stage_a] == d1

        # Step 3: request_external_review → AWAITING
        task = task.request_external_review(updated_at=next_ts(task))
        assert task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

        # Step 4: approve_review → 次ステージで IN_PROGRESS
        stage_b = uuid4()
        task = task.approve_review(uuid4(), uuid4(), stage_b, updated_at=next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.current_stage_id == stage_b

        # Step 5: commit + complete
        d2 = make_deliverable(stage_id=stage_b)
        task = task.commit_deliverable(
            stage_id=stage_b,
            deliverable=d2,
            by_agent_id=agent_a,
            updated_at=next_ts(task),
        )
        task = task.complete(uuid4(), uuid4(), updated_at=next_ts(task))
        assert task.status == TaskStatus.DONE
        assert len(task.deliverables) == 2

        # DONE は後続全アクションを拒絶 (新規 Task に対する TestTerminalGate
        # との交差確認)。
        for action in ALL_ACTIONS:
            with pytest.raises(TaskInvariantViolation) as exc_info:
                invoke_action(task, action)
            assert exc_info.value.kind == "terminal_violation"

    def test_blocked_recovery_to_done(self) -> None:
        """TC-IT-TS-003: IN_PROGRESS → BLOCKED → IN_PROGRESS → DONE。

        §確定 D の ``last_error`` クリア契約を検証する: ``unblock_retry``
        後は IN_PROGRESS に戻り ``last_error is None`` で正常完了できる。
        """
        task = make_in_progress_task()
        agent = task.assigned_agent_ids[0]
        stage = task.current_stage_id

        # last_error に webhook URL を含めて block する ── auto-mask は
        # 例外層で発動するが、Task 自体は NFC 正規化された生形を保持する
        # (Repository 側の masking は workflow-repository の関心事)。
        last_err = "AuthExpired: https://discord.com/api/webhooks/123456789012345678/SecretToken-x"
        task = task.block("auth retry exhausted", last_err, updated_at=next_ts(task))
        assert task.status == TaskStatus.BLOCKED
        assert task.last_error is not None
        assert task.last_error == last_err  # Aggregate は生形のまま保持する

        # Unblock → IN_PROGRESS に戻り、last_error クリア。
        task = task.unblock_retry(updated_at=next_ts(task))
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.last_error is None

        # commit + complete。
        d = make_deliverable(stage_id=stage)
        task = task.commit_deliverable(
            stage_id=stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=next_ts(task),
        )
        task = task.complete(uuid4(), uuid4(), updated_at=next_ts(task))
        assert task.status == TaskStatus.DONE

    def test_reject_review_and_resubmit_loop(self) -> None:
        """TC-IT-TS-005: AWAITING → IN_PROGRESS (reject による rollback) → 再 review → DONE。

        ``reject_review`` が真のラウンドトリップ経路となることを検証する:
        reject された Task は別の ``current_stage_id`` を経て戻ってきて、
        再投稿し、最終的に完了できる。
        """
        task = make_task_in_status(TaskStatus.AWAITING_EXTERNAL_REVIEW)
        agent = task.assigned_agent_ids[0]

        # Reject ── 「rollback」ステージへ戻す。
        rollback_stage = uuid4()
        task = task.reject_review(
            uuid4(),
            uuid4(),
            rollback_stage,
            updated_at=next_ts(task),
        )
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.current_stage_id == rollback_stage

        # 再 commit + 再 review。
        d = make_deliverable(stage_id=rollback_stage)
        task = task.commit_deliverable(
            stage_id=rollback_stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=next_ts(task),
        )
        task = task.request_external_review(updated_at=next_ts(task))
        assert task.status == TaskStatus.AWAITING_EXTERNAL_REVIEW

        # 今度は approve → 次ステージで IN_PROGRESS。
        next_stage = uuid4()
        task = task.approve_review(
            uuid4(),
            uuid4(),
            next_stage,
            updated_at=next_ts(task),
        )
        assert task.current_stage_id == next_stage

        # complete。
        task = task.complete(uuid4(), uuid4(), updated_at=next_ts(task))
        assert task.status == TaskStatus.DONE

    def test_assign_failure_then_alternate_action_succeeds(self) -> None:
        """TC-IT-TS-001: 失敗した ``assign`` が後続の正当アクションを壊さないことを検証する。

        Confirmation H: pre-validate は連続的な失敗 + 再試行を経ても
        Task 状態をクリーンに保つ。IN_PROGRESS への違法 ``assign`` 後でも
        ``commit_deliverable`` は成功するはず (隠れた状態破壊なしを示す)。
        """
        task = make_in_progress_task()
        agent = task.assigned_agent_ids[0]
        stage = task.current_stage_id

        with pytest.raises(TaskInvariantViolation):
            task.assign([uuid4()], updated_at=next_ts(task))

        # 元 Task は不変 → ``commit_deliverable`` が成功する。
        d = make_deliverable(stage_id=stage)
        out = task.commit_deliverable(
            stage_id=stage,
            deliverable=d,
            by_agent_id=agent,
            updated_at=next_ts(task),
        )
        assert out.status == TaskStatus.IN_PROGRESS
        assert out.deliverables[stage] == d

    def test_cancel_from_each_state_clears_last_error(self) -> None:
        """TC-IT-TS-004: PENDING / IN_PROGRESS / AWAITING / BLOCKED
        いずれからの cancel も last_error をクリア。

        兄弟ファイルの ``test_cancel_from_each_of_four_states`` を、
        BLOCKED 起点経路 (cancel 前は ``last_error`` が非空) も含めて
        ``last_error=None`` の事後条件アサートを明示する形で繰り返す。
        """
        for status in (
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.AWAITING_EXTERNAL_REVIEW,
            TaskStatus.BLOCKED,
        ):
            task = make_task_in_status(status)
            with contextlib.suppress(TaskInvariantViolation):
                # PENDING ファクトリは既に last_error=None を返す。
                # 残るファクトリも BLOCKED (合成文字列を持つ) を除いて
                # None のまま。
                pass
            out = task.cancel(uuid4(), "manual abort", updated_at=next_ts(task))
            assert out.status == TaskStatus.CANCELLED
            assert out.last_error is None


# ---------------------------------------------------------------------------
# 到達性確認: IN_PROGRESS に入る全メソッドが updated_at を更新する
# ---------------------------------------------------------------------------
class TestUpdatedAtAdvances:
    """全許可遷移は ``updated_at`` を厳密に前進させなければならない。"""

    @pytest.mark.parametrize(
        "status",
        [
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
            TaskStatus.AWAITING_EXTERNAL_REVIEW,
            TaskStatus.BLOCKED,
        ],
        ids=lambda s: s.value,
    )
    def test_allowed_action_advances_updated_at(self, status: TaskStatus) -> None:
        """全合法 (status, action) で結果の ``updated_at`` が厳密に未来であることを保証する。"""
        # ``TRANSITIONS`` のキーは (TaskStatus, TaskAction) のタプルだが、
        # iteration では Literal narrowing が消える ── action を
        # TaskAction として明示的に注釈する。
        legal_actions: list[TaskAction] = [a for (s, a) in TRANSITIONS if s == status]
        assert legal_actions, f"status {status} has zero legal actions"
        for action in legal_actions:
            task = make_task_in_status(status)
            # block は非空 last_error を要し、ヘルパが透過する。
            # commit_deliverable は stage_id 一致の Deliverable を要する ──
            # いずれも invoke_action 内で吸収される。
            try:
                out = invoke_action(task, action)
            except TaskInvariantViolation:  # pragma: no cover - defensive
                pytest.fail(
                    f"Allowed transition ({status.value}, {action}) raised — contract regression."
                )
            assert out.updated_at > task.updated_at, (
                f"({status.value}, {action}): updated_at did not advance."
            )
