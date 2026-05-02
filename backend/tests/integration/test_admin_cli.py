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

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typer.testing import CliRunner

from bakufu.application.exceptions.task_exceptions import IllegalTaskStateError, TaskNotFoundError
from bakufu.application.services.admin_service import BlockedTaskSummary, DeadLetterSummary
from bakufu.domain.exceptions.outbox import OutboxEventNotFoundError
from bakufu.domain.value_objects import TaskStatus
from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow
from bakufu.interfaces.cli.admin import app
from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory
from tests.factories.directive import make_directive
from tests.factories.empire import make_empire
from tests.factories.room import make_room
from tests.factories.task import make_blocked_task, make_done_task, make_task
from tests.factories.workflow import make_workflow


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
    mock_session: AsyncMock,  # session_factory 注入方式では不要だが呼び出し元との互換のため残す
) -> patch:
    """_build_service をモックするコンテキストマネージャを返す。

    Option-A 修正後: Tx 管理は AdminService 内部に移動したため、
    CLI 層では AdminService インスタンスのみを返す。
    """
    async def _fake_build() -> AsyncMock:
        return mock_service

    return patch("bakufu.interfaces.cli.admin._build_service", new=_fake_build)


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


# ---------------------------------------------------------------------------
# TC-E2E-AC-001〜003: CLI経由フルパスでの audit_log 永続化検証（§確定A / Option-A 修正確認）
#
# ヘルスバーグ指摘対応:
#   業務Tx と audit_log Tx が独立 session で実行され、業務Tx の rollback 後も
#   audit_log INSERT が独立 commit で永続化されることを実 DB + CLI 全経路で証明する。
#
# 設計書: docs/features/admin-cli/cli/detailed-design.md §確定A
#         docs/features/admin-cli/application/test-design.md §TC-E2E-AC
#
# テスト戦略:
#   - _build_service_with_session を一切モックしない（CLI全経路）
#   - 実 SQLite bakufu.db + BAKUFU_DATA_DIR 設定で LiteBootstrap を通す
#   - 非同期操作（DB setup / audit_log 検証）は asyncio.run() で sync テスト内から呼ぶ
#     （CliRunner が asyncio.run() を使う都合上、テスト関数を sync にする必要がある）
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# E2E テスト用ヘルパー
# ---------------------------------------------------------------------------


async def _create_bakufu_db(db_path: Path) -> None:
    """テスト用 bakufu.db を作成してスキーマを展開する。"""
    engine = make_test_engine(db_path)
    await create_all_tables(engine)
    await engine.dispose()


async def _read_audit_logs_from_db(db_path: Path) -> list[AuditLogRow]:
    """audit_log テーブルの全行を executed_at 昇順で取得する。"""
    engine = make_test_engine(db_path)
    sf = make_test_session_factory(engine)
    try:
        async with sf() as session:
            result = await session.execute(
                select(AuditLogRow).order_by(AuditLogRow.executed_at.asc())
            )
            return list(result.scalars().all())
    finally:
        await engine.dispose()


