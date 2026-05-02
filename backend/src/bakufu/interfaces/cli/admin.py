"""bakufu admin CLI — Typer 5 コマンド定義（M5-C）。

CEO が実行する管理コマンド:
  list-blocked      BLOCKED Task の一覧表示
  retry-task        BLOCKED Task を IN_PROGRESS に変更
  cancel-task       Task を CANCELLED に変更
  list-dead-letters dead-letter Outbox Event の一覧表示
  retry-event       dead-letter Event を PENDING にリセット

設計書: docs/features/admin-cli/cli/detailed-design.md
"""

from __future__ import annotations

import asyncio
import getpass
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

import typer

if TYPE_CHECKING:
    from bakufu.application.services.admin_service import AdminService

from bakufu.application.exceptions.task_exceptions import IllegalTaskStateError, TaskNotFoundError
from bakufu.domain.exceptions.outbox import IllegalOutboxStateError, OutboxEventNotFoundError
from bakufu.interfaces.cli import formatters

app = typer.Typer(
    name="admin",
    help="bakufu 管理 CLI — BLOCKED Task / dead-letter Event の復旧操作",
)


# ---------------------------------------------------------------------------
# list-blocked
# ---------------------------------------------------------------------------


@app.command("list-blocked")
def list_blocked(
    json_output: Annotated[bool, typer.Option("--json", help="JSON 形式で出力する")] = False,
) -> None:
    """BLOCKED 状態の Task 一覧を表示する（UC-AC-001）。"""

    async def _run() -> int:
        service = await _build_service()
        try:
            tasks = await service.list_blocked_tasks()
            typer.echo(formatters.format_blocked_tasks(tasks, json_output))
            return 0
        except Exception as exc:
            typer.echo(formatters.format_error(str(exc)), err=True)
            return 1

    raise typer.Exit(code=asyncio.run(_run()))


# ---------------------------------------------------------------------------
# retry-task
# ---------------------------------------------------------------------------


@app.command("retry-task")
def retry_task(
    task_id: Annotated[str, typer.Argument(help="BLOCKED Task の UUID")],
    json_output: Annotated[bool, typer.Option("--json", help="JSON 形式で出力する")] = False,
) -> None:
    """BLOCKED Task を IN_PROGRESS に変更する（UC-AC-002）。

    bakufu サーバーの StageWorker が次回起動時に自動的に再実行します。
    """
    parsed_id = _parse_uuid(task_id, arg_name="task_id")

    async def _run() -> int:
        service = await _build_service()
        try:
            await service.retry_task(parsed_id)
            msg = (
                f"Task {parsed_id} を BLOCKED → IN_PROGRESS に変更しました。"
                " bakufu サーバーの StageWorker が自動的に再実行します。"
            )
            typer.echo(
                formatters.format_success(
                    msg, json_output, command="retry-task", id_=str(parsed_id)
                )
            )
            return 0
        except (TaskNotFoundError, IllegalTaskStateError) as exc:
            typer.echo(formatters.format_error(str(exc)), err=True)
            return 1
        except Exception as exc:
            typer.echo(formatters.format_error(str(exc)), err=True)
            return 1

    raise typer.Exit(code=asyncio.run(_run()))


# ---------------------------------------------------------------------------
# cancel-task
# ---------------------------------------------------------------------------


@app.command("cancel-task")
def cancel_task(
    task_id: Annotated[str, typer.Argument(help="キャンセルする Task の UUID")],
    reason: Annotated[
        str, typer.Option("--reason", help="キャンセル理由")
    ] = "Admin CLI による手動キャンセル",
    json_output: Annotated[bool, typer.Option("--json", help="JSON 形式で出力する")] = False,
) -> None:
    """Task を CANCELLED に変更する（UC-AC-003）。

    対象: BLOCKED / PENDING / IN_PROGRESS 状態の Task のみ。
    """
    parsed_id = _parse_uuid(task_id, arg_name="task_id")

    async def _run() -> int:
        service = await _build_service()
        try:
            await service.cancel_task(parsed_id, reason)
            msg = f"Task {parsed_id} を CANCELLED に変更しました。"
            typer.echo(
                formatters.format_success(
                    msg, json_output, command="cancel-task", id_=str(parsed_id)
                )
            )
            return 0
        except (TaskNotFoundError, IllegalTaskStateError) as exc:
            typer.echo(formatters.format_error(str(exc)), err=True)
            return 1
        except Exception as exc:
            typer.echo(formatters.format_error(str(exc)), err=True)
            return 1

    raise typer.Exit(code=asyncio.run(_run()))


