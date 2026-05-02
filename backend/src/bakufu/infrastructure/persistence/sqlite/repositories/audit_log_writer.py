"""AuditLogWriterPort の SQLite 実装（admin-cli 用）。

``audit_log`` テーブルへの追記専用操作を実装する。
MaskedJSONEncoded / MaskedText TypeDecorator が永続化時に自動的にマスキングを適用する
（BUG-PF-001 修正済み）。

設計書: docs/features/admin-cli/application/detailed-design.md §確定 D
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow


class SqliteAuditLogWriter:
    """``AuditLogWriterPort`` の SQLite 実装。

    Core INSERT（``session.execute(insert(...))``）を使用する。
    ``MaskedJSONEncoded`` / ``MaskedText`` TypeDecorator の ``process_bind_param``
    は Core INSERT 経路でも発火するため（BUG-PF-001 修正）、args_json / error_text
    は手動マスキング不要。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(
        self,
        actor: str,
        command: str,
        args_json: dict[str, object],
        result: str,
        error_text: str | None = None,
    ) -> None:
        """audit_log テーブルに 1 行 INSERT する。

        書き込み失敗時は例外を再 raise する（audit_log の欠落は許容しない §確定 A）。
        """
        await self._session.execute(
            insert(AuditLogRow).values(
                id=uuid4(),
                actor=actor,
                command=command,
                args_json=args_json,
                result=result,
                error_text=error_text,
                executed_at=datetime.now(UTC),
            )
        )


__all__ = ["SqliteAuditLogWriter"]
