"""AdminService — admin-cli 5 コマンドのアプリケーションサービス（M5-C）。

全 public メソッドは try/finally 構造で audit_log の記録を保証する（§確定 A）。
「LLM を呼ぶ」「Queue に投入する」責務を持たない — Task の状態変更のみを担う。
StageWorker の起動時リカバリスキャン（§確定J）が IN_PROGRESS Task をピックアップして
LLM 実行を再開する。

**Tx 分離方針（§確定 Option A）**:
業務 Tx と audit_log Tx は **独立した別 session** で実行する。
``session_factory`` を DI 注入し、各 public メソッド内で業務用 session を生成する。
``_write_audit()`` では audit 専用 session を生成するため、業務 Tx の rollback に
audit_log INSERT が巻き込まれることはない。

設計書:
  docs/features/admin-cli/application/detailed-design.md
  docs/features/admin-cli/feature-spec.md
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, NamedTuple
from uuid import UUID

from bakufu.application.exceptions.task_exceptions import IllegalTaskStateError, TaskNotFoundError
from bakufu.application.ports.audit_log_writer import AuditLogWriterPort
from bakufu.application.ports.outbox_event_repository import OutboxEventRepositoryPort
from bakufu.application.ports.task_repository import TaskRepository
from bakufu.domain.exceptions.outbox import IllegalOutboxStateError
from bakufu.domain.value_objects import SYSTEM_AGENT_ID, TaskId, TaskStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

_DEAD_LETTER_STATUS = "DEAD_LETTER"


class BlockedTaskSummary(NamedTuple):
    """BLOCKED Task の表示用サマリー（list-blocked コマンドの返却型）。"""

    task_id: TaskId
    room_id: UUID
    last_error: str
    blocked_at: datetime


class DeadLetterSummary(NamedTuple):
    """dead-letter Event の表示用サマリー（list-dead-letters コマンドの返却型）。"""

    event_id: UUID
    event_kind: str
    aggregate_id: UUID
    attempt_count: int
    last_error: str | None
    updated_at: datetime


class AdminService:
    """Admin CLI 操作のアプリケーションサービス。

    **不変条件**: 全 public メソッドは操作の成否に依らず audit_log を記録する
    （try/finally §確定 A）。失敗操作も ``result='FAIL'`` で記録することで
    「試みた事実」が audit_log に残る。

    **Tx 分離**: ``session_factory`` を保持し、業務操作と audit_log 記録を
    それぞれ独立した session / commit で実行する（§確定 Option A）。
    業務 Tx が rollback されても ``_write_audit()`` は独立した session で
    コミットするため、audit_log の欠落が発生しない。

    ``actor`` は DI 時に OS ユーザー名（``getpass.getuser()`` 相当）を注入する
    （§確定 E: AdminService 自体は OS 環境依存の情報を取得しない）。
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        task_repo_factory: Callable[[AsyncSession], TaskRepository],
        outbox_event_repo_factory: Callable[[AsyncSession], OutboxEventRepositoryPort],
        audit_log_writer_factory: Callable[[AsyncSession], AuditLogWriterPort],
        actor: str,
    ) -> None:
        self._session_factory = session_factory
        self._task_repo_factory = task_repo_factory
        self._outbox_event_repo_factory = outbox_event_repo_factory
        self._audit_log_writer_factory = audit_log_writer_factory
        self._actor = actor

    # ------------------------------------------------------------------
    # Public commands
    # ------------------------------------------------------------------

    async def list_blocked_tasks(self) -> list[BlockedTaskSummary]:
        """BLOCKED 状態の全 Task を返す（UC-AC-001）。

        ``TaskRepositoryPort.find_blocked()`` を使い、``BlockedTaskSummary`` に変換する。
        audit_log に ``command=list-blocked`` / ``result=OK`` を記録する。
        """
        error_text: str | None = None
        try:
            async with self._session_factory() as session, session.begin():
                repo = self._task_repo_factory(session)
                tasks = await repo.find_blocked()
                return [
                    BlockedTaskSummary(
                        task_id=task.id,
                        room_id=task.room_id,
                        last_error=task.last_error or "",
                        blocked_at=task.updated_at,
                    )
                    for task in tasks
                ]
        except Exception as exc:
            error_text = str(exc)
            raise
        finally:
            await self._write_audit(
                command="list-blocked",
                args_json={},
                result="OK" if error_text is None else "FAIL",
                error_text=error_text,
            )

    async def retry_task(self, task_id: TaskId) -> None:
        """BLOCKED Task を IN_PROGRESS に戻す（UC-AC-002）。

        Fail Fast: ``task.status != BLOCKED`` の場合は即座に ``IllegalTaskStateError``
        を送出する（§確定 B / R1-2）。

        Task.unblock_retry() を呼んで DB に保存するのみ。LLM 実行は行わない。
        StageWorker の起動時リカバリスキャン（§確定J）が IN_PROGRESS Task を拾う。
        """
        error_text: str | None = None
        try:
            async with self._session_factory() as session, session.begin():
                repo = self._task_repo_factory(session)
                task = await repo.find_by_id(task_id)
                if task is None:
                    raise TaskNotFoundError(task_id)

                if task.status != TaskStatus.BLOCKED:
                    raise IllegalTaskStateError(
                        task_id=task_id,
                        current_status=task.status,
                        action="retry",
                        message=(
                            f"[FAIL] Task {task_id} は BLOCKED 状態ではありません"
                            f"（現在: {task.status}）。\n"
                            "Next: 'bakufu admin list-blocked' で"
                            " BLOCKED Task を確認してください。"
                        ),
                    )

                updated = task.unblock_retry(updated_at=datetime.now(UTC))
                await repo.save(updated)
        except Exception as exc:
            error_text = str(exc)
            raise
        finally:
            await self._write_audit(
                command="retry-task",
                args_json={"task_id": str(task_id)},
                result="OK" if error_text is None else "FAIL",
                error_text=error_text,
            )

    async def cancel_task(self, task_id: TaskId, reason: str) -> None:
        """Task を CANCELLED に遷移させる（UC-AC-003）。

        Fail Fast: ``task.status ∉ {BLOCKED, PENDING, IN_PROGRESS}`` の場合は
        即座に ``IllegalTaskStateError`` を送出する（§確定 B / R1-3）。

        AWAITING_EXTERNAL_REVIEW 状態の Task はスコープ外（Phase 2）。
        """
        _cancelable = {TaskStatus.BLOCKED, TaskStatus.PENDING, TaskStatus.IN_PROGRESS}
        error_text: str | None = None
        try:
            async with self._session_factory() as session, session.begin():
                repo = self._task_repo_factory(session)
                task = await repo.find_by_id(task_id)
                if task is None:
                    raise TaskNotFoundError(task_id)

                if task.status not in _cancelable:
                    raise IllegalTaskStateError(
                        task_id=task_id,
                        current_status=task.status,
                        action="cancel",
                        message=(
                            f"[FAIL] Task {task_id} はキャンセル可能な状態ではありません"
                            f"（現在: {task.status}）。\n"
                            "Next: キャンセル対象は BLOCKED / PENDING / IN_PROGRESS"
                            " 状態の Task のみです。"
                        ),
                    )

                updated = task.cancel(
                    by_owner_id=SYSTEM_AGENT_ID,
                    reason=reason,
                    updated_at=datetime.now(UTC),
                )
                await repo.save(updated)
        except Exception as exc:
            error_text = str(exc)
            raise
        finally:
            await self._write_audit(
                command="cancel-task",
                args_json={"task_id": str(task_id)},
                result="OK" if error_text is None else "FAIL",
                error_text=error_text,
            )

    async def list_dead_letters(self) -> list[DeadLetterSummary]:
        """DEAD_LETTER 状態の全 Outbox Event を返す（UC-AC-004）。

        audit_log に ``command=list-dead-letters`` / ``result=OK`` を記録する。
        """
        error_text: str | None = None
        try:
            async with self._session_factory() as session, session.begin():
                repo = self._outbox_event_repo_factory(session)
                events = await repo.list_dead_letters()
                return [
                    DeadLetterSummary(
                        event_id=ev.event_id,
                        event_kind=ev.event_kind,
                        aggregate_id=ev.aggregate_id,
                        attempt_count=ev.attempt_count,
                        last_error=ev.last_error,
                        updated_at=ev.updated_at,
                    )
                    for ev in events
                ]
        except Exception as exc:
            error_text = str(exc)
            raise
        finally:
            await self._write_audit(
                command="list-dead-letters",
                args_json={},
                result="OK" if error_text is None else "FAIL",
                error_text=error_text,
            )

    async def retry_event(self, event_id: UUID) -> None:
        """DEAD_LETTER な Outbox Event を PENDING にリセットする（UC-AC-005）。

        Fail Fast: ``status != 'DEAD_LETTER'`` の場合は即座に
        ``IllegalOutboxStateError`` を送出する（§確定 C / R1-5）。

        ``outbox_event_repo.reset_to_pending()`` は attempt_count をリセットし
        next_attempt_at を now(UTC) に設定する。Outbox Dispatcher の次回ポーリングで
        自動 dispatch される。
        """
        error_text: str | None = None
        try:
            async with self._session_factory() as session, session.begin():
                repo = self._outbox_event_repo_factory(session)
                event_view = await repo.find_by_id(event_id)

                if event_view.status != _DEAD_LETTER_STATUS:
                    raise IllegalOutboxStateError(
                        event_id=event_id,
                        current_status=event_view.status,
                        message=(
                            f"[FAIL] Outbox Event {event_id} は DEAD_LETTER 状態ではありません"
                            f"（現在: {event_view.status}）。\n"
                            "Next: 'bakufu admin list-dead-letters' で"
                            " DEAD_LETTER Event を確認してください。"
                        ),
                    )

                await repo.reset_to_pending(event_id)
        except Exception as exc:
            error_text = str(exc)
            raise
        finally:
            await self._write_audit(
                command="retry-event",
                args_json={"event_id": str(event_id)},
                result="OK" if error_text is None else "FAIL",
                error_text=error_text,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _write_audit(
        self,
        command: str,
        args_json: dict[str, object],
        result: str,
        error_text: str | None,
    ) -> None:
        """独立した session で audit_log に 1 行追記する（§確定 A / Option A）。

        業務 Tx とは **別の** session を生成してコミットするため、業務 Tx が
        rollback されても audit_log INSERT は確実にコミットされる。

        audit_log 書き込み失敗は例外を握り潰さず再 raise する。
        「操作証跡の欠落は許容しない」（§確定 A）。
        """
        async with self._session_factory() as audit_session, audit_session.begin():
            writer = self._audit_log_writer_factory(audit_session)
            await writer.write(
                actor=self._actor,
                command=command,
                args_json=args_json,
                result=result,
                error_text=error_text,
            )


__all__ = ["AdminService", "BlockedTaskSummary", "DeadLetterSummary"]
