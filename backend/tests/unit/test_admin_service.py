"""AdminService ユニットテスト（TC-UT-AC-001〜014）。

設計書: docs/features/admin-cli/application/test-design.md §ユニットテストケース

全 Port を AsyncMock でスタブ化し、AdminService のビジネスロジック（Fail Fast
検証 / audit_log 記録タイミング / actor DI / 確定文言）を DB 接続なしで検証する。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID, uuid4

import pytest

from bakufu.application.exceptions.task_exceptions import IllegalTaskStateError, TaskNotFoundError
from bakufu.application.ports.outbox_event_repository import OutboxEventView
from bakufu.application.services.admin_service import AdminService
from bakufu.domain.exceptions.outbox import IllegalOutboxStateError, OutboxEventNotFoundError
from bakufu.domain.value_objects import TaskStatus

from tests.factories.task import (
    make_blocked_task,
    make_cancelled_task,
    make_done_task,
    make_in_progress_task,
)

# asyncio mark はクラスレベルで設定（sync テストクラスには付けない）


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    task_repo: object | None = None,
    outbox_event_repo: object | None = None,
    audit_log_writer: object | None = None,
    actor: str = "test_actor",
) -> AdminService:
    """全 Port を AsyncMock でスタブした AdminService を構築する。"""
    return AdminService(
        task_repo=task_repo or AsyncMock(),
        outbox_event_repo=outbox_event_repo or AsyncMock(),
        audit_log_writer=audit_log_writer or AsyncMock(),
        actor=actor,
    )


def _make_outbox_view(
    *,
    event_id: UUID | None = None,
    status: str = "DEAD_LETTER",
    attempt_count: int = 3,
    last_error: str | None = "some error",
) -> OutboxEventView:
    return OutboxEventView(
        event_id=event_id or uuid4(),
        event_kind="TestEventEmitted",
        aggregate_id=uuid4(),
        status=status,
        attempt_count=attempt_count,
        last_error=last_error,
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# TC-UT-AC-001/002: _write_audit() の result=OK / FAIL 引数確認
# ---------------------------------------------------------------------------


class TestWriteAudit:
    """TC-UT-AC-001/002: audit_log_writer.write() が正しい引数で呼ばれる。"""

    pytestmark = pytest.mark.asyncio

    async def test_write_audit_ok_on_success(self) -> None:
        """TC-UT-AC-001: 成功時 audit_log_writer.write() に result='OK' / error_text=None が渡される。"""
        audit_log_writer = AsyncMock()
        task_repo = AsyncMock()
        task_repo.find_blocked.return_value = []

        service = _make_service(
            task_repo=task_repo,
            audit_log_writer=audit_log_writer,
        )
        await service.list_blocked_tasks()

        audit_log_writer.write.assert_called_once()
        _, kwargs = audit_log_writer.write.call_args
        assert kwargs["result"] == "OK"
        assert kwargs["error_text"] is None

    async def test_write_audit_fail_on_error(self) -> None:
        """TC-UT-AC-002: 失敗時 audit_log_writer.write() に result='FAIL' / error_text が渡される。"""
        audit_log_writer = AsyncMock()
        task_repo = AsyncMock()
        task_repo.find_by_id.return_value = None  # 存在しない → TaskNotFoundError

        service = _make_service(task_repo=task_repo, audit_log_writer=audit_log_writer)

        with pytest.raises(TaskNotFoundError):
            await service.retry_task(uuid4())

        audit_log_writer.write.assert_called_once()
        _, kwargs = audit_log_writer.write.call_args
        assert kwargs["result"] == "FAIL"
        assert kwargs["error_text"] is not None


# ---------------------------------------------------------------------------
# TC-UT-AC-003/004: try/finally audit_log 保証（§確定 A）
# ---------------------------------------------------------------------------


class TestAuditLogFinally:
    """TC-UT-AC-003/004: 例外発生後も audit_log が記録される（§確定 A / try/finally 保証）。"""

    pytestmark = pytest.mark.asyncio

    async def test_retry_task_audit_written_even_on_task_not_found(self) -> None:
        """TC-UT-AC-003: find_by_id が None → TaskNotFoundError 送出 AND audit_log FAIL 記録。"""
        audit_log_writer = AsyncMock()
        task_repo = AsyncMock()
        task_repo.find_by_id.return_value = None

        service = _make_service(task_repo=task_repo, audit_log_writer=audit_log_writer)

        with pytest.raises(TaskNotFoundError):
            await service.retry_task(uuid4())

        # try/finally 保証: 例外後も write() が呼ばれる
        assert audit_log_writer.write.call_count == 1
        _, kwargs = audit_log_writer.write.call_args
        assert kwargs["result"] == "FAIL"

    async def test_cancel_task_audit_written_even_on_illegal_state(self) -> None:
        """TC-UT-AC-004: DONE Task の cancel → IllegalTaskStateError 送出 AND audit_log FAIL 記録。"""
        audit_log_writer = AsyncMock()
        task_repo = AsyncMock()
        done_task = make_done_task()
        task_repo.find_by_id.return_value = done_task

        service = _make_service(task_repo=task_repo, audit_log_writer=audit_log_writer)

        with pytest.raises(IllegalTaskStateError):
            await service.cancel_task(done_task.id, reason="test")

        assert audit_log_writer.write.call_count == 1
        _, kwargs = audit_log_writer.write.call_args
        assert kwargs["result"] == "FAIL"


# ---------------------------------------------------------------------------
# TC-UT-AC-005/006: Fail Fast 検証（§確定 B）
# ---------------------------------------------------------------------------


class TestFailFast:
    """TC-UT-AC-005/006: Fail Fast 検証 — 不正ステータス → 即座に例外（§確定 B）。"""

    pytestmark = pytest.mark.asyncio

    async def test_retry_done_task_raises_illegal_state(self) -> None:
        """TC-UT-AC-005: DONE Task retry → IllegalTaskStateError（task.unblock_retry 未呼び出し）。"""
        task_repo = AsyncMock()
        done_task = make_done_task()
        task_repo.find_by_id.return_value = done_task

        service = _make_service(task_repo=task_repo)

        with pytest.raises(IllegalTaskStateError):
            await service.retry_task(done_task.id)

        # unblock_retry が呼ばれないことを確認（save が呼ばれない）
        task_repo.save.assert_not_called()

    async def test_cancel_cancelled_task_raises_illegal_state(self) -> None:
        """TC-UT-AC-006: CANCELLED Task cancel → IllegalTaskStateError（§確定 B）。"""
        task_repo = AsyncMock()
        cancelled_task = make_cancelled_task()
        task_repo.find_by_id.return_value = cancelled_task

        service = _make_service(task_repo=task_repo)

        with pytest.raises(IllegalTaskStateError):
            await service.cancel_task(cancelled_task.id, reason="test")

        task_repo.save.assert_not_called()


# ---------------------------------------------------------------------------
# TC-UT-AC-007: retry_event Fail Fast（§確定 C）
# ---------------------------------------------------------------------------


class TestRetryEventFailFast:
    """TC-UT-AC-007: retry_event Fail Fast — PENDING → IllegalOutboxStateError（§確定 C）。"""

    pytestmark = pytest.mark.asyncio

    async def test_retry_pending_event_raises_illegal_outbox_state(self) -> None:
        """TC-UT-AC-007: status=PENDING の Event → IllegalOutboxStateError（reset_to_pending 未呼び出し）。"""
        outbox_event_repo = AsyncMock()
        pending_view = _make_outbox_view(status="PENDING")
        outbox_event_repo.find_by_id.return_value = pending_view

        service = _make_service(outbox_event_repo=outbox_event_repo)

        with pytest.raises(IllegalOutboxStateError):
            await service.retry_event(pending_view.event_id)

        outbox_event_repo.reset_to_pending.assert_not_called()


# ---------------------------------------------------------------------------
# TC-UT-AC-008: actor DI 確認（§確定 E）
# ---------------------------------------------------------------------------


class TestActorDI:
    """TC-UT-AC-008: actor フィールドが audit_log に記録される（§確定 E）。"""

    pytestmark = pytest.mark.asyncio

    async def test_actor_passed_to_audit_log_writer(self) -> None:
        """TC-UT-AC-008: actor='ceo_operator' → audit_log_writer.write() に actor='ceo_operator' が渡される。"""
        audit_log_writer = AsyncMock()
        task_repo = AsyncMock()
        task_repo.find_blocked.return_value = []

        service = _make_service(
            task_repo=task_repo,
            audit_log_writer=audit_log_writer,
            actor="ceo_operator",
        )
        await service.list_blocked_tasks()

        _, kwargs = audit_log_writer.write.call_args
        assert kwargs["actor"] == "ceo_operator"


# ---------------------------------------------------------------------------
# TC-UT-AC-009~013: 確定文言（MSG-AC-001〜005）照合
# ---------------------------------------------------------------------------


class TestMessageWording:
    """TC-UT-AC-009〜013: MSG-AC-001〜005 の確定文言照合。"""

    def test_task_not_found_error_message(self) -> None:
        """TC-UT-AC-009: TaskNotFoundError のメッセージに task_id が含まれる（MSG-AC-001）。"""
        task_id = uuid4()
        error = TaskNotFoundError(task_id)
        assert str(task_id) in str(error)

    def test_illegal_task_state_error_retry_message_contains_blocked(self) -> None:
        """TC-UT-AC-010: IllegalTaskStateError(retry) のメッセージに BLOCKED が含まれる（MSG-AC-002）。"""
        task_id = uuid4()
        error = IllegalTaskStateError(
            task_id=task_id,
            current_status=TaskStatus.IN_PROGRESS,
            action="retry",
            message=(
                f"[FAIL] Task {task_id} は BLOCKED 状態ではありません"
                f"（現在: IN_PROGRESS）。\n"
                "Next: 'bakufu admin list-blocked' で BLOCKED Task を確認してください。"
            ),
        )
        assert "BLOCKED" in str(error)
        assert "[FAIL]" in str(error)

    def test_illegal_task_state_error_cancel_message(self) -> None:
        """TC-UT-AC-011: IllegalTaskStateError(cancel) のメッセージに BLOCKED/PENDING/IN_PROGRESS が含まれる（MSG-AC-003）。"""
        task_id = uuid4()
        error = IllegalTaskStateError(
            task_id=task_id,
            current_status=TaskStatus.DONE,
            action="cancel",
            message=(
                f"[FAIL] Task {task_id} はキャンセル可能な状態ではありません"
                f"（現在: DONE）。\n"
                "Next: キャンセル対象は BLOCKED / PENDING / IN_PROGRESS 状態の Task のみです。"
            ),
        )
        msg = str(error)
        assert "[FAIL]" in msg
        # BLOCKED / PENDING / IN_PROGRESS のいずれかが含まれる
        assert any(s in msg for s in ("BLOCKED", "PENDING", "IN_PROGRESS"))

    def test_outbox_event_not_found_error_message(self) -> None:
        """TC-UT-AC-012: OutboxEventNotFoundError のメッセージに [FAIL] と event_id が含まれる（MSG-AC-004）。"""
        event_id = uuid4()
        error = OutboxEventNotFoundError(
            event_id=event_id,
            message=(
                f"[FAIL] Outbox Event {event_id} が見つかりません。\n"
                "Next: event_id を確認し、"
                "'bakufu admin list-dead-letters' で存在確認してください。"
            ),
        )
        assert "[FAIL]" in str(error)
        assert str(event_id) in str(error)

    def test_illegal_outbox_state_error_message_contains_dead_letter(self) -> None:
        """TC-UT-AC-013: IllegalOutboxStateError のメッセージに DEAD_LETTER が含まれる（MSG-AC-005）。"""
        event_id = uuid4()
        error = IllegalOutboxStateError(
            event_id=event_id,
            current_status="PENDING",
            message=(
                f"[FAIL] Outbox Event {event_id} は DEAD_LETTER 状態ではありません"
                f"（現在: PENDING）。\n"
                "Next: 'bakufu admin list-dead-letters' で DEAD_LETTER Event を確認してください。"
            ),
        )
        assert "DEAD_LETTER" in str(error)
        assert "[FAIL]" in str(error)


# ---------------------------------------------------------------------------
# TC-UT-AC-014: T2 対策 — args_json に raw last_error が含まれない
# ---------------------------------------------------------------------------


class TestArgsJsonSecurity:
    """TC-UT-AC-014: T2 — args_json に task の last_error が含まれない。"""

    pytestmark = pytest.mark.asyncio

    async def test_cancel_task_args_json_contains_only_task_id(self) -> None:
        """TC-UT-AC-014: cancel_task の args_json は task_id のみ（last_error は含まれない）。

        T2 脅威対策: args_json に task の生エラーテキストをそのまま格納しない。
        task の last_error は AuditLogWriterPort 経由で MaskedText カラムに書かれるが、
        args_json には混入しない。
        """
        audit_log_writer = AsyncMock()
        task_repo = AsyncMock()

        # last_error に機密情報を含む BLOCKED Task
        secret_error = "super_secret_token: abc123xyz"
        blocked_task = make_blocked_task(last_error=secret_error)
        task_repo.find_by_id.return_value = blocked_task

        service = _make_service(task_repo=task_repo, audit_log_writer=audit_log_writer)
        await service.cancel_task(blocked_task.id, reason="test")

        _, kwargs = audit_log_writer.write.call_args
        args_json = kwargs["args_json"]

        # args_json は {"task_id": str(task_id)} のみ
        assert "task_id" in args_json
        # last_error の内容が args_json に含まれていない
        assert secret_error not in str(args_json)
        assert "super_secret_token" not in str(args_json)
