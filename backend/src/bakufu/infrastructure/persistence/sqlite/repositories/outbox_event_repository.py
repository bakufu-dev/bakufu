"""OutboxEventRepositoryPort の SQLite 実装（admin-cli 用）。

``domain_event_outbox`` テーブルを対象に DEAD_LETTER 管理操作を実装する。
設計書: docs/features/admin-cli/application/detailed-design.md §確定 D
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bakufu.application.ports.outbox_event_repository import OutboxEventView
from bakufu.domain.exceptions.outbox import OutboxEventNotFoundError
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow

_DEAD_LETTER_STATUS = "DEAD_LETTER"
_PENDING_STATUS = "PENDING"


class SqliteOutboxEventRepository:
    """``OutboxEventRepositoryPort`` の SQLite 実装。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, event_id: UUID) -> OutboxEventView:
        """``event_id`` で Outbox Event を 1 件取得する。

        Raises:
            OutboxEventNotFoundError: 指定 event_id が DB に存在しない場合。
        """
        row = await self._session.get(OutboxRow, str(event_id))
        if row is None:
            raise OutboxEventNotFoundError(
                event_id=event_id,
                message=(
                    f"[FAIL] Outbox Event {event_id} が見つかりません。\n"
                    "Next: event_id を確認し、"
                    "'bakufu admin list-dead-letters' で存在確認してください。"
                ),
            )
        return self._to_view(row)

    async def list_dead_letters(self) -> list[OutboxEventView]:
        """``status == 'DEAD_LETTER'`` の Outbox Event を全件返す。

        ORDER BY updated_at DESC（最近 DEAD_LETTER 化したものが先頭）。
        0 件は空リスト。
        """
        rows = list(
            (
                await self._session.execute(
                    select(OutboxRow)
                    .where(OutboxRow.status == _DEAD_LETTER_STATUS)
                    .order_by(OutboxRow.updated_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [self._to_view(row) for row in rows]

    async def reset_to_pending(self, event_id: UUID) -> None:
        """Outbox Event を DEAD_LETTER → PENDING にリセットする（R1-5）。

        Raises:
            OutboxEventNotFoundError: 指定 event_id が DB に存在しない場合。
        """
        row = await self._session.get(OutboxRow, str(event_id))
        if row is None:
            raise OutboxEventNotFoundError(
                event_id=event_id,
                message=(
                    f"[FAIL] Outbox Event {event_id} が見つかりません。\n"
                    "Next: event_id を確認し、"
                    "'bakufu admin list-dead-letters' で存在確認してください。"
                ),
            )
        now = datetime.now(UTC)
        await self._session.execute(
            update(OutboxRow)
            .where(OutboxRow.event_id == str(event_id))
            .values(
                status=_PENDING_STATUS,
                attempt_count=0,
                next_attempt_at=now,
                updated_at=now,
            )
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _to_view(row: OutboxRow) -> OutboxEventView:
        """OutboxRow → OutboxEventView 変換（TypeDecorator-trust パターン）。"""
        return OutboxEventView(
            event_id=row.event_id,
            event_kind=row.event_kind,
            aggregate_id=row.aggregate_id,
            status=row.status,
            attempt_count=row.attempt_count,
            last_error=row.last_error,
            updated_at=row.updated_at,
        )


__all__ = ["SqliteOutboxEventRepository"]
