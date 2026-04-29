"""Outbox dispatcher の Fail Loud WARN テスト
（TC-IT-PF-008-A / 008-B / 008-C / 008-D, 確定 K）。

Schneier 中等 3 物理保証 — ハンドラレジストリが空のまま
``domain_event_outbox`` の行が蓄積している場合、dispatcher は条件ごとに
WARN を 1 回だけ発行しなければならない（ログスパムも沈黙バックログも禁止）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from bakufu.infrastructure.persistence.sqlite.outbox import handler_registry
from bakufu.infrastructure.persistence.sqlite.outbox.dispatcher import (
    BACKLOG_WARN_THRESHOLD,
    OutboxDispatcher,
)
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow

from tests.factories.persistence_rows import make_outbox_row

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


async def _insert_pending_rows(
    session_factory: async_sessionmaker[AsyncSession],
    count: int,
) -> list[OutboxRow]:
    """dispatcher が拾えるように ``count`` 件の PENDING 行をバルク挿入する。"""
    rows: list[OutboxRow] = []
    async with session_factory() as session, session.begin():
        for _ in range(count):
            row = make_outbox_row(
                event_id=uuid4(),
                payload_json={"safe": "ok"},
                status="PENDING",
                next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
            )
            session.add(row)
            rows.append(row)
    return rows


class TestEmptyRegistryWarnOnFirstSeenPending:
    """TC-IT-PF-008-B: pending 行 + 空レジストリ → WARN を 1 回。"""

    async def test_warn_emitted_once_for_pending_with_empty_registry(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-B: pending 件数が 0 を超えると dispatcher が WARN を出力する。"""
        await _insert_pending_rows(session_factory, count=1)
        dispatcher = OutboxDispatcher(session_factory)

        caplog.clear()
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        warn_messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any(
            "Outbox has 1 pending events but handler_registry is empty" in m for m in warn_messages
        )


class TestEmptyRegistryWarnDoesNotSpam:
    """TC-IT-PF-008-C: 同じバックログに対する後続のポーリングでは再 WARN しない。"""

    async def test_second_poll_does_not_re_warn(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-C: 空レジストリ WARN はサイクルごとではなく 1 回だけ発火する。"""
        await _insert_pending_rows(session_factory, count=1)
        dispatcher = OutboxDispatcher(session_factory)

        # 1 回目のポーリング — WARN が出ることを期待。
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]
        # 2 回目のポーリング — 追加の WARN は出ないこと。
        caplog.clear()
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        assert all(
            "handler_registry is empty" not in r.getMessage()
            for r in caplog.records
            if r.levelname == "WARNING"
        )


class TestEmptyRegistryWarnRefiresAfterRegistration:
    """TC-IT-PF-008-A 系: 登録 + クリアで WARN トリガが再武装する。"""

    async def test_registering_then_clearing_re_arms_warning(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-A 系: 正常な登録サイクル後に WARN が再発火する。

        リセット仕様（確定 K）: ``_empty_registry_warned`` フラグは、
        ポーリングが「空でないレジストリ」または「空の pending キュー」を
        観測したときのみ戻る。よって現実的な再武装シーケンスは:

        1. Poll #1 — pending>0、レジストリ空 → WARN 発火。
        2. ハンドラを登録。
        3. Poll #2 — registry>0 → フラグリセット（WARN なし）。
        4. レジストリをクリア。
        5. Poll #3 — pending>0、レジストリ再び空 → WARN 再発火。
        """
        await _insert_pending_rows(session_factory, count=1)
        dispatcher = OutboxDispatcher(session_factory)

        # Poll 1: WARN が発火する。
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        # poll 2 で空でないレジストリを観測させるためハンドラを登録する。
        async def _noop(_payload: dict[str, object]) -> None:
            return None

        handler_registry.register("TestKind", _noop)

        # Poll 2: 静かにフラグをリセットする（新たな WARN は出ない）。
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        # 緊急修正のミスを再現するためハンドラを破棄する。
        handler_registry.clear()

        # Poll 3: 再び空、フラグはリセット済み → WARN 再発火。
        caplog.clear()
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]
        warn_messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("handler_registry is empty" in m for m in warn_messages)


class TestBacklogWarnThreshold:
    """TC-IT-PF-008-D: BACKLOG_WARN_THRESHOLD 超過の pending 行で別 WARN が発火する。

    BUG-PF-003 修正: ``OutboxDispatcher._backlog_last_warn_monotonic``
    のデフォルトが ``None`` になり、スロットルは「まだ警告していない」
    状態を「即座に警告する」と扱うようになった。以前のブート時レース
    （起動直後の CI クロックが 300 秒未満だと最初のバックログ WARN が
    抑制された問題）は解消したため、このテストはスロットルを過去日時に
    細工する必要なく閾値ロジックを実行する。
    """

    async def test_backlog_above_threshold_warns(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TC-IT-PF-008-D: PENDING 行が 100 を超えるとバックログ WARN が発火する。"""
        await _insert_pending_rows(session_factory, count=BACKLOG_WARN_THRESHOLD + 1)
        dispatcher = OutboxDispatcher(session_factory)

        caplog.clear()
        with caplog.at_level("WARNING"):
            await dispatcher._poll_once()  # pyright: ignore[reportPrivateUsage]

        warn_messages = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any(f"Outbox PENDING count={BACKLOG_WARN_THRESHOLD + 1}" in m for m in warn_messages)
        assert any("bakufu admin list-pending" in m for m in warn_messages)