# ---------------------------------------------------------------------------
# list-dead-letters
# ---------------------------------------------------------------------------


@app.command("list-dead-letters")
def list_dead_letters(
    json_output: Annotated[bool, typer.Option("--json", help="JSON 形式で出力する")] = False,
) -> None:
    """DEAD_LETTER 状態の Outbox Event 一覧を表示する（UC-AC-004）。"""

    async def _run() -> int:
        service = await _build_service()
        try:
            events = await service.list_dead_letters()
            typer.echo(formatters.format_dead_letters(events, json_output))
            return 0
        except Exception as exc:
            typer.echo(formatters.format_error(str(exc)), err=True)
            return 1

    raise typer.Exit(code=asyncio.run(_run()))


# ---------------------------------------------------------------------------
# retry-event
# ---------------------------------------------------------------------------


@app.command("retry-event")
def retry_event(
    event_id: Annotated[str, typer.Argument(help="DEAD_LETTER Outbox Event の UUID")],
    json_output: Annotated[bool, typer.Option("--json", help="JSON 形式で出力する")] = False,
) -> None:
    """dead-letter Outbox Event を PENDING にリセットする（UC-AC-005）。

    Outbox Dispatcher が次回ポーリングで自動的に再 dispatch します。
    """
    parsed_id = _parse_uuid(event_id, arg_name="event_id")

    async def _run() -> int:
        service = await _build_service()
        try:
            await service.retry_event(parsed_id)
            msg = (
                f"Outbox Event {parsed_id} を DEAD_LETTER → PENDING にリセットしました。"
                " Outbox Dispatcher が次回ポーリングで再 dispatch します。"
            )
            typer.echo(
                formatters.format_success(
                    msg, json_output, command="retry-event", id_=str(parsed_id)
                )
            )
            return 0
        except (OutboxEventNotFoundError, IllegalOutboxStateError) as exc:
            typer.echo(formatters.format_error(str(exc)), err=True)
            return 1
        except Exception as exc:
            typer.echo(formatters.format_error(str(exc)), err=True)
            return 1

    raise typer.Exit(code=asyncio.run(_run()))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_uuid(raw: str, arg_name: str) -> UUID:
    """UUID 文字列をパースする。失敗時は MSG-AC-CLI-002 を stderr に出力して exit 1。

    §確定 B: UUID パースエラーは Typer callback で Fail Fast する。
    """
    try:
        return UUID(raw)
    except ValueError:
        msg = (
            f"[FAIL] {arg_name} が有効な UUID ではありません: {raw}\n"
            "Next: 'bakufu admin list-blocked' または "
            "'bakufu admin list-dead-letters' で正しい ID を確認してください。"
        )
        typer.echo(msg, err=True)
        raise typer.Exit(code=1) from None


async def _build_service() -> AdminService:
    """AdminService を構築して返す。

    session_factory を LiteBootstrap から取得し、factory callable を DI 注入する。
    Tx 管理（業務 Tx / audit_log Tx の分離）は AdminService 内部で行う（Option A）。
    遅延 import で循環参照リスクを回避する。
    """
    from bakufu.application.services.admin_service import AdminService
    from bakufu.infrastructure.persistence.sqlite.repositories.audit_log_writer import (
        SqliteAuditLogWriter,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.outbox_event_repository import (
        SqliteOutboxEventRepository,
    )
    from bakufu.infrastructure.persistence.sqlite.repositories.task_repository import (
        SqliteTaskRepository,
    )
    from bakufu.interfaces.cli.lite_bootstrap import LiteBootstrap

    session_factory = await LiteBootstrap.setup_db()
    return AdminService(
        session_factory=session_factory,
        task_repo_factory=SqliteTaskRepository,
        outbox_event_repo_factory=SqliteOutboxEventRepository,
        audit_log_writer_factory=SqliteAuditLogWriter,
        actor=_resolve_actor(),
    )


def _resolve_actor() -> str:
    """OS ユーザー名を取得する（§確定 E）。"""
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


__all__ = ["app"]
