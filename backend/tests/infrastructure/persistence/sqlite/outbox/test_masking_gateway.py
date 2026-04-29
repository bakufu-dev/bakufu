"""マスキングゲートウェイ統合テスト（TC-IT-PF-007 / 020 / 021 / 022）。

Schneier 申し送り #6 + 確定 R1-D（フリップ後）の**核**となる契約 —
呼び出し側が ORM マッパーを迂回して
``insert(table).values(...)`` の生 Core ステートメントを使う場合でも
マスキングゲートウェイは発火しなければならない。元の設計は
``event.listens_for(target, 'before_insert/before_update')`` マッパー
イベントを使っていたが、BUG-PF-001 によりそれらのリスナーは Core の
``insert(table).values(...)`` 経路では**発火しない**ことが判明した。
R1-D は ``MaskedJSONEncoded`` / ``MaskedText``
:class:`~sqlalchemy.types.TypeDecorator` 列に差し戻された。これらの
``process_bind_param`` フックは ORM フラッシュと Core 経路の**両方**で
発火し、まさに R1-D がリスナーで得ようとした性質を満たす。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest
from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow
from bakufu.infrastructure.persistence.sqlite.tables.pid_registry import (
    PidRegistryRow,
)
from sqlalchemy import insert, select

from tests.factories.persistence_rows import (
    make_audit_log_row,
    make_outbox_row,
    make_pid_registry_row,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio

# 実形の secret。SELECT の前にすべて redact されねばならない。
ANTHROPIC_KEY = "sk-ant-api03-" + "A" * 60
GITHUB_PAT = "ghp_" + "X" * 40
AWS_KEY = "AKIA1234567890ABCDEF"  # gitleaks:allow — synthetic test fixture, not a real key
SLACK_TOKEN = "xoxb-1234567890-token-data"
BEARER_PHRASE = "Authorization: Bearer eyJ.tokenpart.signature"


def _outbox_columns(row: OutboxRow) -> dict[str, object]:
    """Project an OutboxRow factory output to a dict of column→value."""
    return {
        "event_id": row.event_id,
        "event_kind": row.event_kind,
        "aggregate_id": row.aggregate_id,
        "payload_json": row.payload_json,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "next_attempt_at": row.next_attempt_at,
        "last_error": row.last_error,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "dispatched_at": row.dispatched_at,
    }


class TestOutboxMaskingViaOrm:
    """TC-IT-PF-007: ORM パス INSERT は payload_json + last_error を redact する。"""

    async def test_payload_json_redacted_after_insert(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-007: payload_json 内の Anthropic + GitHub PAT は redact される。"""
        row = make_outbox_row(
            payload_json={"key": ANTHROPIC_KEY, "github_pat": GITHUB_PAT},
            last_error=AWS_KEY,
        )
        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(stmt)).scalar_one()

        payload = cast("dict[str, object]", fetched.payload_json)
        assert "<REDACTED:ANTHROPIC_KEY>" in str(payload["key"])
        assert "<REDACTED:GITHUB_PAT>" in str(payload["github_pat"])
        assert fetched.last_error is not None
        assert "<REDACTED:AWS_ACCESS_KEY>" in fetched.last_error


class TestOutboxMaskingViaRawSql:
    """TC-IT-PF-020: 生 ``insert(table).values(...)`` でもマスキングゲートウェイが発火する。

    R1-D-flip 後の契約 — マスキングゲートウェイは列 TypeDecorator
    :class:`~bakufu.infrastructure.persistence.sqlite.base.MaskedJSONEncoded`
    および :class:`~bakufu.infrastructure.persistence.sqlite.base.MaskedText` 経由で配線される。
    それらの ``process_bind_param`` はバインドパラメータ解決時に毎回実行されるため、
    ORM フラッシュと Core ``insert(table).values(...)`` の両方が masking される。
    将来の Repository PR は生 SQL に到達することで redaction を回避できない。
    """

    async def test_raw_sql_path_redacts_payload(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-020: 生 insert パスも同様に payload_json + last_error を redact。"""
        row = make_outbox_row(
            payload_json={"key": ANTHROPIC_KEY},
            last_error=GITHUB_PAT,
        )
        async with session_factory() as session, session.begin():
            stmt = insert(OutboxRow).values(**_outbox_columns(row))
            await session.execute(stmt)

        async with session_factory() as session:
            sel = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(sel)).scalar_one()

        payload = cast("dict[str, object]", fetched.payload_json)
        assert "<REDACTED:ANTHROPIC_KEY>" in str(payload["key"])
        assert fetched.last_error is not None
        assert "<REDACTED:GITHUB_PAT>" in fetched.last_error


class TestOutboxMaskingOnUpdate:
    """TC-IT-PF-021: ``before_update`` は insert と同様に update を redact する。"""

    async def test_update_path_redacts_last_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-021: 行を DEAD_LETTER として再マーク、last_error に生 secret を含む。"""
        row = make_outbox_row(payload_json={"safe": "value"}, last_error=None)
        async with session_factory() as session, session.begin():
            session.add(row)

        # 次に読み込み + 新しい secret を含むデータで更新。
        async with session_factory() as session, session.begin():
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            target = (await session.execute(stmt)).scalar_one()
            target.status = "DEAD_LETTER"
            target.last_error = AWS_KEY
            target.updated_at = datetime.now(UTC)

        async with session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(stmt)).scalar_one()
        assert fetched.last_error is not None
        assert "<REDACTED:AWS_ACCESS_KEY>" in fetched.last_error


class TestAuditLogAndPidRegistryMaskingHook:
    """TC-IT-PF-022: フックは他の 2 つの secret を含むテーブルに配線される。"""

    async def test_audit_log_redacts_args_and_error(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-022 (audit_log): args_json + error_text が masking される。"""
        row = make_audit_log_row(
            args_json={"token": SLACK_TOKEN},
            error_text=BEARER_PHRASE,
        )
        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(AuditLogRow).where(AuditLogRow.id == row.id)
            fetched = (await session.execute(stmt)).scalar_one()
        args = cast("dict[str, object]", fetched.args_json)
        assert "<REDACTED:SLACK_TOKEN>" in str(args["token"])
        assert fetched.error_text is not None
        assert "<REDACTED:BEARER>" in fetched.error_text

    async def test_pid_registry_redacts_cmd(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """TC-IT-PF-022 (pid_registry): cmd column masked."""
        row = make_pid_registry_row(cmd=f"claude --api-key={ANTHROPIC_KEY} --task xyz")
        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(PidRegistryRow).where(PidRegistryRow.pid == row.pid)
            fetched = (await session.execute(stmt)).scalar_one()
        assert "<REDACTED:ANTHROPIC_KEY>" in fetched.cmd
        # The plaintext ``ANTHROPIC_KEY`` must not survive.
        assert ANTHROPIC_KEY not in fetched.cmd
