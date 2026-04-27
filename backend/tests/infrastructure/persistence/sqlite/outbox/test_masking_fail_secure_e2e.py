"""Fail-Secure E2E injection tests
(TC-UT-PF-006-C complement, Confirmation F, Norman 前回 △ 宿題).

Confirmation F freezes that **listener-equivalent failures must never
let raw bytes hit the disk**. Earlier ``test_masking.py`` covers the
sentinel constants (``REDACT_MASK_ERROR`` / ``REDACTED_MASK_OVERFLOW``
/ ``REDACT_LISTENER_ERROR``) at the gateway layer, but the Fail-Secure
E2E loop — *gateway raises → DB SELECT shows sentinel* — was missing.
This file adds the three injection patterns Norman flagged:

1. :func:`mask_in` raises while encoding ``payload_json`` →
   ``MaskedJSONEncoded.process_bind_param`` catches the exception and
   writes ``json.dumps(REDACT_LISTENER_ERROR)`` instead. Subsequent
   SELECT returns the sentinel string.
2. :func:`mask` raises while encoding ``last_error`` →
   ``MaskedText.process_bind_param`` writes ``REDACT_LISTENER_ERROR``
   instead. SELECT returns the sentinel.
3. Same path for ``audit_log.error_text`` → confirms the gateway is
   wired across all three secret-bearing tables.

The injection is at the **gateway** (`mask` / `mask_in`) so the test
is independent of which TypeDecorator does the wiring; if Linus ever
swaps the masker implementation, the contract still holds.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from bakufu.infrastructure.persistence.sqlite.tables.audit_log import AuditLogRow
from bakufu.infrastructure.persistence.sqlite.tables.outbox import OutboxRow
from bakufu.infrastructure.security.masking import REDACT_LISTENER_ERROR
from sqlalchemy import select

from tests.factories.persistence_rows import make_audit_log_row, make_outbox_row

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.asyncio


def _force_mask_in_to_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make :func:`mask_in` raise when the TypeDecorator calls it.

    We patch the symbol the TypeDecorator imported (the
    ``base`` module's local ``mask_in`` binding), not the masking
    module's, because Python ``from X import Y`` captures the
    reference at import time.
    """
    from bakufu.infrastructure.persistence.sqlite import base as base_mod

    def _explode(_value: object) -> object:
        msg = "simulated mask_in failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(base_mod, "mask_in", _explode)


def _force_mask_to_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make :func:`mask` raise when the TypeDecorator calls it."""
    from bakufu.infrastructure.persistence.sqlite import base as base_mod

    def _explode(_value: object) -> str:
        msg = "simulated mask failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(base_mod, "mask", _explode)


class TestMaskInFailureRedactsPayloadJson:
    """Pattern 1: ``mask_in`` raise → ``payload_json`` becomes the sentinel.

    The raw secret in ``payload_json`` must NEVER reach the disk —
    the TypeDecorator catches the exception and writes
    ``json.dumps(REDACT_LISTENER_ERROR)`` so a SELECT returns
    ``REDACT_LISTENER_ERROR`` (a string, not the original dict).
    """

    async def test_payload_json_replaced_with_listener_error_sentinel(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fail-Secure E2E: secret payload never lands on disk if mask_in raises."""
        _force_mask_in_to_raise(monkeypatch)

        # The raw payload contains a sk-ant- key; if the Fail-Secure
        # path is broken, the SELECT below would return that key.
        row = make_outbox_row(
            payload_json={"key": "sk-ant-api03-" + "A" * 60},
            last_error=None,
        )

        async with session_factory() as session, session.begin():
            session.add(row)

        async with session_factory() as session:
            stmt = select(OutboxRow).where(OutboxRow.event_id == row.event_id)
            fetched = (await session.execute(stmt)).scalar_one()

        # SELECT must return the sentinel; the original secret must
        # never appear anywhere in the loaded value.
        assert fetched.payload_json == REDACT_LISTENER_ERROR
        assert "sk-ant-" not in str(fetched.payload_json)


class TestMaskFailureRedactsLastError:
    """Pattern 2: ``mask`` raise → ``last_error`` becomes the sentinel."""

    async def test_last_error_replaced_with_listener_error_sentinel(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fail-Secure E2E: last_error secret never lands on disk if mask raises."""
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
    """Pattern 3: ``mask`` raise on ``audit_log.error_text`` → sentinel.

    Same gateway, different table. Confirms the TypeDecorator wiring
    is consistent across all three secret-bearing tables.
    """

    async def test_audit_log_error_text_replaced_with_sentinel(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fail-Secure E2E: audit_log error_text secret never lands on disk."""
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

        # ``args_json`` is dict-typed, ``error_text`` is the str column
        # we drove the failure through.
        loaded_error = fetched.error_text
        assert loaded_error == REDACT_LISTENER_ERROR
        assert loaded_error is not None
        assert "Bearer" not in loaded_error
