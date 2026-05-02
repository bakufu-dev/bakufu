"""admin-cli Typer コマンド 結合テスト（TC-IT-AC-CLI-001〜012）。

設計書: docs/features/admin-cli/cli/test-design.md §結合テストケース

テスト戦略:
  - CliRunner(mix_stderr=False) で Typer コマンドを同プロセス内で呼び出す
  - AdminService を AsyncMock でスタブ化し、CLI 層の契約のみを検証する
    （引数解析・出力形式・exit code・エラーメッセージ）
  - TC-IT-AC-CLI-012 のみ実 BAKUFU_DATA_DIR 設定で LiteBootstrap のエラーパスを検証

注意: CliRunner は同期呼び出し。コマンド内部の asyncio.run() はランナー内で実行される。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from bakufu.application.exceptions.task_exceptions import IllegalTaskStateError, TaskNotFoundError
from bakufu.application.services.admin_service import BlockedTaskSummary, DeadLetterSummary
from bakufu.domain.exceptions.outbox import OutboxEventNotFoundError
from bakufu.interfaces.cli.admin import app


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_cli_runner() -> CliRunner:
    # Click 8.2+ では mix_stderr が廃止され、result.stdout / result.stderr が常に独立
    return CliRunner()


def _make_mock_session() -> AsyncMock:
    """async with session, session.begin(): をサポートするモックセッションを返す。"""
    session = AsyncMock()
    # async with session: をサポート
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    # session.begin() が返す async context manager
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_ctx)
    return session


def _patch_build_service(
    mock_service: AsyncMock,
    mock_session: AsyncMock,
) -> patch:
    """_build_service_with_session をモックするコンテキストマネージャを返す。"""
    from bakufu.application.services.admin_service import AdminService

    async def _fake_build() -> tuple:
        return mock_service, mock_session

    return patch("bakufu.interfaces.cli.admin._build_service_with_session", new=_fake_build)


def _make_blocked_summary(
    *,
    last_error: str = "test error",
) -> BlockedTaskSummary:
    return BlockedTaskSummary(
        task_id=uuid4(),
        room_id=uuid4(),
        last_error=last_error,
        blocked_at=datetime.now(UTC),
    )


def _make_dead_letter_summary() -> DeadLetterSummary:
    return DeadLetterSummary(
        event_id=uuid4(),
        event_kind="TaskEventEmitted",
        aggregate_id=uuid4(),
        attempt_count=3,
        last_error="dispatch failed",
        updated_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# TC-IT-AC-CLI-001: list-blocked — テーブル形式デフォルト出力
# ---------------------------------------------------------------------------


class TestListBlocked:
    """TC-IT-AC-CLI-001〜003: list-blocked コマンドのテスト。"""

    def test_list_blocked_default_table_format(self) -> None:
        """TC-IT-AC-CLI-001: list-blocked → exit 0 + テーブル形式（TASK ID ヘッダ）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        summary = _make_blocked_summary()
        mock_service.list_blocked_tasks.return_value = [summary]

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["list-blocked"])

        assert result.exit_code == 0
        assert "TASK ID" in result.output
        assert str(summary.task_id) in result.output

    def test_list_blocked_json_format(self) -> None:
        """TC-IT-AC-CLI-002: list-blocked --json → exit 0 + 有効な JSON 配列（§確定 D / R1-7）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        summary = _make_blocked_summary(last_error="some error")
        mock_service.list_blocked_tasks.return_value = [summary]

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["list-blocked", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        item = data[0]
        assert "task_id" in item
        assert "room_id" in item
        assert "blocked_at" in item
        assert "last_error" in item
        assert str(summary.task_id) == item["task_id"]

    def test_list_blocked_empty_shows_human_message(self) -> None:
        """TC-IT-AC-CLI-003: list-blocked 0件 → exit 0 + "BLOCKED Task はありません" メッセージ（§確定 D）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        mock_service.list_blocked_tasks.return_value = []

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["list-blocked"])

        assert result.exit_code == 0
        assert "BLOCKED Task はありません" in result.output


# ---------------------------------------------------------------------------
# TC-IT-AC-CLI-004〜006: retry-task コマンド
# ---------------------------------------------------------------------------


class TestRetryTask:
    """TC-IT-AC-CLI-004〜006: retry-task コマンドのテスト。"""

    def test_retry_task_success_exit0_with_ok_message(self) -> None:
        """TC-IT-AC-CLI-004: retry-task 正常系 → exit 0 + [OK] + IN_PROGRESS が stdout（§確定 C）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        mock_service.retry_task.return_value = None  # 正常終了
        task_id = uuid4()

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["retry-task", str(task_id)])

        assert result.exit_code == 0
        assert "[OK]" in result.output
        assert "IN_PROGRESS" in result.output

    def test_retry_task_invalid_uuid_exit1_with_fail_on_stderr(self) -> None:
        """TC-IT-AC-CLI-005: 無効 UUID → exit 1 + [FAIL] が stderr（MSG-AC-CLI-002 / §確定 B / T2）。

        AdminService は呼ばれない（Fail Fast）。
        """
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["retry-task", "not-a-uuid"])

        assert result.exit_code == 1
        assert "[FAIL]" in result.stderr
        # AdminService が一度も呼ばれていない
        mock_service.retry_task.assert_not_called()

    def test_retry_task_not_found_exit1_with_fail_on_stderr(self) -> None:
        """TC-IT-AC-CLI-006: TaskNotFoundError → exit 1 + [FAIL] が stderr（MSG-AC-001）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        task_id = uuid4()
        mock_service.retry_task.side_effect = TaskNotFoundError(task_id)

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["retry-task", str(task_id)])

        assert result.exit_code == 1
        assert "[FAIL]" in result.stderr


