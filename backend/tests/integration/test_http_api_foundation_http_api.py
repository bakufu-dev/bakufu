"""http-api-foundation / http-api 結合テスト (TC-IT-HAF-001, 002, 003, 004, 006, 007, 008)。

``docs/features/http-api-foundation/http-api/test-design.md`` §結合テストケース 準拠。

カバー範囲:
  TC-IT-HAF-001  GET /health → 200 {"status": "ok"} (REQ-HAF-002, feature-spec.md §9 #1)
  TC-IT-HAF-002  GET /nonexistent → 404 not_found (REQ-HAF-003, MSG-HAF-001, §9 #2)
  TC-IT-HAF-003  body 無しの POST → 422 validation_error (REQ-HAF-003, MSG-HAF-002, §9 #3)
  TC-IT-HAF-004  GET で RuntimeError → 500 スタックトレース無し
                 (REQ-HAF-003, MSG-HAF-003, §9 #4, T3)
  TC-IT-HAF-006  get_session() が AsyncSession を yield する (REQ-HAF-004, §9 #6)
  TC-IT-HAF-007  lifespan: startup で session_factory を設定し、shutdown で engine を dispose
                 (REQ-HAF-001/007, §9 #7)
  TC-IT-HAF-008  POST + 不正 Origin → 403 CSRF failed (MSG-HAF-004, T2, §9 #8)

Issue: #55
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# TC-IT-HAF-001: GET /health → 200 {"status": "ok"}
# ---------------------------------------------------------------------------
class TestHealthEndpoint:
    """TC-IT-HAF-001: GET /health が HTTP 200 と {"status": "ok"} を返す。"""

    async def test_health_returns_200(self, app_client: AsyncClient) -> None:
        response = await app_client.get("/health")
        assert response.status_code == 200

    async def test_health_body_is_status_ok(self, app_client: AsyncClient) -> None:
        response = await app_client.get("/health")
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# TC-IT-HAF-002: GET /nonexistent → 404 not_found (MSG-HAF-001)
# ---------------------------------------------------------------------------
class TestNotFoundHandler:
    """TC-IT-HAF-002: 未定義ルート → code=not_found の 404 ErrorResponse。"""

    async def test_not_found_returns_404(self, app_client: AsyncClient) -> None:
        response = await app_client.get("/nonexistent")
        assert response.status_code == 404

    async def test_not_found_error_code_is_not_found(self, app_client: AsyncClient) -> None:
        response = await app_client.get("/nonexistent")
        assert response.json()["error"]["code"] == "not_found"

    async def test_not_found_error_message(self, app_client: AsyncClient) -> None:
        response = await app_client.get("/nonexistent")
        assert response.json()["error"]["message"] == "Resource not found."

    async def test_not_found_response_has_error_key(self, app_client: AsyncClient) -> None:
        """レスポンスボディは {"error": {...}} エンベロープ形式に従わねばならない (REQ-HAF-003)。"""
        response = await app_client.get("/nonexistent")
        body = response.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]


# ---------------------------------------------------------------------------
# TC-IT-HAF-003: POST no body → 422 validation_error (MSG-HAF-002)
# ---------------------------------------------------------------------------
class TestValidationErrorHandler:
    """TC-IT-HAF-003: 必須 body 欠落の POST → code=validation_error の 422。"""

    async def test_missing_body_returns_422(self, app_client: AsyncClient) -> None:
        response = await app_client.post("/test/validation-required")
        assert response.status_code == 422

    async def test_validation_error_code(self, app_client: AsyncClient) -> None:
        response = await app_client.post("/test/validation-required")
        assert response.json()["error"]["code"] == "validation_error"

    async def test_validation_error_message_starts_with_prefix(
        self, app_client: AsyncClient
    ) -> None:
        response = await app_client.post("/test/validation-required")
        assert response.json()["error"]["message"].startswith("Request validation failed")


# ---------------------------------------------------------------------------
# TC-IT-HAF-004: RuntimeError → 500, no stack trace (MSG-HAF-003, T3)
# ---------------------------------------------------------------------------
class TestInternalErrorHandler:
    """TC-IT-HAF-004: 未処理 RuntimeError → スタックトレース無しの 500 (T3)。"""

    async def test_exception_returns_500(self, app_client: AsyncClient) -> None:
        response = await app_client.get("/test/raise-exception")
        assert response.status_code == 500

    async def test_internal_error_code(self, app_client: AsyncClient) -> None:
        response = await app_client.get("/test/raise-exception")
        assert response.json()["error"]["code"] == "internal_error"

    async def test_internal_error_message(self, app_client: AsyncClient) -> None:
        response = await app_client.get("/test/raise-exception")
        assert response.json()["error"]["message"] == "An internal server error occurred."

    async def test_no_traceback_in_body(self, app_client: AsyncClient) -> None:
        """T3: スタックトレース非露出 ── body に traceback が含まれてはならない。"""
        response = await app_client.get("/test/raise-exception")
        body = response.text
        assert "Traceback" not in body

    async def test_no_runtime_error_in_body(self, app_client: AsyncClient) -> None:
        """T3: 内部例外のクラス名がレスポンスボディに漏れてはならない。"""
        response = await app_client.get("/test/raise-exception")
        assert "RuntimeError" not in response.text

    async def test_no_test_error_message_in_body(self, app_client: AsyncClient) -> None:
        """T3: 内部エラーメッセージがレスポンスボディに漏れてはならない。"""
        response = await app_client.get("/test/raise-exception")
        # "test internal error" は RuntimeError のメッセージ。出現してはならない。
        assert "test internal error" not in response.text


# ---------------------------------------------------------------------------
# TC-IT-HAF-006: get_session() yields AsyncSession (REQ-HAF-004)
# ---------------------------------------------------------------------------
class TestGetSessionDI:
    """TC-IT-HAF-006: get_session() DI 依存が実際の AsyncSession を yield する。"""

    async def test_session_type_is_async_session(self, app_client: AsyncClient) -> None:
        """Session DI が AsyncSession を yield する（None や誤った型ではない）。"""
        response = await app_client.get("/test/session-type")
        assert response.status_code == 200
        assert response.json()["session_type"] == "AsyncSession"


# ---------------------------------------------------------------------------
# TC-IT-HAF-007: lifespan startup sets session_factory; shutdown disposes engine
# ---------------------------------------------------------------------------
class TestLifespan:
    """TC-IT-HAF-007: lifespan の完全サイクル ── startup + health + shutdown。"""

    async def test_lifespan_startup_sets_session_factory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """lifespan の startup イベント後、app.state.session_factory が None でない。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        from bakufu.infrastructure.config import data_dir

        data_dir.reset()

        from bakufu.interfaces.http.app import create_app

        app = create_app()
        queue: asyncio.Queue[Any] = asyncio.Queue()
        sent: list[Any] = []

        async def receive() -> Any:
            return await queue.get()

        async def send(msg: Any) -> None:
            sent.append(msg)

        scope: dict[str, object] = {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
        }
        task = asyncio.create_task(app(scope, receive, send))

        await queue.put({"type": "lifespan.startup"})
        await asyncio.sleep(0.2)

        assert hasattr(app.state, "session_factory")
        assert app.state.session_factory is not None

        await queue.put({"type": "lifespan.shutdown"})
        await task
        data_dir.reset()

    async def test_lifespan_startup_emits_startup_complete(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lifespan startup が lifespan.startup.complete ASGI イベントを送る。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        from bakufu.infrastructure.config import data_dir

        data_dir.reset()

        from bakufu.interfaces.http.app import create_app

        app = create_app()
        queue: asyncio.Queue[Any] = asyncio.Queue()
        sent: list[Any] = []

        async def receive() -> Any:
            return await queue.get()

        async def send(msg: Any) -> None:
            sent.append(msg)

        scope: dict[str, object] = {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
        }
        task = asyncio.create_task(app(scope, receive, send))

        await queue.put({"type": "lifespan.startup"})
        await asyncio.sleep(0.2)

        startup_events = [m for m in sent if m.get("type") == "lifespan.startup.complete"]
        assert len(startup_events) == 1

        await queue.put({"type": "lifespan.shutdown"})
        await task
        data_dir.reset()

    async def test_lifespan_health_responds_after_startup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """lifespan startup 後、GET /health が HTTP 200 と {"status": "ok"} を返す。"""
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        from bakufu.infrastructure.config import data_dir

        data_dir.reset()

        from bakufu.interfaces.http.app import create_app

        app = create_app()
        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def receive() -> Any:
            return await queue.get()

        async def send(msg: Any) -> None:
            pass

        scope: dict[str, object] = {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
        }
        task = asyncio.create_task(app(scope, receive, send))

        await queue.put({"type": "lifespan.startup"})
        await asyncio.sleep(0.2)

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        await queue.put({"type": "lifespan.shutdown"})
        await task
        data_dir.reset()

    async def test_lifespan_engine_dispose_called_on_shutdown(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """lifespan shutdown 後、engine.dispose() がちょうど 1 回呼ばれている。

        SQLAlchemy ではインスタンス属性が read-only なため、AsyncEngine.dispose を
        クラスレベルでパッチして呼び出しを追跡する。
        """
        monkeypatch.setenv("BAKUFU_DATA_DIR", str(tmp_path))
        from bakufu.infrastructure.config import data_dir

        data_dir.reset()

        from unittest.mock import patch as mock_patch

        from sqlalchemy.ext.asyncio import AsyncEngine

        dispose_calls: list[int] = []
        original_dispose = AsyncEngine.dispose

        async def tracking_dispose(self: AsyncEngine, close: bool = True) -> None:
            dispose_calls.append(1)
            await original_dispose(self, close=close)

        from bakufu.interfaces.http.app import create_app

        app = create_app()
        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def receive() -> Any:
            return await queue.get()

        async def send(msg: Any) -> None:
            pass

        scope: dict[str, object] = {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
        }

        with mock_patch.object(AsyncEngine, "dispose", new=tracking_dispose):
            task = asyncio.create_task(app(scope, receive, send))

            await queue.put({"type": "lifespan.startup"})
            await asyncio.sleep(0.2)
            assert len(dispose_calls) == 0  # まだ dispose されていない

            await queue.put({"type": "lifespan.shutdown"})
            await task

        assert len(dispose_calls) == 1  # shutdown でちょうど 1 回 dispose される
        data_dir.reset()


# ---------------------------------------------------------------------------
# TC-IT-HAF-008: POST + evil Origin → 403 CSRF check failed (MSG-HAF-004, T2)
# ---------------------------------------------------------------------------
class TestCsrfOriginMiddleware:
    """TC-IT-HAF-008: CSRF Origin チェック ── 不正 Origin → 403、
    Origin なし → 許可 (MVP ルール)。"""

    async def test_evil_origin_returns_403(self, app_client: AsyncClient) -> None:
        """Origin: http://evil.example.com の POST → 403。"""
        response = await app_client.post(
            "/test/validation-required",
            headers={"Origin": "http://evil.example.com"},
            json={"name": "test"},
        )
        assert response.status_code == 403

    async def test_evil_origin_error_code_is_forbidden(self, app_client: AsyncClient) -> None:
        response = await app_client.post(
            "/test/validation-required",
            headers={"Origin": "http://evil.example.com"},
            json={"name": "test"},
        )
        assert response.json()["error"]["code"] == "forbidden"

    async def test_evil_origin_error_message(self, app_client: AsyncClient) -> None:
        response = await app_client.post(
            "/test/validation-required",
            headers={"Origin": "http://evil.example.com"},
            json={"name": "test"},
        )
        assert response.json()["error"]["message"] == "CSRF check failed: Origin not allowed."

    async def test_no_origin_header_passes(self, app_client: AsyncClient) -> None:
        """MVP ルール: Origin ヘッダなしの POST は通過する（AI agent / SDK サポート）。"""
        response = await app_client.post(
            "/test/validation-required",
            json={"name": "test"},
        )
        assert response.status_code == 200

    async def test_allowed_origin_passes(self, app_client: AsyncClient) -> None:
        """許可された Origin（デフォルト: http://localhost:5173）の POST は通過する。"""
        response = await app_client.post(
            "/test/validation-required",
            headers={"Origin": "http://localhost:5173"},
            json={"name": "test"},
        )
        assert response.status_code == 200

    async def test_safe_method_get_ignores_origin(self, app_client: AsyncClient) -> None:
        """GET は安全メソッド: 不正 Origin でも CSRF チェック対象外。"""
        response = await app_client.get(
            "/health",
            headers={"Origin": "http://evil.example.com"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# TC-IT-HAF-009: http_exception_handler status_code 分岐 (ヘルスバーグ指摘 #1)
# ---------------------------------------------------------------------------
class TestHttpExceptionHandlerBranching:
    """TC-IT-HAF-009: http_exception_handler が status code を別個の error code に振り分ける。

    404 以外の HTTP 例外が "not_found" に潰されないこと、および 404 が引き続き
    MSG-HAF-001 と完全一致するメッセージを返すことを保証する。
    """

    async def test_404_returns_not_found_code(self, app_client: AsyncClient) -> None:
        """GET /nonexistent → code "not_found"（分岐リファクタ後に再検証）。"""
        response = await app_client.get("/nonexistent")
        assert response.json()["error"]["code"] == "not_found"

    async def test_404_returns_msg_haf_001_message(self, app_client: AsyncClient) -> None:
        """GET /nonexistent → message が MSG-HAF-001
        "Resource not found." と一致（"Not Found" ではなく）。"""
        response = await app_client.get("/nonexistent")
        assert response.json()["error"]["message"] == "Resource not found."

    async def test_405_returns_method_not_allowed_code(self, app_client: AsyncClient) -> None:
        """POST /health（GET 専用ルート、Origin なし）→ code "method_not_allowed" の 405。"""
        response = await app_client.post("/health")
        assert response.status_code == 405

    async def test_405_error_code_is_method_not_allowed(self, app_client: AsyncClient) -> None:
        """POST /health → error code "method_not_allowed"（"not_found" ではない）。"""
        response = await app_client.post("/health")
        assert response.json()["error"]["code"] == "method_not_allowed"

    async def test_405_has_error_envelope(self, app_client: AsyncClient) -> None:
        """POST /health → レスポンスが
        {"error": {"code": ..., "message": ...}} エンベロープを用いる。"""
        response = await app_client.post("/health")
        body = response.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
