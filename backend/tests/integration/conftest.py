"""http-api-foundation 結合テスト共通フィクスチャ。

``docs/features/http-api-foundation/http-api/test-design.md`` §外部 I/O 依存マップ
に従う。

pytest の ``tmp_path`` 配下に実 SQLite を用いる ── DB のモックは行わない。
ほとんどのテストでは FastAPI の lifespan を意図的にバイパスする:
``app.state.session_factory`` を直接注入することで本番 lifespan
(ファイルシステム上の DB パス解決) を不要にする。TC-IT-HAF-007 では
実 lifespan を別途検証する。

設計メモ ── ルートハンドラはモジュール直下に置く必要がある
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``from __future__ import annotations`` (PEP 563) により**全ての型注釈**が
文字列化される。FastAPI はこれを ``typing.get_type_hints(fn, ...)`` 経由で
解決し、名前は ``fn.__globals__`` (モジュールレベル名前空間) を引く。
そのため ``SessionDep`` やローカル Pydantic モデルを利用するルートハンドラ
は、**必ず**本ファイルのモジュール直下で定義する必要がある ── そうしない
と FastAPI が型解決を行う際に ``conftest.__dict__`` に必要な記号が揃わない。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

# ── FastAPI の型注釈解決に必要なモジュールレベル記号 ──────────────────────────
from bakufu.interfaces.http.dependencies import SessionDep
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel


class _Item(BaseModel):
    """テスト用バリデーションエンドポイントのリクエストボディモデル。"""

    name: str


# ── モジュールレベルのルートハンドラ関数群 ────────────────────────────────────
# 全ハンドラは FastAPI の ``get_type_hints`` 呼び出しが ``conftest.__dict__``
# から型注釈を解決できるよう、モジュール直下で定義しなければならない。


async def _validation_endpoint(item: _Item) -> dict[str, str]:
    """POST /test/validation-required ── JSON ボディが必須。欠落時は 422。"""
    return {"name": item.name}


async def _exception_endpoint() -> None:
    """GET /test/raise-exception ── 500 ハンドラ検証用に RuntimeError を送出する。"""
    raise RuntimeError("test internal error")


async def _session_di_endpoint(session: SessionDep) -> dict[str, str]:
    """GET /test/session-type ── SessionDep が AsyncSession を yield することを確認する。"""
    return {"session_type": type(session).__name__}


def _build_test_router() -> APIRouter:
    """モジュール直下のハンドラを事前配線したテスト専用ルータを構築する。"""
    router = APIRouter()
    router.add_api_route(
        "/test/validation-required",
        _validation_endpoint,
        methods=["POST"],
    )
    router.add_api_route(
        "/test/raise-exception",
        _exception_endpoint,
        methods=["GET"],
    )
    router.add_api_route(
        "/test/session-type",
        _session_di_endpoint,
        methods=["GET"],
    )
    return router


@pytest_asyncio.fixture
async def empire_app_client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    """empire ルート + 実 SQLite tempdb を配線した FastAPI app に繋ぐ httpx.AsyncClient。

    ``app_client`` と異なりテスト専用ルートは追加しない (empire ルータは
    ``HttpApplicationFactory.create()`` 経由で既に登録されている)。ORM テーブルは
    ``create_all_tables`` で作成され、CRUD 操作は実 SQLite DB に到達する。
    """
    from bakufu.interfaces.http.app import HttpApplicationFactory

    from tests.factories.db import create_all_tables, make_test_engine, make_test_session_factory

    app = HttpApplicationFactory.create()
    engine = make_test_engine(tmp_path / "test.db")
    await create_all_tables(engine)
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()


@pytest_asyncio.fixture
async def app_client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    """テスト用ルート + 実 SQLite tempdb を配線した FastAPI app に繋ぐ httpx.AsyncClient。

    lifespan は意図的にバイパスし、``app.state.session_factory`` を temp-db
    エンジンから直接設定する。``raise_app_exceptions=False`` を指定しなけ
    れば TC-IT-HAF-004 が 500 JSON ボディをアサートできない ── Starlette 1.0
    の ``ServerErrorMiddleware`` はレスポンス送信後に必ず例外を再送出する
    ため、httpx 側ではテストレベルの ``RuntimeError`` として浮上してしまう。
    """
    from bakufu.interfaces.http.app import HttpApplicationFactory

    from tests.factories.db import make_test_engine, make_test_session_factory

    app = HttpApplicationFactory.create()

    # ── 本番 lifespan をバイパス ────────────────────────────────────────────
    engine = make_test_engine(tmp_path / "test.db")
    session_factory = make_test_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.include_router(_build_test_router())

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await engine.dispose()