# ---------------------------------------------------------------------------
# TC-IT-AC-CLI-007: cancel-task コマンド
# ---------------------------------------------------------------------------


class TestCancelTask:
    """TC-IT-AC-CLI-007: cancel-task コマンドのテスト。"""

    def test_cancel_task_success_exit0_with_ok_message(self) -> None:
        """TC-IT-AC-CLI-007: cancel-task 正常系 → exit 0 + [OK] + CANCELLED が stdout（§確定 C）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        mock_service.cancel_task.return_value = None
        task_id = uuid4()

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["cancel-task", str(task_id)])

        assert result.exit_code == 0
        assert "[OK]" in result.output
        assert "CANCELLED" in result.output


# ---------------------------------------------------------------------------
# TC-IT-AC-CLI-008〜009: list-dead-letters コマンド
# ---------------------------------------------------------------------------


class TestListDeadLetters:
    """TC-IT-AC-CLI-008〜009: list-dead-letters コマンドのテスト。"""

    def test_list_dead_letters_table_format(self) -> None:
        """TC-IT-AC-CLI-008: list-dead-letters → exit 0 + テーブル形式（EVENT ID ヘッダ）（§確定 D）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        summary = _make_dead_letter_summary()
        mock_service.list_dead_letters.return_value = [summary]

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["list-dead-letters"])

        assert result.exit_code == 0
        assert "EVENT ID" in result.output
        assert "KIND" in result.output

    def test_list_dead_letters_json_format(self) -> None:
        """TC-IT-AC-CLI-009a: list-dead-letters --json → exit 0 + 有効な JSON 配列（§確定 D）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        summary = _make_dead_letter_summary()
        mock_service.list_dead_letters.return_value = [summary]

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["list-dead-letters", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        item = data[0]
        assert "event_id" in item
        assert "event_kind" in item
        assert "attempt_count" in item

    def test_list_dead_letters_json_empty(self) -> None:
        """TC-IT-AC-CLI-009b: list-dead-letters --json 0件 → exit 0 + "[]"（§確定 D JSON 0件）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        mock_service.list_dead_letters.return_value = []

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["list-dead-letters", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []


# ---------------------------------------------------------------------------
# TC-IT-AC-CLI-010〜011: retry-event コマンド
# ---------------------------------------------------------------------------


class TestRetryEvent:
    """TC-IT-AC-CLI-010〜011: retry-event コマンドのテスト。"""

    def test_retry_event_success_exit0_with_ok_message(self) -> None:
        """TC-IT-AC-CLI-010: retry-event 正常系 → exit 0 + [OK] + PENDING が stdout（§確定 C）。"""
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        mock_service.retry_event.return_value = None
        event_id = uuid4()

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["retry-event", str(event_id)])

        assert result.exit_code == 0
        assert "[OK]" in result.output
        assert "PENDING" in result.output

    def test_retry_event_invalid_uuid_exit1_with_fail_on_stderr(self) -> None:
        """TC-IT-AC-CLI-011: 無効 UUID → exit 1 + [FAIL] が stderr（MSG-AC-CLI-002 / §確定 B / T2）。

        AdminService は呼ばれない（Fail Fast）。
        """
        runner = _make_cli_runner()
        mock_service = AsyncMock()
        mock_session = _make_mock_session()

        with _patch_build_service(mock_service, mock_session):
            result = runner.invoke(app, ["retry-event", "invalid-uuid"])

        assert result.exit_code == 1
        assert "[FAIL]" in result.stderr
        mock_service.retry_event.assert_not_called()


# ---------------------------------------------------------------------------
# TC-IT-AC-CLI-012: LiteBootstrap — DB 不在 → MSG-AC-CLI-001 + exit 1
# ---------------------------------------------------------------------------


class TestLiteBootstrapError:
    """TC-IT-AC-CLI-012: DB ファイル不在 → [FAIL] + exit 1（MSG-AC-CLI-001 / §確定 A）。"""

    def test_list_blocked_db_not_found_exit1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-IT-AC-CLI-012: BAKUFU_DATA_DIR に存在しない DB パス → exit 1 + [FAIL] が出力（MSG-AC-CLI-001）。"""
        runner = _make_cli_runner()

        # 存在しない DATA_DIR を設定（bakufu.db が存在しないことが保証される）
        nonexistent_dir = tmp_path / "nonexistent_db_dir"
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(nonexistent_dir))

        # AdminService を mock しない → LiteBootstrap の Fail Fast パスをテスト
        result = runner.invoke(app, ["list-blocked"])

        assert result.exit_code == 1
        # [FAIL] メッセージが stderr または stdout に出力される（LiteBootstrap は print で出力）
        combined_output = (result.output or "") + (result.stderr or "")
        assert "[FAIL]" in combined_output
