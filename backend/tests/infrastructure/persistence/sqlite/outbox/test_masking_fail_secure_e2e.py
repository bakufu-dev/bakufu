"""Fail-Secure E2E インジェクションテスト
（TC-UT-PF-006-C 補完, 確定 F, Norman 前回 △ 宿題）。

確定 F は「**リスナー相当の失敗が生バイトをディスクに到達させてはならない**」
ことを凍結している。先行する ``test_masking.py`` はゲートウェイ層で
sentinel 定数（``REDACT_MASK_ERROR`` / ``REDACTED_MASK_OVERFLOW``
/ ``REDACT_LISTENER_ERROR``）を検証するが、Fail-Secure E2E ループ
（*ゲートウェイが raise → DB SELECT が sentinel を返す*）は欠けていた。
本ファイルは Norman が指摘した 3 つのインジェクションパターンを補う:

1. :meth:`MaskingGateway.mask_in` が ``payload_json`` のエンコード中に raise →
   ``MaskedJSONEncoded.process_bind_param`` が例外を捕捉し、
   代わりに ``json.dumps(REDACT_LISTENER_ERROR)`` を書き込む。
   後続の SELECT は sentinel 文字列を返す。
2. :meth:`MaskingGateway.mask` が ``last_error`` のエンコード中に raise →
   ``MaskedText.process_bind_param`` が代わりに ``REDACT_LISTENER_ERROR``
   を書き込む。SELECT は sentinel を返す。
3. ``audit_log.error_text`` でも同経路 → ゲートウェイが秘密を持つ
   3 テーブルすべてに配線されていることを確認する。

インジェクションは**ゲートウェイ**（`MaskingGateway.mask` / `MaskingGateway.mask_in`）で行うため、
このテストは TypeDecorator の配線実装に依存しない。Linus がマスク
実装を差し替えても契約は維持される。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow
from bakufu.infrastructure.security.masking import REDACT_LISTENER_ERROR, MaskingGateway
from sqlalchemy import select

from tests.factories.persistence_rows import make_audit_log_row, make_outbox_row

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


def _force_mask_in_to_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """TypeDecorator が :meth:`MaskingGateway.mask_in` を呼んだとき raise させる。"""

    def _explode(cls: type[MaskingGateway], _value: object) -> object:
        del cls
        msg = "simulated mask_in failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(MaskingGateway, "mask_in", classmethod(_explode))


def _force_mask_to_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """TypeDecorator が :meth:`MaskingGateway.mask` を呼んだとき raise させる。"""

    def _explode(cls: type[MaskingGateway], _value: object) -> str:
        del cls
        msg = "simulated mask failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(MaskingGateway, "mask", classmethod(_explode))


class TestMaskInFailureRedactsPayloadJson:
    """パターン 1: ``mask_in`` が raise → ``payload_json`` が sentinel になる。

    ``payload_json`` の生秘密は決してディスクに到達してはならない —
    TypeDecorator が例外を捕捉し ``json.dumps(REDACT_LISTENER_ERROR)``
    を書き込むため、SELECT は ``REDACT_LISTENER_ERROR``（元の dict ではなく
    文字列）を返す。
    """

    async def test_payload_json_replaced_with_listener_error_sentinel(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fail-Secure E2E: mask_in が raise しても秘密 payload はディスクに到達しない。"""
        _force_mask_in_to_raise(monkeypatch)

        # 生 payload に sk-ant- キーが含まれる。Fail-Secure 経路が壊れていれば
        # 下の SELECT がそのキーを返してしまう。
        row = make_outbox_row(
            payload_json={"key": "sk-ant-api03-" + "A" * 60},
            last_error=None,
        )

        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(stmt)).scalar_one()

        # SELECT は sentinel を返さなければならず、元の秘密は
        # ロード値のどこにも現れてはならない。
        assert fetched.payload_json == REDACT_LISTENER_ERROR
        assert "sk-ant-" not in str(fetched.payload_json)


class TestMaskFailureRedactsLastError:
    """パターン 2: ``mask`` が raise → ``last_error`` が sentinel になる。"""

    async def test_last_error_replaced_with_listener_error_sentinel(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fail-Secure E2E: mask が raise しても last_error の秘密はディスクに到達しない。"""
        _force_mask_to_raise(monkeypatch)

        row = make_outbox_row(
            payload_json={"safe": "ok"},
            last_error="ghp_" + "X" * 40,
        )

        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(stmt)).scalar_one()

        assert fetched.last_error == REDACT_LISTENER_ERROR
        assert fetched.last_error is not None
        assert "ghp_" not in fetched.last_error


class TestMaskFailureRedactsAuditLogErrorText:
    """パターン 3: ``audit_log.error_text`` で ``mask`` が raise → sentinel。

    ゲートウェイは同じ、テーブルは別。TypeDecorator の配線が
    秘密を持つ 3 テーブル間で一貫していることを確認する。
    """

    async def test_audit_log_error_text_replaced_with_sentinel(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fail-Secure E2E: audit_log の error_text の秘密はディスクに到達しない。"""
        _force_mask_to_raise(monkeypatch)

        row = make_audit_log_row(
            args_json={"safe": "value"},
            error_text="Bearer eyJ.tokenpart.signature",
            executed_at=datetime.now(UTC),
        )

        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(AuditLogRow).where(AuditLogRow.id == row.id)
            fetched = (await session.execute(stmt)).scalar_one()

        # ``args_json`` は dict 型、``error_text`` は失敗を駆動した str 列。
        loaded_error = fetched.error_text
        assert loaded_error == REDACT_LISTENER_ERROR
        assert loaded_error is not None
        assert "Bearer" not in loaded_error
