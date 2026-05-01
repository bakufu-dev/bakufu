"""role-profile / http-api 結合テスト共有フィクスチャ。

``docs/features/deliverable-template/http-api/test-design/index.md`` §外部 I/O 依存マップ 準拠。

http-api-foundation / room / dt の conftest.py と同一パターン。
Empire 作成は HTTP API 経由（POST /api/empires）で行う。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class RpTestCtx:
    """RoleProfile 結合テスト用コンテキスト。

    ``client``: HTTP リクエスト送信 (FastAPI ASGI)
    ``session_factory``: 直接 DB 操作用セッションファクトリ
    """

    client: AsyncClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def rp_ctx(tmp_path: Path) -> AsyncIterator[RpTestCtx]:
    """RoleProfile テスト用 AsyncClient + session_factory。"""
    from bakufu.interfaces.http.app import create_app
    from httpx import ASGITransport

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = create_app()
    engine = make_test_engine(tmp_path / "rp_test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield RpTestCtx(client=client, session_factory=session_factory)

    await engine.dispose()


async def _create_empire(ctx: RpTestCtx, name: str = "テスト幕府") -> dict[str, Any]:
    """POST /api/empires → 201 を assert → JSON を返す。"""
    resp = await ctx.client.post("/api/empires", json={"name": name})
    assert resp.status_code == 201, f"Empire creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


async def _create_deliverable_template(
    ctx: RpTestCtx, name: str = "参照テンプレート"
) -> dict[str, Any]:
    """POST /api/deliverable-templates → 201 を assert → JSON を返す。"""
    body: dict[str, Any] = {
        "name": name,
        "description": "",
        "type": "MARKDOWN",
        "schema": "## guide",
        "version": {"major": 1, "minor": 0, "patch": 0},
        "acceptance_criteria": [],
        "composition": [],
    }
    resp = await ctx.client.post("/api/deliverable-templates", json=body)
    assert resp.status_code == 201, f"template creation failed: {resp.text}"
    return resp.json()  # type: ignore[return-value]


__all__ = [
    "RpTestCtx",
    "_create_deliverable_template",
    "_create_empire",
    "rp_ctx",
]
