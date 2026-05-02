"""OutboxEventRepositoryPort — Outbox Event 操作 Port（admin-cli 用）。

AdminService が DEAD_LETTER な Outbox Event の参照・リセット操作に使う
Clean Architecture Port。SQLAlchemy の直接 import を application 層に持ち込まない
（§確定 D: Clean Architecture 保全）。

設計書: docs/features/admin-cli/application/detailed-design.md
"""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple, Protocol
from uuid import UUID


class OutboxEventView(NamedTuple):
    """Outbox Event の読み取り専用ビュー（Port の返却型）。

    ORM クラス（OutboxRow）を application 層に漏らさないための境界 VO。
    全フィールドはイミュータブル（NamedTuple）。
    """

    event_id: UUID
    event_kind: str
    aggregate_id: UUID
    status: str
    attempt_count: int
    last_error: str | None
    updated_at: datetime


class OutboxEventRepositoryPort(Protocol):
    """Outbox Event 操作の Port 契約（Admin CLI 用）。

    infrastructure 実装:
      ``bakufu.infrastructure.persistence.sqlite.repositories.outbox_event_repository``

    全メソッドは async。SQLAlchemy 型はこの Port 境界を越えない。
    """

    async def find_by_id(self, event_id: UUID) -> OutboxEventView:
        """``event_id`` で Outbox Event を 1 件取得する。

        Raises:
            OutboxEventNotFoundError: 指定 event_id が DB に存在しない場合。
        """
        ...

    async def list_dead_letters(self) -> list[OutboxEventView]:
        """``status == 'DEAD_LETTER'`` の Outbox Event を全件返す。

        0 件の場合は空リストを返す（エラーではない）。
        ORDER BY updated_at DESC（最近 DEAD_LETTER 化したものが先頭）。
        """
        ...

    async def reset_to_pending(self, event_id: UUID) -> None:
        """Outbox Event を DEAD_LETTER → PENDING にリセットする。

        リセット内容:
        - ``status = 'PENDING'``
        - ``attempt_count = 0``
        - ``next_attempt_at = now(UTC)``
        - ``updated_at = now(UTC)``

        Outbox Dispatcher の次回ポーリングで自動 dispatch される（R1-5）。

        Raises:
            OutboxEventNotFoundError: 指定 event_id が DB に存在しない場合。
        """
        ...


__all__ = ["OutboxEventRepositoryPort", "OutboxEventView"]