async def _seed_entity_hierarchy(db_path: Path) -> tuple[UUID, UUID]:
    """empire → workflow → room → directive をシードして (room_id, directive_id) を返す。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.directive_repository import (
        SqliteDirectiveRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.empire_repository import (
        SqliteEmpireRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.room_repository import (
        SqliteRoomRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.workflow_repository import (
        SqliteWorkflowRepository,
    )

    engine = make_test_engine(db_path)
    sf = make_test_session_factory(engine)
    empire = make_empire()
    workflow = make_workflow()
    room = make_room(workflow_id=workflow.id)
    directive = make_directive(target_room_id=room.id)
    try:
        async with sf() as session, session.begin():
            await SqliteEmpireRepository(session).save(empire)
        async with sf() as session, session.begin():
            await SqliteWorkflowRepository(session).save(workflow)
        async with sf() as session, session.begin():
            await SqliteRoomRepository(session).save(room, empire.id)
        async with sf() as session, session.begin():
            await SqliteDirectiveRepository(session).save(directive)
    finally:
        await engine.dispose()
    return room.id, directive.id


async def _seed_task(db_path: Path, task: object) -> None:
    """Task を DB に保存する。"""
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )

    engine = make_test_engine(db_path)
    sf = make_test_session_factory(engine)
    try:
        async with sf() as session, session.begin():
            await SqliteTaskRepository(session).save(task)
    finally:
        await engine.dispose()


def _init_masking_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """masking 初期化に必要な環境変数をクリアして masking.init() を呼ぶ。"""
    for key in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OAUTH_CLIENT_SECRET",
        "BAKUFU_DISCORD_BOT_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    from bakufu.infrastructure.security import masking

    masking.init()


class TestAuditLogPersistenceViaCLI:
    """TC-E2E-AC-001〜003: CLI経由フルパスでの audit_log 永続化検証。

    **§確定A 契約**: 全 Admin CLI 操作の後（成功・失敗を問わず）、
    audit_log テーブルに対応レコードが追記される。

    ヘルスバーグ指摘（Option-A 修正後の確認テスト）:
    - AdminService が session_factory を受け取り、業務Tx と audit_log Tx を分離する修正後、
      業務Tx の rollback（失敗時）の影響を audit_log Tx が受けないことを実 DB で証明する。
    - _build_service_with_session を一切モックしない（CLI全経路）。
    """

    def test_retry_nonexistent_task_fail_audit_log_persisted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-E2E-AC-001: retry-task で TaskNotFoundError → exit 1 AND audit_log result='FAIL' が永続化。

        §確定A 核心検証:
        CLI 経由フルパスで業務Tx が rollback しても audit_log の FAIL 記録が永続化される。
        CLI が _build_service_with_session をモックしない実 DB 接続で検証する。
        """
        db_path = tmp_path / "bakufu.db"
        asyncio.run(_create_bakufu_db(db_path))
        _init_masking_env(monkeypatch)
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))

        runner = _make_cli_runner()
        nonexistent_id = uuid4()
        result = runner.invoke(app, ["retry-task", str(nonexistent_id)])

        # CLI は TaskNotFoundError → exit 1
        assert result.exit_code == 1

        # §確定A: audit_log に result='FAIL' が永続化されている
        audit_logs = asyncio.run(_read_audit_logs_from_db(db_path))
        assert len(audit_logs) == 1, (
            f"audit_log が 1 件期待されるが {len(audit_logs)} 件。"
            f" 業務Tx の rollback が audit_log Tx を巻き込んでいる可能性がある。"
        )
        assert audit_logs[0].result == "FAIL"
        assert audit_logs[0].command == "retry-task"
        assert str(nonexistent_id) in str(audit_logs[0].args_json)

    def test_cancel_nonexistent_task_fail_audit_log_persisted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-E2E-AC-002: cancel-task で TaskNotFoundError → exit 1 AND audit_log result='FAIL' が永続化。"""
        db_path = tmp_path / "bakufu.db"
        asyncio.run(_create_bakufu_db(db_path))
        _init_masking_env(monkeypatch)
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))

        runner = _make_cli_runner()
        nonexistent_id = uuid4()
        result = runner.invoke(app, ["cancel-task", str(nonexistent_id)])

        assert result.exit_code == 1

        audit_logs = asyncio.run(_read_audit_logs_from_db(db_path))
        assert len(audit_logs) == 1, (
            f"audit_log が 1 件期待されるが {len(audit_logs)} 件。"
            f" 業務Tx の rollback が audit_log Tx を巻き込んでいる可能性がある。"
        )
        assert audit_logs[0].result == "FAIL"
        assert audit_logs[0].command == "cancel-task"

    def test_retry_task_illegal_state_fail_audit_log_persisted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-E2E-AC-003: DONE Task の retry-task → IllegalTaskStateError + audit_log result='FAIL' 永続化。

        §確定B: Fail Fast 後も audit_log FAIL が記録される。
        Task が存在するが不正ステータスのケース（DB seed 必要）。
        """
        db_path = tmp_path / "bakufu.db"
        asyncio.run(_create_bakufu_db(db_path))
        _init_masking_env(monkeypatch)
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))

        # entity hierarchy + DONE task をシード
        room_id, directive_id = asyncio.run(_seed_entity_hierarchy(db_path))
        done_task = make_done_task(room_id=room_id, directive_id=directive_id)
        asyncio.run(_seed_task(db_path, done_task))

        runner = _make_cli_runner()
        result = runner.invoke(app, ["retry-task", str(done_task.id)])

        assert result.exit_code == 1
        assert "[FAIL]" in (result.output + result.stderr)

        audit_logs = asyncio.run(_read_audit_logs_from_db(db_path))
        assert len(audit_logs) == 1, (
            f"audit_log が 1 件期待されるが {len(audit_logs)} 件"
        )
        assert audit_logs[0].result == "FAIL"
        assert audit_logs[0].command == "retry-task"

    def test_retry_blocked_task_ok_audit_log_persisted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """TC-E2E-AC-004: BLOCKED Task の retry-task 成功 → exit 0 AND audit_log result='OK' が永続化。

        正常系: 成功時も audit_log に result='OK' が記録される（§確定A の両面検証）。
        """
        db_path = tmp_path / "bakufu.db"
        asyncio.run(_create_bakufu_db(db_path))
        _init_masking_env(monkeypatch)
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))

        # entity hierarchy + BLOCKED task をシード
        room_id, directive_id = asyncio.run(_seed_entity_hierarchy(db_path))
        blocked_task = make_blocked_task(room_id=room_id, directive_id=directive_id)
        asyncio.run(_seed_task(db_path, blocked_task))

        runner = _make_cli_runner()
        result = runner.invoke(app, ["retry-task", str(blocked_task.id)])

        assert result.exit_code == 0
        assert "[OK]" in result.output

        audit_logs = asyncio.run(_read_audit_logs_from_db(db_path))
        assert len(audit_logs) == 1
        assert audit_logs[0].result == "OK"
        assert audit_logs[0].command == "retry-task"
